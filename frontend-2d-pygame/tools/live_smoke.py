"""Exercise the native client against an isolated live API (no visible window)."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import sys, subprocess, time, json, urllib.request
from pathlib import Path
frontend = Path(__file__).resolve().parents[1]
project = frontend.parent
sys.path.insert(0, str(frontend))
from app.application import Application
from app.state import ActiveScreen
import pygame
port = 8104
url = f'http://127.0.0.1:{port}'
flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
process = subprocess.Popen([sys.executable,'-m','uvicorn','backend.api.main:app','--host','127.0.0.1','--port',str(port)],
                           cwd=project, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
app = None
try:
    deadline = time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError('Test backend failed to start')
        try:
            with urllib.request.urlopen(url+'/',timeout=.5):
                break
        except Exception:
            time.sleep(.05)
    else:
        raise RuntimeError('Backend startup timed out')
    app = Application(url)
    def until(predicate, seconds=15):
        timeout = time.monotonic()+seconds
        while time.monotonic()<timeout:
            app._drain_updates()
            app._active_screen.update(.016)
            app.draw_frame()
            pygame.event.pump()
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError('Native integration operation timed out: '+app._status_msg)
    until(lambda: app.state.has_graph)
    app.async_step()
    until(lambda: app.state.backend_sim.step == 1 and not app.op_runner.is_running)
    app.navigate(ActiveScreen.ROUTE_LAB)
    route = app._active_screen
    route._inp_src.text, route._inp_dst.text = 'A1','O15'
    route._run_route()
    until(lambda: route._backend_route is not None and not route._pending)
    assert route._backend_validation['valid']
    app.async_optimization('start')
    until(lambda: app.state.backend_sim.optimization.get('status') == 'completed')
    app.async_export_metrics()
    until(lambda: app._status_msg.startswith('Metrics exported:'))
    export_path = Path(app._status_msg.removeprefix('Metrics exported: '))
    assert export_path.exists() and 'sim_id,step,metric,value' in export_path.read_text(encoding='utf-8')
    for screen in ActiveScreen:
        app.navigate(screen)
        app._active_screen.update(.016)
        app.draw_frame()
    app.navigate(ActiveScreen.CITY_MAP)
    app.draw_frame()
    (frontend / "artifacts").mkdir(exist_ok=True)
    pygame.image.save(app.window, str(frontend/'artifacts'/'live_city_map.png'))
    print(json.dumps({'connected':True,'step':app.state.backend_sim.step,'native_route_valid':True,
                      'optimization':app.state.backend_sim.optimization['status'],'export':str(export_path),'screens_rendered':9}))
    # Drive the real Pygame event loop: typed emergency, GO,
    # automatic response movement and return to depot. No direct dispatch shortcut.
    app.navigate(ActiveScreen.DASHBOARD)
    app._active_screen.update(.016)
    app.draw_frame()
    errors=[]
    def get_state():
        with urllib.request.urlopen(url+'/state',timeout=2) as response:
            return json.load(response)
    def control():
        try:
            import threading
            state=get_state()
            assert state['emergencies']==[]
            screen=app.screens[ActiveScreen.DASHBOARD]
            unit=state['fleet'][0]
            assert all('radius' not in u for u in state['fleet'])
            source=unit['depot']
            edge=next(e for e in state['graph']['edges'] if source in (e['node_a'],e['node_b']) and not e['blocked'])
            target=edge['node_b'] if edge['node_a']==source else edge['node_a']
            node=next(n for n in state['graph']['nodes'] if n['id']==target)
            label=node['label']
            with urllib.request.urlopen(url+f'/simulation/ambulance_routes/{target}',timeout=2) as response:
                expected=json.load(response)['best']['ambulance_id']
            pointer=screen._inp_node.rect.center
            for kind in [pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP]:
                pygame.event.post(pygame.event.Event(kind,button=1,pos=pointer))
            for char in label:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=ord(char.lower()),unicode=char,mod=0))
            for kind in [pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP]:
                pygame.event.post(pygame.event.Event(kind,button=1,pos=screen._go.rect.center))
            deadline=time.monotonic()+20
            captured=False
            while time.monotonic()<deadline:
                state=get_state()
                if state['emergencies']:
                    event=state['emergencies'][0]
                    assert event['ambulance_id']==expected
                    if not captured:
                        app._post_update(('callback',lambda: pygame.image.save(app.window,str(frontend/'artifacts'/'live_dispatch.png'))))
                        captured=True
                    if event['status']=='RESOLVED' and all(u['status']=='AVAILABLE' for u in state['fleet']):
                        break
                time.sleep(.04)
            else:
                raise AssertionError('Dispatch movement or return timed out')
            print(json.dumps({'typed_node':label,'nearest_unit':expected,'ambulance_radius_removed':True,
                              'resolved':True,'returned_to_depot':True,'no_preset_emergencies':True}),flush=True)
            # Isolate a node through the real API, then use native warning,
            # landing-site and helicopter controls through Pygame events.
            def post(path,payload=None):
                body=json.dumps(payload or {}).encode()
                req=urllib.request.Request(url+path,data=body,headers={'Content-Type':'application/json'},method='POST')
                with urllib.request.urlopen(req,timeout=5) as response:
                    return json.load(response)
            def press(button):
                for kind in [pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP]:
                    pygame.event.post(pygame.event.Event(kind,button=1,pos=button.rect.center))
            def wait_until(predicate,seconds=15):
                deadline=time.monotonic()+seconds
                while time.monotonic()<deadline:
                    if predicate():
                        return
                    time.sleep(.04)
                raise AssertionError('Air rescue event flow timed out: '+app._status_msg)
            wait_until(lambda:not app.playing)
            target=next(n['id'] for n in reversed(state['graph']['nodes']) if n['id'] not in state['medical_network']['centers'])
            label=next(n['label'] for n in state['graph']['nodes'] if n['id']==target)
            assert not screen._air.enabled
            for edge in state['graph']['edges']:
                if target in (edge['node_a'],edge['node_b']) and not edge['blocked']:
                    post(f"/simulation/block_road/{edge['node_a']}/{edge['node_b']}")
            app.refresh_state()
            wait_until(lambda:screen._modal=='network')
            app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/'live_coverage_alert.png'))))
            press(screen._close)
            wait_until(lambda:screen._modal is None)
            # Replace optional building pads; hospitals must never be bases.
            press(screen._landings)
            wait_until(lambda:screen._modal=='landings')
            pad=next(p for p in get_state()['air_rescue']['landing_sites'] if p['available'])
            center=pad['label']
            app._post_update(('callback',lambda:setattr(screen._landing_input,'text',center)))
            time.sleep(.15)
            press(screen._apply_landings)
            wait_until(lambda:get_state()['air_rescue']['custom_landings']==[pad['node_id']])
            press(screen._close)
            wait_until(lambda:screen._modal is None)
            press(screen._inp_node)
            for _ in range(10):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_BACKSPACE,unicode='',mod=0))
            for char in label:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=ord(char.lower()),unicode=char,mod=0))
            wait_until(lambda:screen._air.enabled)
            press(screen._air)
            wait_until(lambda:get_state()['air_rescue']['status']=='OUTBOUND')
            app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/'live_helicopter.png'))))
            wait_until(lambda:len(get_state()['emergencies'])==2 and get_state()['emergencies'][-1]['status']=='RESOLVED',seconds=55)
            wait_until(lambda:not app.playing)
            state=get_state()
            assert 0<state['air_rescue']['fuel']<state['air_rescue']['capacity']
            assert state['air_rescue']['landed_node'] in state['medical_network']['reachable_nodes']
            assert state['air_rescue']['landed_node'] not in state['medical_network']['centers']
            assert state['emergencies'][-1]['hospital_id'] in state['medical_network']['centers']
            assert state['emergencies'][-1]['ambulance_id'] is None
            press(screen._refuel)
            wait_until(lambda:get_state()['air_rescue']['fuel_pct']==100)
            print(json.dumps({'isolated_node':label,'air_button_unlocked':True,'native_landing_edit':True,
                              'air_rescue_resolved':True,'direct_hospital_delivery':state['emergencies'][-1]['hospital_id'],
                              'returned_to_building':state['air_rescue']['landed_label'],
                              'landing_fuel':state['air_rescue']['fuel'],'refueled':True}),flush=True)
            # Drive disaster controls by selecting the actual road link.
            app._post_update(('callback',lambda:app.navigate(ActiveScreen.GOD_MODE)))
            wait_until(lambda:app.state.active_screen==ActiveScreen.GOD_MODE)
            screen=app.screens[ActiveScreen.GOD_MODE]
            state=get_state()
            road=next(e for e in state['graph']['edges'] if abs(e['node_a']-e['node_b'])==1 and not e['blocked'])
            a,b=road['node_a'],road['node_b']
            nodes={n['id']:n for n in state['graph']['nodes']}
            pa,pb=screen._renderer.node_screen_pos(nodes[a]),screen._renderer.node_screen_pos(nodes[b])
            midpoint=tuple((v+w)//2 for v,w in zip(pa,pb))
            def press_at(point):
                for kind in [pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP]:
                    pygame.event.post(pygame.event.Event(kind,button=1,pos=point))
            def road_state():
                return next(e for e in get_state()['graph']['edges'] if (e['node_a'],e['node_b'])==(a,b))
            press_at(pa)
            time.sleep(.15)
            assert screen._selected_edge is None
            press_at(midpoint)
            wait_until(lambda:screen._selected_edge==(a,b) and screen._execute.enabled)
            press(screen._execute)
            wait_until(lambda:road_state()['blocked'])
            wait_until(lambda:not app.op_runner.is_running)
            press(screen._mode_btns[1])
            wait_until(lambda:screen._mode=='unblock')
            press_at(midpoint)
            wait_until(lambda:screen._selected_edge==(a,b) and screen._execute.enabled)
            press(screen._execute)
            wait_until(lambda:not road_state()['blocked'])
            wait_until(lambda:not app.op_runner.is_running)
            press(screen._mode_btns[2])
            wait_until(lambda:screen._mode=='gate')
            press_at(screen._renderer.node_screen_pos(nodes[112]))
            press(screen._level_btns[7])
            wait_until(lambda:screen._intensity==8 and screen._preview and screen._preview['intensity']==8)
            before=get_state()
            press(screen._execute)
            wait_until(lambda:len(get_state()['disasters']['gates'])==1)
            gate_state=get_state()
            assert gate_state['disasters']['gates'][0]['radius']==8
            assert gate_state['medical_network']['unreachable_nodes']==before['medical_network']['unreachable_nodes']
            normal=post('/simulation/route',{'src':112,'dst':0})
            ambulance=post('/simulation/route',{'src':112,'dst':0,'travel_mode':'ambulance'})
            assert normal['travel_mode']=='normal' and not normal['reachable'] and ambulance['reachable']
            app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/'live_gate_of_death.png'))))
            # The ordinary Route Lab form starts without ambulance privileges.
            app._post_update(('callback',lambda:app.navigate(ActiveScreen.ROUTE_LAB)))
            wait_until(lambda:app.state.active_screen==ActiveScreen.ROUTE_LAB)
            route_screen=app.screens[ActiveScreen.ROUTE_LAB]
            app._post_update(('callback',lambda:(setattr(route_screen._inp_src,'text','H8'),setattr(route_screen._inp_dst,'text','A1'))))
            wait_until(lambda:route_screen._inp_src.text=='H8' and route_screen._inp_dst.text=='A1')
            assert route_screen._travel_mode=='normal'
            press(route_screen._btn_run)
            wait_until(lambda:route_screen._backend_route is not None and not route_screen._pending)
            assert route_screen._backend_route['travel_mode']=='normal' and not route_screen._backend_route['reachable']
            assert not route_screen._renderer.route_paths
            app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/'live_normal_gate_route.png'))))
            press(route_screen._mode_button)
            wait_until(lambda:route_screen._travel_mode=='ambulance')
            press(route_screen._btn_run)
            wait_until(lambda:route_screen._backend_route is not None and not route_screen._pending)
            assert route_screen._backend_route['travel_mode']=='ambulance' and route_screen._backend_route['reachable']
            assert route_screen._backend_validation['valid']
            app._post_update(('callback',lambda:pygame.image.save(app.window,str(frontend/'artifacts'/'live_ambulance_gate_route.png'))))
            app._post_update(('callback',lambda:app.navigate(ActiveScreen.GOD_MODE)))
            wait_until(lambda:app.state.active_screen==ActiveScreen.GOD_MODE)
            wait_until(lambda:not app.op_runner.is_running and screen._clear.enabled)
            press(screen._clear)
            wait_until(lambda:not get_state()['disasters']['gates'])
            assert get_state()['disasters']['fully_blocked_roads']==before['disasters']['fully_blocked_roads']
            print(json.dumps({'selected_link':[a,b],'native_block_unblock':True,'gate_level':8,'radius':8,
                              'normal_traffic_prohibited':True,'ambulance_access_preserved':True,
                              'coverage_preserved':True,'native_default_route_prohibited':True,
                              'native_explicit_ambulance_route_allowed':True,'gates_cleared':True}),flush=True)
            # Catch one medical center and the current helipad, then use the
            # actual assistant button. This flight must finish with an outage
            # still present, rather than keeping playback running indefinitely.
            wait_until(lambda:not app.op_runner.is_running)
            initial=get_state()
            home=initial['air_rescue']['landed_node']
            post('/simulation/disasters/gate',{'node_id':initial['fleet'][0]['depot'],'intensity':1})
            caught=post('/simulation/disasters/gate',{'node_id':home,'intensity':1})['state']
            assert caught['fleet'][0]['status']=='OUT_OF_SERVICE'
            assert caught['air_rescue']['relocation']['can_relocate']
            app.refresh_state()
            wait_until(lambda:screen._relocate.enabled)
            fuel=caught['air_rescue']['fuel']
            press(screen._relocate)
            wait_until(lambda:get_state()['air_rescue']['landed_node']!=home)
            wait_until(lambda:get_state()['air_rescue']['status']=='READY')
            wait_until(lambda:not app.playing)
            final=get_state()
            assert final['air_rescue']['fuel']<fuel
            assert final['air_rescue']['landed_node'] in final['air_rescue']['landing_nodes']
            assert final['fleet'][0]['status']=='OUT_OF_SERVICE'
            assert any('Assistant required' in n['message'] for n in caught['medical_network']['notifications'])
            print(json.dumps({'native_assistant_relocation':True,'safe_pad':final['air_rescue']['landed_label'],
                              'fuel_consumed':fuel-final['air_rescue']['fuel'],'exposed_ambulance_disabled':True,
                              'playback_stops_after_relocation':True}),flush=True)
        except Exception as error:
            errors.append(error)
        finally:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
    import threading
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
