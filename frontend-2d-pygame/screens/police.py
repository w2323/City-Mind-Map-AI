"""Police operations: physical patrol cars, reports, station planning and comparison."""
import pygame
from screens.base_screen import BaseScreen
from screens.dispatch import text,card
from app.theme import Colors,Fonts
from components.buttons import Button,TextInput,Slider
from visualization.graph_renderer import GraphRenderer


class PoliceScreen(BaseScreen):
    def __init__(self,app,rect):
        super().__init__(app,rect)
        self._right=pygame.Rect(rect.right-352,rect.y+22,330,rect.height-44)
        self._map=pygame.Rect(rect.x+22,rect.y+116,rect.width-396,rect.height-350)
        self._table=pygame.Rect(self._map.x,self._map.bottom+14,self._map.width,rect.bottom-self._map.bottom-34)
        self._renderer=GraphRenderer(self._map.inflate(-20,-20))
        x,y,w=self._right.x+16,self._right.y,self._right.width-32
        self._node=TextInput((x,y+94,w,36),placeholder='Report sector, e.g. C4',max_len=10,font_size=15)
        self._kind='THEFT'
        self._severity=1
        self._medical=False
        self._selected=None
        self._report_id=None
        self._tab='reports'
        self._scroll=0
        self._positions={}
        self._identity=''
        self._compare=None
        self._modal=False
        self._compare_pending=False
        self._kind_button=Button('THEFT',(x,y+144,w,30),font_size=12)
        self._severity_buttons=[Button(str(i),(x+(i-1)*102,y+204,94,30),font_size=12) for i in (1,2,3)]
        self._medical_button=Button('MEDICAL ASSISTANCE: OFF',(x,y+248,w,30),font_size=11)
        self._submit=Button('REPORT & DISPATCH',(x,y+290,w,38),style='primary',font_size=12)
        self._patrol=Button('PATROLS: ON',(x,y+366,w,30),font_size=11)
        self._auto=Button('AUTOMATIC REPORTS: OFF',(x,y+405,w,30),font_size=11)
        self._probability=Slider((x+4,y+473,220,16),15,0,100)
        self._plan=Button('PLAN STATION LOCATIONS',(x,y+530,w,30),font_size=11)
        self._benchmark=Button('COMPARE DEPLOYMENT STRATEGIES',(x,y+570,w,30),font_size=10)
        self._open_station=Button('OPEN RECOMMENDED STATION',(x,y+616,w,32),font_size=10)
        self._air=Button('REQUEST MEDICAL HELICOPTER',(x,y+656,w,32),style='warning',font_size=10)
        self._tabs=[Button(label,(self._table.x+14+i*108,self._table.y+12,100,28),font_size=10) for i,label in enumerate(('REPORTS','FLEET','STATIONS'))]
        self._rows=[]
        self._modal_rect=pygame.Rect(rect.centerx-390,rect.centery-240,780,480)
        m=self._modal_rect
        self._close=Button('CLOSE',(m.right-100,m.y+20,78,30),font_size=11)
        self._seed=TextInput((m.x+24,m.bottom-63,170,34),placeholder='Optional replay seed',max_len=10,font_size=12)
        self._rerun=Button('RUN COMPARISON',(m.x+208,m.bottom-63,180,34),style='primary',font_size=11)

    @property
    def police(self):
        return self.sim.police

    def on_enter(self):
        self._renderer.fit_to_view(self.graph.grid_rows,self.graph.grid_cols)
        self.on_state_updated()

    def on_state_updated(self):
        if self._identity!=self.sim.sim_id:
            self._identity=self.sim.sim_id
            self._positions.clear()
            self._selected=self._report_id=None
            self._modal=False
            self._compare=None
        if not self._probability.dragging:
            self._probability.value=self.police.get('settings',{}).get('auto_probability',.15)*100

    def _act(self,action,payload=None):
        if hasattr(self.app,'async_police'):
            self.app.async_police(action,payload)

    def _report(self):
        if not self._node.text.strip():
            self.app.show_status('Select or enter a report sector.',level='warning')
            return
        self._act('report',{'node':self._node.text.strip(),'kind':self._kind,'severity':self._severity,
                            'medical_required':self._medical or self._kind=='INJURY'})

    def _run_compare(self):
        payload={}
        if self._seed.text:
            try:
                payload={'seed':int(self._seed.text)}
            except ValueError:
                self.app.show_status('Comparison seed must be a nonnegative integer.',level='warning')
                return
        if not hasattr(self.app,'async_police'):
            return
        self._compare_pending=True
        self._modal=True
        identity=self.sim.sim_id
        def done(data):
            self._compare_pending=False
            if identity==self.sim.sim_id:
                self._compare=data
        self.app.async_police('compare',payload,on_compare=done)

    def handle_event(self,event):
        if self._modal:
            self._seed.handle_event(event)
            if self._close.handle_event(event) or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                self._modal=False
            if self._rerun.handle_event(event):
                self._run_compare()
            return
        if event.type==pygame.KEYDOWN and event.key==pygame.K_RETURN and self._node.focused:
            self._report()
        self._node.handle_event(event)
        if self._renderer.handle_event(event):
            return
        if self._kind_button.handle_event(event):
            types=self.police.get('incident_types',['THEFT','VANDALISM','DISTURBANCE','INJURY'])
            self._kind=types[(types.index(self._kind)+1)%len(types)]
        for i,button in enumerate(self._severity_buttons,1):
            if button.handle_event(event):
                self._severity=i
        if self._medical_button.handle_event(event):
            self._medical=not self._medical
        if self._submit.handle_event(event):
            self._report()
        settings=self.police.get('settings',{})
        if self._patrol.handle_event(event):
            self._act('settings',{'patrol_enabled':not settings.get('patrol_enabled',True)})
        if self._auto.handle_event(event):
            self._act('settings',{'automatic_incidents':not settings.get('automatic_incidents',False)})
        if self._probability.handle_event(event):
            self._act('settings',{'auto_probability':self._probability.value/100})
        if self._plan.handle_event(event):
            self._act('plan')
        if self._benchmark.handle_event(event):
            self._run_compare()
        if self._open_station.handle_event(event):
            choices=(self.police.get('recommendations') or {}).get('additions',[])
            if choices:
                self._act('station',{'node':choices[0]['label']})
        if self._air.handle_event(event):
            if self.sim.air_rescue.get('relocation_required'):
                self.app.async_rescue_action('relocate')
            else:
                self._act('medical',{'report_id':self._report_id})
        for button,name in zip(self._tabs,('reports','fleet','stations')):
            if button.handle_event(event):
                self._tab=name
                self._scroll=0
        if event.type==pygame.MOUSEWHEEL and self._table.collidepoint(getattr(event,'pos',pygame.mouse.get_pos())):
            self._scroll=max(0,self._scroll-event.y*34)
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self._renderer.viewport.collidepoint(event.pos):
                node=self._renderer.hit_test_node(*event.pos,self.graph.nodes)
                if node is not None:
                    self._selected=node
                    self._node.text=self.graph.nodes[node].get('label','')
                    self._renderer.selected_node=node
                    self._report_id=next((r['id'] for r in reversed(self.police.get('reports',[])) if r['node_id']==node),None)
            for row,report in self._rows:
                if row.collidepoint(event.pos):
                    self._report_id=report['id']
                    self._selected=report['node_id']
                    self._node.text=report['label']
                    self._renderer.selected_node=report['node_id']

    def update(self,dt):
        self._node.update(dt)
        self._seed.update(dt)
        units=[]
        for unit in self.police.get('units',[])+self.sim.fleet:
            n=self.graph.nodes.get(unit['position'])
            if n:
                target=(n['row'],n['col'])
                previous=self._positions.get(unit['id'],target)
                point=tuple(a+(b-a)*min(1,dt*10) for a,b in zip(previous,target))
                self._positions[unit['id']]=point
                units.append({**unit,'render_position':point})
        self._renderer.police_service={**self.police,'units':units}
        self._renderer.fleet=[{**u,'render_position':self._positions.get(u['id'])} for u in self.sim.fleet]
        self._renderer.air_rescue=self.sim.air_rescue
        self._renderer.gate_zones=self.sim.disasters.get('gates',[])
        self._renderer.selected_node=self._selected

    def draw(self,surface):
        pygame.draw.rect(surface,Colors.BG_DEEP,self.rect)
        summary=self.police.get('summary',{})
        kpis=[('READY CARS',f"{summary.get('available',0)} / {summary.get('total_units',0)}",'Patrol and free return trips can respond'),
              ('UNRESOLVED',summary.get('unresolved',0),f"{summary.get('queued',0)} queued / {summary.get('unreachable',0)} unreachable"),
              ('RESPONSE STEPS',summary.get('mean_response_steps') if summary.get('mean_response_steps') is not None else '--','Mean of arrivals; unresolved shown separately'),
              ('POLICE HANDLED',summary.get('police_handled',0),f"{summary.get('medical_pending',0)} medical tasks pending")]
        width=(self._map.width-36)//4
        for i,(title,value,caption) in enumerate(kpis):
            x=self._map.x+i*(width+12)
            card(surface,pygame.Rect(x,self.rect.y+22,width,78))
            text(surface,title,x+12,self.rect.y+34,10,Colors.TEXT_MUTED,True)
            text(surface,value,x+12,self.rect.y+49,23,Colors.POLICE,True)
            text(surface,caption,x+12,self.rect.y+83,8,Colors.TEXT_MUTED)
        card(surface,self._map)
        routes=[{'path':u['path'],'color':Colors.POLICE if u['status']=='RESPONDING' else Colors.ACCENT_CYAN} for u in self.police.get('units',[]) if len(u.get('path',[]))>1]
        routes += [{'path':u['path'],'color':Colors.AMBULANCE} for u in self.sim.fleet if len(u.get('path',[]))>1]
        self._renderer.draw(surface,self.graph.nodes,self.graph.edges,self.sim.risk_predictions,route_paths=routes)
        self._draw_table(surface)
        self._draw_controls(surface)
        if self._modal:
            self._draw_comparison(surface)

    def _draw_controls(self,surface):
        r=self._right
        card(surface,r)
        x,y=r.x+16,r.y
        text(surface,'Police operations',x,y+18,21,bold=True)
        text(surface,'Police + ambulance routes shown together.',x,y+49,11,Colors.TEXT_MUTED)
        text(surface,'Report location',x,y+77,11,Colors.TEXT_SECONDARY)
        self._node.draw(surface)
        self._kind_button.label='TYPE: '+self._kind.replace('_',' ')
        self._kind_button.draw(surface)
        text(surface,'Severity:  1 low / 2 medium / 3 urgent',x,y+184,11,Colors.TEXT_SECONDARY)
        for i,button in enumerate(self._severity_buttons,1):
            button.style='primary' if i==self._severity else 'neutral'
            button.draw(surface)
        self._medical_button.label='MEDICAL ASSISTANCE: '+('ON' if self._medical or self._kind=='INJURY' else 'OFF')
        self._medical_button.enabled=self._kind!='INJURY'
        self._medical_button.draw(surface)
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        ready=self.state.is_connected and not busy
        self._submit.enabled=ready and not self.sim.is_complete
        self._submit.draw(surface)
        text(surface,'PATROL & INCIDENT SETTINGS',x,y+345,10,Colors.TEXT_MUTED,True)
        settings=self.police.get('settings',{})
        self._patrol.label='PATROLS: '+('ON' if settings.get('patrol_enabled',True) else 'OFF')
        self._auto.label='AUTOMATIC REPORTS: '+('ON' if settings.get('automatic_incidents',False) else 'OFF')
        for button in (self._patrol,self._auto):
            button.enabled=ready
            button.draw(surface)
        text(surface,'Automatic report chance per simulation step',x,y+451,10,Colors.TEXT_MUTED)
        self._probability.enabled=ready
        self._probability.draw(surface,Colors.POLICE)
        text(surface,f'{self._probability.value:g}%',x+240,y+473,12,Colors.POLICE,True)
        intervals=self.police.get('patrol_policy',{}).get('revisit_steps',{})
        hint=(f"High: continuous / Medium: {intervals.get('MEDIUM',8)} steps / Low: {intervals.get('LOW',24)} steps" if settings.get('patrol_enabled',True)
              else 'Patrols OFF: idle cars park; reports still dispatch.')
        text(surface,hint,x,y+503,9,Colors.TEXT_MUTED)
        hotspots=self.police.get('patrol_policy',{}).get('hotspots',[])
        text(surface,f"High areas: {sum(bool(z['assigned_units']) for z in hotspots)} assigned / {sum(bool(z['present_units']) for z in hotspots)} present / {len(hotspots)} total",x,y+518,9,Colors.POLICE)
        self._plan.enabled=ready
        self._benchmark.enabled=self.state.is_connected and not self._compare_pending
        self._plan.draw(surface)
        self._benchmark.draw(surface)
        plan=self.police.get('recommendations') or {}
        self._open_station.enabled=ready and bool(plan.get('additions')) and not plan.get('stale',True)
        self._open_station.draw(surface)
        report=next((r for r in self.police.get('reports',[]) if r['id']==self._report_id),None)
        self._air.enabled=ready and report is not None and report['medical_status']=='HELICOPTER_REQUIRED' and self.sim.air_rescue.get('status')=='READY'
        self._air.label='REQUEST MEDICAL HELICOPTER'
        if self.sim.air_rescue.get('relocation_required'):
            self._air.label='RELOCATE HELICOPTER'
            self._air.enabled=ready and self.sim.air_rescue.get('relocation',{}).get('can_relocate',False)
        self._air.draw(surface)
        if report:
            text(surface,f"{report['id']}: {report['status'].replace('_',' ')}",x,y+707,11,Colors.POLICE)
            text(surface,'Medical: '+report['medical_status'].replace('_',' '),x,y+728,10,Colors.TEXT_MUTED)
        else:
            text(surface,'Select a report row to inspect its medical task.',x,y+707,10,Colors.TEXT_MUTED)
        text(surface,'Police cannot cross Gate of Death restrictions.',x,y+754,10,Colors.ACCENT_AMBER)

    def _draw_table(self,surface):
        card(surface,self._table)
        for button,name in zip(self._tabs,('reports','fleet','stations')):
            button.style='primary' if self._tab==name else 'neutral'
            button.draw(surface)
        content=pygame.Rect(self._table.x+16,self._table.y+54,self._table.width-32,self._table.height-64)
        self._rows=[]
        lines=[]
        if self._tab=='reports':
            for r in reversed(self.police.get('reports',[])):
                lines.append((f"{r['id']}  {r['label']}  {r['kind']} / severity {r['severity']}  |  {r['status'].replace('_',' ')}",
                              f"{r['unit_id'] or 'Unassigned'}  |  {r['reason']}  |  Medical: {r['medical_status']} / {r.get('medical_emergency_id') or 'none'}",r))
        elif self._tab=='fleet':
            lines=[(f"{u['id']} / {u['station_id']}  |  {u['status']}  |  Now {u['position_label']}",
                    f"Assignment: {u.get('report_id') or ('To '+u['target_label'] if u.get('target_label') else 'Parked / awaiting report')}  |  Station reserve: {'yes' if u['reserve'] else 'no'}",None) for u in self.police.get('units',[])]
            lines += [(f"{u['id']} / MEDICAL  |  {u['status']}  |  Now {u['position_label']}",'Assignment: '+(u.get('emergency_id') or 'Awaiting medical request'),None) for u in self.sim.fleet]
        else:
            lines=[(f"{s['id']} at {s['label']}",f"{sum(u['station_id']==s['id'] for u in self.police.get('units',[]))} patrol cars based here",None) for s in self.police.get('stations',[])]
            lines += [(f"Financial sector {b['label']} / "+(f"{b['station_id']} at {b['station_label']} / {b['grid_blocks']} units {b.get('police_direction') or ''}" if b['protected'] else 'NO NEARBY ROAD ACCESS'),
                       'Maximum three sector units plus a permitted road route',None) for b in self.police.get('banks',[])]
            plan=self.police.get('recommendations') or {}
            lines += [(f"Suggested: {s['label']} / {s['gain']} unserved sectors",'Recalculate plan before construction' if plan.get('stale') else 'First recommendation can be opened with the station button',None) for s in plan.get('additions',[])]
        self._scroll=min(self._scroll,max(0,len(lines)*45-content.height))
        clip=surface.get_clip()
        surface.set_clip(content.clip(clip))
        if not lines:
            text(surface,'No reports yet. Enter a sector or click one on the map.',content.x,content.y+10,13,Colors.TEXT_MUTED)
        for i,(title,caption,report) in enumerate(lines):
            row=pygame.Rect(content.x,content.y+i*45-self._scroll,content.width,42)
            if report and row.colliderect(content):
                self._rows.append((row.clip(content),report))
            text(surface,title,row.x,row.y+3,12,Colors.POLICE if report and report['id']==self._report_id else Colors.TEXT_PRIMARY,True)
            text(surface,caption,row.x,row.y+23,10,Colors.TEXT_MUTED)
        surface.set_clip(clip)

    def _draw_comparison(self,surface):
        shade=pygame.Surface(self.rect.size,pygame.SRCALPHA)
        shade.fill((15,25,42,145))
        surface.blit(shade,self.rect.topleft)
        r=self._modal_rect
        card(surface,r)
        self._close.draw(surface)
        text(surface,'Compare police deployments',r.x+24,r.y+24,22,bold=True)
        text(surface,'Same incident sequence, road restrictions and number of vehicles.',r.x+24,r.y+72,13,Colors.TEXT_SECONDARY)
        if self._compare_pending:
            text(surface,'Running isolated simulations...',r.x+24,r.y+120,16,Colors.POLICE)
        elif self._compare and self._compare.get('error'):
            text(surface,self._compare['error'][:90],r.x+24,r.y+122,12,Colors.RED)
        elif self._compare:
            data=self._compare
            text(surface,f"Seed {data['seed']} / {data['steps']} steps / {data['incident_count']} identical reports",r.x+24,r.y+110,13,Colors.POLICE,True)
            columns=[r.x+24,r.x+330,r.x+535]
            text(surface,'MEASURE',columns[0],r.y+156,11,Colors.TEXT_MUTED,True)
            text(surface,'UNIFORM',columns[1],r.y+156,11,Colors.TEXT_MUTED,True)
            text(surface,'RISK WEIGHTED',columns[2],r.y+156,11,Colors.TEXT_MUTED,True)
            fields=[('Reports','reported'),('Police tasks handled','police_handled'),('Unresolved reports','unresolved'),('Mean response steps','mean_response_steps'),('Worst response steps','worst_response_steps'),('Road coverage %','coverage_pct')]
            for i,(label,key) in enumerate(fields):
                y=r.y+191+i*30
                text(surface,label,columns[0],y,13)
                for col,result in zip(columns[1:],data['results']):
                    text(surface,result.get(key) if result.get(key) is not None else '--',col,y,13,Colors.POLICE,True)
            text(surface,'Mean response includes arrivals only; read it alongside unresolved reports.',r.x+24,r.bottom-100,11,Colors.TEXT_MUTED)
        self._seed.draw(surface)
        self._rerun.enabled=not self._compare_pending
        self._rerun.draw(surface)
