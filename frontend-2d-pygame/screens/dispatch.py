"""Map-first dispatch workspace: explicit emergencies and per-depot coverage."""
import pygame
from screens.base_screen import BaseScreen
from app.theme import Colors, Fonts
from components.buttons import Button, TextInput, Slider
from visualization.graph_renderer import GraphRenderer
from presentation.sectors import sector_label,sector_text

UNIT_COLORS = [(38,100,220),(23,154,119),(185,123,42),(126,86,192)]


def text(surface, value, x, y, size=13, color=None, bold=False):
    font = Fonts.bold(size) if bold else Fonts.sans(size)
    surface.blit(font.render(str(value),True,color or Colors.TEXT_PRIMARY),(x,y))


def card(surface,rect):
    pygame.draw.rect(surface,(224,231,240),rect.move(0,2),border_radius=12)
    pygame.draw.rect(surface,(255,255,255),rect,border_radius=12)
    pygame.draw.rect(surface,Colors.BORDER,rect,1,border_radius=12)


class DispatchScreen(BaseScreen):
    def __init__(self,app,rect):
        super().__init__(app,rect)
        self._right = pygame.Rect(rect.right-352,rect.y+22,330,rect.height-44)
        self._map_card = pygame.Rect(rect.x+22,rect.y+116,rect.width-396,rect.height-194)
        viewport = pygame.Rect(self._map_card.x+14,self._map_card.y+53,self._map_card.width-28,self._map_card.height-76)
        self._renderer=GraphRenderer(viewport)
        self._inp_node = TextInput((self._right.x+18,self._right.y+96,210,42),placeholder='e.g. C4',max_len=10,font_size=17)
        self._go=Button('GO',(self._right.x+238,self._right.y+96,74,42),style='primary',font_size=14)
        self._restart=Button('NEW CITY',(self._map_card.right-118,self._map_card.y+15,96,27),font_size=10)
        self._fit=Button('FIT',(self._map_card.right-174,self._map_card.y+15,48,27),font_size=10)
        self._events=Button('CITY EVENTS: ON',(self._map_card.right-344,self._map_card.y+15,160,27),font_size=10)
        self._unit_positions={}
        self._air_position=None
        self._selected=None
        self._fitted=False
        self._fleet_scroll=0
        self._modal=None
        self._modal_scroll=0
        self._seen_notice=0
        self._seen_sim=''
        self._air=Button('HELICOPTER RESCUE',(self._right.x+18,self._right.y+148,294,34),style='warning',enabled=False,font_size=12)
        self._landings=Button('LANDING SITES',(self._right.x+18,self._right.y+350,175,30),font_size=11)
        self._relocate=Button('RELOCATE HELICOPTER',(self._right.x+18,self._right.y+386,294,28),style='warning',font_size=11)
        self._refuel=Button('REFUEL',(self._right.x+204,self._right.y+350,108,30),font_size=11)
        self._alerts=Button('COVERAGE & ALERTS',(self._map_card.x+12,self._map_card.bottom+21,178,30),font_size=11)
        self._modal_rect=pygame.Rect(rect.centerx-410,rect.centery-296,820,592)
        mr=self._modal_rect
        self._close=Button('CLOSE',(mr.right-100,mr.y+20,78,30),font_size=11)
        self._landing_input=TextInput((mr.x+24,mr.y+136,615,40),placeholder='e.g. A1, H8, O15',max_len=100,font_size=15)
        self._apply_landings=Button('APPLY',(mr.right-158,mr.y+136,134,40),style='primary',font_size=12)
        self._build_center=Button('OPEN RECOMMENDED CENTER',(mr.x+24,mr.bottom-57,300,34),style='primary',font_size=12)
        self._event_all=Button('PAUSE ALL AUTOMATIC EVENTS',(mr.x+24,mr.y+80,350,34),font_size=11)
        self._event_channels=[('medical_enabled','MEDICAL'),('crime_enabled','CRIME'),('roads_enabled','ROADS')]
        self._event_buttons=[Button(name,(mr.x+24+i*258,mr.y+138,246,34),font_size=11) for i,(_,name) in enumerate(self._event_channels)]
        self._event_rates={key:Slider((mr.x+32,mr.y+225+i*84,610,16),0,0,100) for i,key in enumerate(('medical_probability','crime_probability','road_probability'))}

    def on_enter(self):
        if not self._fitted:
            self._renderer.fit_to_view(self.graph.grid_rows,self.graph.grid_cols)
            self._fitted=True

    def on_state_updated(self):
        for key,slider in self._event_rates.items():
            if not slider.dragging:
                slider.value=100*self.sim.city_events.get('settings',{}).get(key,0)
        if self._seen_sim != self.sim.sim_id:
            self._seen_sim=self.sim.sim_id
            self._seen_notice=0
            self._modal=None
            self._unit_positions.clear()
            self._air_position=None
        notices=self.sim.medical_network.get('notifications',[])
        fresh=[n for n in notices if n['id']>self._seen_notice]
        if any(n['message'].startswith('Medical centers cut off') for n in fresh):
            self._modal='network'
            self._modal_scroll=0
        if notices:
            self._seen_notice=notices[-1]['id']
        if self._selected not in self.graph.nodes:
            self._selected=None

    def _dispatch(self):
        label=self._inp_node.text.strip()
        if not label:
            self.app.show_status('Enter an emergency sector, or click a location on the map.',level='warning')
            return
        if hasattr(self.app,'async_dispatch'):
            self.app.async_dispatch(label)

    def handle_event(self,event):
        if self._modal:
            if self._close.handle_event(event) or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                self._modal=None
            if event.type==pygame.MOUSEWHEEL:
                self._modal_scroll=max(0,self._modal_scroll-event.y*30)
            if self._modal=='events':
                if self._event_all.handle_event(event):
                    self.app.async_city_events({'enabled':not self.sim.city_events.get('enabled',False)})
                for button,(key,_) in zip(self._event_buttons,self._event_channels):
                    if button.handle_event(event):
                        self.app.async_city_events({key:not self.sim.city_events.get('settings',{}).get(key,False)})
                for key,slider in self._event_rates.items():
                    if slider.handle_event(event):
                        self.app.async_city_events({key:slider.value/100})
                return
            if self._modal=='landings':
                self._landing_input.handle_event(event)
                if self._apply_landings.handle_event(event):
                    labels=[s.strip() for s in self._landing_input.text.split(',') if s.strip()]
                    self.app.async_rescue_action('landings',labels)
            elif self._modal=='network' and self._build_center.handle_event(event):
                choices=self.sim.medical_network.get('recommendations',[])
                if choices:
                    self.app.async_rescue_action('center',choices[0]['label'])
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and self._inp_node.focused:
            self._dispatch()
        self._inp_node.handle_event(event)
        if self._events.handle_event(event):
            self.on_state_updated()
            self._modal='events'
        if self._go.handle_event(event):
            self._dispatch()
        if self._air.handle_event(event):
            self.app.async_rescue_action('dispatch',self._inp_node.text.strip())
        if self._landings.handle_event(event):
            self._modal='landings'
            self._modal_scroll=0
            self._landing_input.text=', '.join(self.graph.nodes[n]['label'] for n in self.sim.air_rescue.get('custom_landings',[]) if n in self.graph.nodes)
        if self._relocate.handle_event(event):
            self.app.async_rescue_action('relocate')
        if self._refuel.handle_event(event):
            self.app.async_rescue_action('refuel')
        if self._alerts.handle_event(event):
            self._modal='network'
            self._modal_scroll=0
        if self._restart.handle_event(event):
            self.app.async_restart()
        if self._fit.handle_event(event):
            self._renderer.fit_to_view(self.graph.grid_rows,self.graph.grid_cols)
        if self._renderer.handle_event(event):
            return
        if event.type==pygame.MOUSEWHEEL and self._fleet_rect.collidepoint(getattr(event,'pos',pygame.mouse.get_pos())):
            self._fleet_scroll=max(0,min(self._fleet_scroll-event.y*34,max(0,len(self.sim.fleet)*107-(self._fleet_rect.height-77))))
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self._renderer.viewport.collidepoint(event.pos):
            node_id=self._renderer.hit_test_node(*event.pos,self.graph.nodes)
            if node_id is not None:
                node=self.graph.nodes[node_id]
                self._selected=node_id
                self._renderer.selected_node=node_id
                self._inp_node.text=node.get('label') or f"{chr(65+node['col'])}{node['row']+1}"
                self.state.selected_node=node_id

    def update(self,dt):
        self._inp_node.update(dt)
        self._landing_input.update(dt)
        point=self.sim.air_rescue.get('position')
        if point:
            previous=self._air_position or point
            self._air_position=tuple(a+(b-a)*min(1,dt*10) for a,b in zip(previous,point))
        for unit in self.sim.fleet:
            node=self.graph.nodes.get(unit['position'])
            if node:
                target=(float(node['row']),float(node['col']))
                previous=self._unit_positions.get(unit['id'],target)
                blend=min(1,dt*10)
                self._unit_positions[unit['id']]=tuple(a+(b-a)*blend for a,b in zip(previous,target))
        if self.graph.nodes and not self._fitted:
            self.on_enter()

    @property
    def _fleet_rect(self):
        return pygame.Rect(self._right.x,self._right.y+424,self._right.width,self._right.height-424)

    def draw(self,surface):
        pygame.draw.rect(surface,Colors.BG_DEEP,self.rect)
        summary=self.sim.dispatch_summary
        metrics=[('AVAILABLE UNITS',f"{summary.get('available',0)} / {summary.get('total',len(self.sim.fleet))}",'Ready for dispatch',Colors.ACCENT_CYAN),
                 ('ACTIVE EMERGENCIES',summary.get('active',0),f"Manual + automatic / {summary.get('queued',0)} queued",Colors.RED),
                 ('ROAD COVERAGE',f"{self.sim.medical_network.get('coverage_pct',0):.1f}%",'Sectors reachable from centers',Colors.GREEN),
                 ('RESOLVED',summary.get('resolved',0),'Ambulances return to depot',Colors.PURPLE)]
        width=(self._map_card.width-36)//4
        for index,(label,value,caption,color) in enumerate(metrics):
            x=self._map_card.x+index*(width+12)
            card(surface,pygame.Rect(x,self.rect.y+22,width,78))
            text(surface,label,x+16,self.rect.y+34,10,Colors.TEXT_MUTED,True)
            text(surface,value,x+16,self.rect.y+47,24,color,True)
            text(surface,caption,x+16,self.rect.y+83,10,Colors.TEXT_MUTED)
        card(surface,self._map_card)
        text(surface,'City coverage & live response',self._map_card.x+20,self._map_card.y+17,16,bold=True)
        self._events.label='CITY EVENTS: '+('ON' if self.sim.city_events.get('enabled') else 'OFF')
        for button in (self._events,self._fit,self._restart):
            button.draw(surface)
        fleet=[]
        for unit in self.sim.fleet:
            fleet.append({**unit,'render_position':self._unit_positions.get(unit['id'])})
        self._renderer.fleet=fleet
        self._renderer.air_rescue={**self.sim.air_rescue,'render_position':self._air_position}
        self._renderer.unserved_nodes=self.sim.medical_network.get('unreachable_nodes',[])
        self._renderer.gate_zones=self.sim.disasters.get('gates',[])
        self._renderer.police_service=self.sim.police
        routes=[{'path':u['path'],'color':UNIT_COLORS[i%len(UNIT_COLORS)]} for i,u in enumerate(fleet) if len(u.get('path',[]))>1]
        self._renderer.draw(surface,self.graph.nodes,self.graph.edges,self.sim.risk_predictions,
                            civilian_nodes=[e['node_id'] for e in self.sim.emergencies if e['status'] not in ('RESOLVED','ABORTED')],route_paths=routes)
        if not self.graph.nodes:
            text(surface,'Connecting to the Python simulation...',self._renderer.viewport.x+30,self._renderer.viewport.centery,17,Colors.TEXT_MUTED)
        # Grid references remain legible even when no emergency has been entered.
        text(surface,'Click a sector to select it.  Wheel to zoom.  Right-drag to pan.',self._map_card.x+18,self._map_card.bottom-19,10,Colors.TEXT_MUTED)
        self._draw_emergency(surface)
        self._draw_fleet_panel(surface)
        self._draw_air_panel(surface)
        strip=pygame.Rect(self._map_card.x,self._map_card.bottom+14,self._map_card.width,44)
        card(surface,strip)
        self._alerts.draw(surface)
        if self._selected in self.graph.nodes:
            node=self.graph.nodes[self._selected]
            label=node.get('label') or self._inp_node.text
            message=f"Sector {label}  |  {sector_label(node.get('node_type','EMPTY'))}  |  {'Road served' if self._selected in self.sim.medical_network.get('reachable_nodes',[]) else 'Air rescue required'}"
        else:
            missing=len(self.sim.medical_network.get('unreachable_nodes',[]))
            message=f'{missing} sectors cut off from medical centers' if missing else 'All sectors have medical road access. Enter a sector to dispatch.'
        text(surface,message,strip.x+204,strip.y+14,12,Colors.TEXT_SECONDARY)
        if self._modal:
            self._draw_modal(surface)

    def _draw_emergency(self,surface):
        rect=pygame.Rect(self._right.x,self._right.y,self._right.width,224)
        card(surface,rect)
        text(surface,'NEW EMERGENCY',rect.x+18,rect.y+17,10,Colors.RED,True)
        text(surface,'Where is help needed?',rect.x+18,rect.y+35,20,bold=True)
        text(surface,'Emergency sector',rect.x+18,rect.y+75,12,Colors.TEXT_SECONDARY)
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        self._go.enabled=self.state.is_connected and not self.sim.is_complete and not busy
        self._inp_node.draw(surface)
        self._go.draw(surface)
        label=self._inp_node.text.strip().upper()
        target=next((n['id'] for n in self.graph.nodes.values() if n.get('label')==label),None)
        requires_air=target is not None and target not in self.sim.dispatch_summary.get('reachable_nodes',[])
        self._air.enabled=(self.state.is_connected and not self.sim.is_complete and not busy and requires_air
                           and self.sim.air_rescue.get('status')=='READY'
                           and not any(e['node_id']==target and e['status'] not in ('RESOLVED','ABORTED') for e in self.sim.emergencies))
        self._air.draw(surface)
        caption='No road access. Helicopter depot required.' if requires_air else 'Helicopter unlocks only when road access is lost.'
        text(surface,caption,rect.x+18,rect.y+193,10,Colors.RED if requires_air else Colors.TEXT_MUTED)

    def _draw_fleet_panel(self,surface):
        rect=self._fleet_rect
        card(surface,rect)
        text(surface,'Medical-center fleet',rect.x+18,rect.y+17,18,bold=True)
        text(surface,'Live service status. Scroll for all units.',rect.x+18,rect.y+44,10,Colors.TEXT_MUTED)
        clip=surface.get_clip()
        content=pygame.Rect(rect.x+12,rect.y+65,rect.width-24,rect.height-77)
        surface.set_clip(content.clip(clip))
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        for index,unit in enumerate(self.sim.fleet):
            y=content.y+index*107-self._fleet_scroll
            color=UNIT_COLORS[index%len(UNIT_COLORS)]
            pygame.draw.rect(surface,Colors.BG_CARD,(content.x,y,content.width,99),border_radius=9)
            pygame.draw.rect(surface,color,(content.x+12,y+16,7,7),border_radius=3)
            text(surface,unit['id'],content.x+27,y+11,14,color,True)
            label=unit['status'].replace('_',' ').title()
            text(surface,label,content.x+112,y+13,9,Colors.GREEN if unit['status']=='AVAILABLE' else Colors.ACCENT_AMBER,True)
            text(surface,f"Depot {unit.get('depot_label','?')}  /  Now {unit.get('position_label','?')}",content.x+12,y+35,11,Colors.TEXT_SECONDARY)
            text(surface,'OUT OF SERVICE: Gate exposure' if unit['status']=='OUT_OF_SERVICE' else 'Assignment: '+(unit.get('emergency_id') or 'Awaiting dispatch'),content.x+12,y+65,10,Colors.RED if unit['status']=='OUT_OF_SERVICE' else Colors.TEXT_MUTED)
        surface.set_clip(clip)
        if not self.sim.fleet:
            text(surface,'Depot units appear after connection.',rect.x+18,rect.y+91,12,Colors.TEXT_MUTED)

    def _draw_air_panel(self,surface):
        rect=pygame.Rect(self._right.x,self._right.y+240,self._right.width,180)
        card(surface,rect)
        air=self.sim.air_rescue
        text(surface,'Air rescue station',rect.x+18,rect.y+16,18,bold=True)
        text(surface,f"Pad {air.get('landed_label') or ('To '+air['target_label'] if air.get('target_label') else '--')}  /  {air.get('status','OFFLINE').replace('_',' ').title()}",rect.x+18,rect.y+43,11,Colors.TEXT_SECONDARY)
        pct=air.get('fuel_pct',0)
        color=Colors.GREEN if pct>air.get('low_fuel_pct',20) else Colors.RED
        pygame.draw.rect(surface,Colors.BG_CARD,(rect.x+18,rect.y+69,220,12),border_radius=5)
        pygame.draw.rect(surface,color,(rect.x+18,rect.y+69,round(220*pct/100),12),border_radius=5)
        text(surface,f'{pct:.0f}%',rect.right-68,rect.y+66,13,color,True)
        text(surface,f"Landing reserve {(air.get('required_landing_fuel') or 0):.1f}  |  Low fuel {air.get('low_fuel_pct',20):g}%",rect.x+18,rect.y+88,10,Colors.TEXT_MUTED)
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        self._landings.enabled=self.state.is_connected and not busy
        self._refuel.enabled=self.state.is_connected and not busy and air.get('landed_node') is not None and pct<100
        self._landings.draw(surface)
        self._refuel.draw(surface)
        self._relocate.enabled=self.state.is_connected and not busy and air.get('relocation',{}).get('can_relocate',False)
        if air.get('relocation_required'):
            self._relocate.draw(surface)
        else:
            text(surface,'Building > emergency > hospital > safe building',rect.x+18,rect.y+151,10,Colors.TEXT_MUTED)

    def _draw_modal(self,surface):
        shade=pygame.Surface(self.rect.size,pygame.SRCALPHA)
        shade.fill((13,25,45,145))
        surface.blit(shade,self.rect.topleft)
        rect=self._modal_rect
        card(surface,rect)
        self._close.draw(surface)
        text(surface,'Automatic city events' if self._modal=='events' else 'Landing sites & fuel safety' if self._modal=='landings' else 'Medical coverage & response activity',rect.x+24,rect.y+25,22,bold=True)
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        if self._modal=='events':
            data=self.sim.city_events
            settings=data.get('settings',{})
            ready=self.state.is_connected and not busy
            self._event_all.enabled=ready
            self._event_all.label='PAUSE ALL AUTOMATIC EVENTS' if data.get('enabled') else 'ENABLE ALL AUTOMATIC EVENTS'
            self._event_all.draw(surface)
            for button,(key,name) in zip(self._event_buttons,self._event_channels):
                button.enabled=ready
                button.label=name+': '+('ON' if settings.get(key) else 'OFF')
                button.draw(surface)
            for (key,slider),name in zip(self._event_rates.items(),('Medical emergency','Crime report','Temporary road closure')):
                text(surface,name+' chance per simulation step',slider.rect.x,slider.rect.y-24,13,Colors.TEXT_SECONDARY)
                slider.enabled=ready
                slider.draw(surface,Colors.ACCENT_CYAN)
                text(surface,f'{slider.value:g}%',slider.rect.right+18,slider.rect.y,13,Colors.ACCENT_CYAN,True)
            text(surface,f"Generated: {data.get('generated_medical',0)} medical / {data.get('generated_crimes',0)} crime / {data.get('generated_road_closures',0)} closures",rect.x+24,rect.y+465,13)
            text(surface,f"Automatic closures active: {len(data.get('active_road_closures',[]))} / {data.get('max_road_closures',3)}",rect.x+24,rect.y+493,12,Colors.TEXT_SECONDARY)
            text(surface,'Existing calls finish and scheduled roads reopen after events are paused.',rect.x+24,rect.y+526,12,Colors.TEXT_MUTED)
            text(surface,'PLAY advances the city. PAUSE freezes event generation and movement.',rect.x+24,rect.y+551,12,Colors.TEXT_MUTED)
            return
        if self._modal=='landings':
            text(surface,'Add or replace optional landing sectors at any time.',rect.x+24,rect.y+74,14)
            text(surface,'Choose non-hospital buildings with medical road access. Separate labels with commas.',rect.x+24,rect.y+100,12,Colors.TEXT_SECONDARY)
            self._landing_input.draw(surface)
            self._apply_landings.enabled=not busy
            self._apply_landings.draw(surface)
            labels=', '.join(self.graph.nodes[n]['label'] for n in self.sim.air_rescue.get('landing_nodes',[]) if n in self.graph.nodes)
            lines=['SAFE BUILDING BASES (HOSPITALS EXCLUDED)',labels,'','Hospital sectors are delivery destinations, never parking or relocation bases.',
                   'Gate-affected buildings are unavailable; relocation selects the closest safe building.',
                   'Fuel is consumed for every grid distance flown; refueling requires landing.',
                   'Takeoff reserves fuel for pickup, direct hospital delivery and the final building return.',
                   '', 'A patient is resolved on arrival at a safe hospital; the helicopter then returns to a building.']
            content=pygame.Rect(rect.x+24,rect.y+204,rect.width-48,rect.height-235)
        else:
            network=self.sim.medical_network
            text(surface,f"{len(network.get('centers',[]))} medical centers  /  {network.get('coverage_pct',0):g}% of city sectors reachable by road",rect.x+24,rect.y+74,14)
            missing=network.get('unreachable_nodes',[])
            labels=', '.join(self.graph.nodes[n]['label'] for n in missing if n in self.graph.nodes)
            lines=['SECTORS CUT OFF FROM ALL MEDICAL CENTERS',labels or 'None. All city sectors have medical road access.','','RECOMMENDED NEW MEDICAL CENTERS']
            choices=network.get('recommendations',[])
            lines += [f"{r['label']}: serves {r['gain']} unserved sector(s), mean road cost {r['mean_cost']:g}"+
                      (' (isolated sector; helicopter available for immediate rescue)' if r['isolated'] else '') for r in choices]
            if not choices:
                lines.append('No additional center needed for current connectivity.')
            lines += ['', 'RECENT NOTIFICATIONS']
            lines += [n['message'] for n in reversed(network.get('notifications',[])[-10:])]
            lines += ['', 'EMERGENCY ACTIVITY']
            lines += [f"{e['id']}  {e['label']}  /  {e.get('ambulance_id') or 'Helicopter'}  /  {e['status'].replace('_',' ').title()}" for e in reversed(self.sim.emergencies)]
            content=pygame.Rect(rect.x+24,rect.y+115,rect.width-48,rect.height-190)
            self._build_center.enabled=bool(choices) and not busy
            self._build_center.draw(surface)
            text(surface,'Opens the first recommended site with a new ambulance.',rect.x+340,rect.bottom-45,11,Colors.TEXT_MUTED)
        # Wrap and clip every message so even a city-wide outage remains readable.
        wrapped=[]
        font=Fonts.sans(13)
        for line in lines:
            line=sector_text(line)
            current=''
            for word in line.split():
                if current and font.size(current+' '+word)[0]>content.width-12:
                    wrapped.append(current)
                    current=word
                else:
                    current=(current+' '+word).strip()
            wrapped.append(current)
        self._modal_scroll=min(self._modal_scroll,max(0,len(wrapped)*24-content.height))
        clip=surface.get_clip()
        surface.set_clip(content.clip(clip))
        for i,line in enumerate(wrapped):
            text(surface,line,content.x,content.y+i*24-self._modal_scroll,13,Colors.TEXT_SECONDARY)
        surface.set_clip(clip)
