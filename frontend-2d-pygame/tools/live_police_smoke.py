"""Exercise police workflows through the actual native event loop and local API."""
import os
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
import sys,json,time,threading,subprocess,urllib.request
from pathlib import Path
frontend=Path(__file__).resolve().parents[1]
project=frontend.parent
sys.path.insert(0,str(frontend))
import pygame
from app.application import Application
from app.state import ActiveScreen

url='http://127.0.0.1:8106'
process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.api.main:app','--host','127.0.0.1','--port','8106'],
                         cwd=project,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
app=None
errors=[]
def request(path,payload=None):
    req=urllib.request.Request(url+path,data=json.dumps(payload).encode() if payload is not None else None,
                               headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as response:
        return json.load(response)
def state():
    return request('/state')
def until(predicate,seconds=20):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(.04)
    raise AssertionError('Police native flow timed out: '+(app._status_msg if app else 'startup'))
def press(button):
    for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
        pygame.event.post(pygame.event.Event(kind,button=1,pos=button.rect.center))
def ready_press(button):
    until(lambda:not app.op_runner.is_running and button.enabled)
    press(button)
def type_node(screen,label):
    press(screen._node)
    for _ in range(10):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_BACKSPACE,unicode='',mod=0))
    for char in label:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=ord(char.lower()),unicode=char,mod=0))
    until(lambda:screen._node.text==label)
def pause():
    if app.playing:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE,unicode=' ',mod=0))
        until(lambda:not app.playing)
def screenshot(name):
    app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/name))))
try:
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            state()
            break
        except Exception:
            if process.poll() is not None:
                raise RuntimeError('Police test backend failed to start')
            time.sleep(.1)
    else:
        raise RuntimeError('Police test backend startup timed out')
    request('/start',{'seed':42})
    app=Application(url)
    def control():
        try:
            until(lambda:app.state.has_graph)
            app._post_update(('callback',lambda:app.navigate(ActiveScreen.POLICE)))
            until(lambda:app.state.active_screen==ActiveScreen.POLICE)
            screen=app.screens[ActiveScreen.POLICE]
            initial=state()
            police=initial['police']
            assert len(police['stations'])==3 and len(police['units'])==10 and not police['reports']
            root=police['stations'][0]['node_id']
            edge=next(e for e in initial['graph']['edges'] if root in (e['node_a'],e['node_b']) and not e['blocked'])
            target=edge['node_b'] if edge['node_a']==root else edge['node_a']
            label=next(n['label'] for n in initial['graph']['nodes'] if n['id']==target)
            ranked=[]
            for unit in police['units']:
                route=request('/simulation/route',{'src':unit['position'],'dst':target})
                if route['reachable']:
                    ranked.append((route['path_cost'],unit['id']))
            expected=min(ranked)[1]
            type_node(screen,label)
            ready_press(screen._submit)
            until(lambda:len(state()['police']['reports'])==1)
            assert state()['police']['reports'][0]['unit_id']==expected
            until(lambda:state()['police']['reports'][0]['status']=='RESOLVED')
            until(lambda:not app.playing)
            first=state()
            assert first['police']['summary']['police_handled']==1
            assert any(u['position']!=v['position'] for u,v in zip(first['police']['units'],police['units']))
            # Reproduce the user's OFF -> manual report sequence using native clicks.
            ready_press(screen._patrol)
            until(lambda:not state()['police']['settings']['patrol_enabled'])
            parked={u['id']:u['position'] for u in state()['police']['units']}
            assert all(u['status']=='AVAILABLE' and not u['path'] for u in state()['police']['units'])
            ready_press(screen._medical_button)
            until(lambda:screen._medical)
            ready_press(screen._submit)
            until(lambda:len(state()['police']['reports'])==2)
            def only_assigned_moves():
                current=state()['police']
                report=current['reports'][1]
                assert not current['settings']['patrol_enabled']
                assert not any(u['status']=='PATROLLING' for u in current['units'])
                assert all(u['position']==parked[u['id']] for u in current['units'] if u['id']!=report['unit_id'])
                return report['status']=='RESOLVED'
            until(only_assigned_moves,40)
            until(lambda:not app.playing)
            joint=state()
            assert joint['events']['metrics']['civilians_rescued']==1
            assert joint['police']['reports'][1]['medical_status']=='RESOLVED'
            screenshot('police_live_reports.png')
            # Turn on the optional event generator at a deterministic 100% rate.
            for kind in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP):
                pygame.event.post(pygame.event.Event(kind,button=1,pos=(screen._probability.rect.right,screen._probability.rect.centery)))
            until(lambda:state()['police']['settings']['auto_probability']==1)
            ready_press(screen._auto)
            until(lambda:len(state()['police']['reports'])>=3)
            ready_press(screen._auto)
            until(lambda:not state()['police']['settings']['automatic_incidents'])
            pause()
            assert any(r['source']=='AUTOMATIC' for r in state()['police']['reports'])
            # A gate prevents police access, while the report remains visible.
            request('/simulation/disasters/gate',{'node_id':112,'intensity':8})
            app.refresh_state()
            until(lambda:bool(app.state.backend_sim.disasters.get('gates')))
            current=state()
            excluded={u['position'] for u in current['police']['units']}|{s['node_id'] for s in current['police']['stations']}|{r['node_id'] for r in current['police']['reports'] if r['status']!='RESOLVED'}
            target=next(n['id'] for n in current['graph']['nodes'] if n['id'] not in excluded and abs(n['row']-7)+abs(n['col']-7)<3)
            label=next(n['label'] for n in current['graph']['nodes'] if n['id']==target)
            if screen._medical:
                ready_press(screen._medical_button)
            type_node(screen,label)
            ready_press(screen._submit)
            until(lambda:any(r['node_id']==target and r['police_status']=='UNREACHABLE' for r in state()['police']['reports']))
            pause()
            ready_press(screen._plan)
            until(lambda:app.state.backend_sim.police.get('recommendations') is not None)
            plan=app.state.backend_sim.police['recommendations']
            assert plan['additions'] and not plan['stale']
            prior=state()['police']
            ready_press(screen._open_station)
            until(lambda:len(state()['police']['stations'])==4)
            constructed=state()['police']
            assert len(constructed['units'])==12
            assert [u['position'] for u in constructed['units'][:10]]==[u['position'] for u in prior['units']]
            ready_press(screen._benchmark)
            until(lambda:screen._compare is not None and not screen._compare_pending,30)
            assert not screen._compare.get('error')
            assert len(screen._compare['results'])==2
            assert all(r['reported']==screen._compare['incident_count'] and r['total_units']==12 for r in screen._compare['results'])
            screenshot('police_live_comparison.png')
            time.sleep(.2)
            print(json.dumps({'stations':4,'patrol_cars':12,'nearest_unit':expected,'physical_patrol_movement':True,
                              'native_report_resolved':True,'patrol_off_other_cars_parked':True,'joint_ambulance_rescue':True,'optional_automatic_reports':True,
                              'gate_unreachable_report':True,'station_construction_no_teleport':True,'matched_comparison':True}),flush=True)
        except Exception as exc:
            errors.append(exc)
        finally:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
    controller=threading.Thread(target=control,daemon=True)
    controller.start()
    app.run()
    controller.join(2)
    if errors:
        raise errors[0]
finally:
    if app:
        app.close()
    process.terminate()
    try:
        process.wait(5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(2)
