"""Road-link disaster controls and eight ambulance-only Gate of Death levels."""
import math
import pygame
from screens.base_screen import BaseScreen
from screens.dispatch import text, card
from app.theme import Colors
from components.buttons import Button
from visualization.graph_renderer import GraphRenderer

ORDINALS = ('First','Second','Third','Fourth','Fifth','Sixth','Seventh','Eighth')


class GodModeScreen(BaseScreen):
    def __init__(self,app,rect):
        super().__init__(app,rect)
        self._ctrl_rect=pygame.Rect(rect.right-348,rect.y+20,328,rect.height-40)
        self._map_rect=pygame.Rect(rect.x+20,rect.y+92,rect.width-388,rect.height-112)
        self._renderer=GraphRenderer(self._map_rect.inflate(-20,-20))
        self._mode='block'
        self._selected_edge=None
        self._selected_node=None
        self._intensity=1
        self._preview=None
        self._preview_requested=None
        self._seen_sim=''
        self._history_scroll=0
        x,y,w=self._ctrl_rect.x+16,self._ctrl_rect.y,self._ctrl_rect.width-32
        self._mode_btns=[Button('BLOCK ROAD',(x,y+68,w//2-4,32),style='danger',font_size=11),
                         Button('UNBLOCK ROAD',(x+w//2+4,y+68,w//2-4,32),style='success',font_size=11),
                         Button('UNLEASH GATE OF DEATH',(x,y+108,w,36),style='neutral',font_size=12)]
        self._level_btns=[Button(f'{name} Gate of Death',(x+(i%2)*(w//2+4),y+272+(i//2)*39,w//2-4,32),font_size=10)
                          for i,name in enumerate(ORDINALS)]
        self._execute=Button('BLOCK SELECTED ROAD',(x,y+338,w,40),style='danger',font_size=12,enabled=False)
        self._clear=Button('CLEAR GATE RESTRICTIONS',(x,y+394,w,30),font_size=11,enabled=False)
        self._btn_step=Button('STEP',(x,self._ctrl_rect.bottom-49,w//2-4,32),style='primary',font_size=11)
        self._btn_restart=Button('NEW CITY',(x+w//2+4,self._ctrl_rect.bottom-49,w//2-4,32),font_size=11)
        self._relocate=Button('RELOCATE HELICOPTER',(self._map_rect.right-216,rect.y+18,210,32),style='warning',font_size=11,enabled=False)

    def on_enter(self):
        self._renderer.fit_to_view(self.graph.grid_rows,self.graph.grid_cols)
        self.state.god_mode=True
        self.app.show_status('Select a road link to block/unblock. Gate mode selects a center sector.',level='info')

    def on_state_updated(self):
        if self._seen_sim!=self.sim.sim_id:
            self._seen_sim=self.sim.sim_id
            self._selected_edge=self._selected_node=None
            self._preview=None
        if self._selected_edge and self.state.get_edge(*self._selected_edge) is None:
            self._selected_edge=None

    def _label(self,node):
        return self.graph.nodes.get(node,{}).get('label','--')

    def _radius(self):
        return next((v['radius'] for v in self.sim.disasters.get('levels',[]) if v['intensity']==self._intensity),0)

    def _request_preview(self):
        if self._mode!='gate' or self._selected_node is None or not hasattr(self.app,'run_query'):
            return
        key=(self.sim.sim_id,self.sim.revision,self._selected_node,self._intensity)
        if key==self._preview_requested or getattr(getattr(self.app,'query_runner',None),'is_running',False):
            return
        self._preview_requested=key
        node,intensity=self._selected_node,self._intensity
        def accept(data):
            if (data.get('sim_id'),data.get('revision'),data.get('node_id'),data.get('intensity'))==key==(self.sim.sim_id,self.sim.revision,self._selected_node,self._intensity):
                self._preview=data
        def failed(error):
            self._preview_requested=None
            self.app.show_status(error,level='error')
        self.app.run_query(lambda:self.app.client.preview_gate(node,intensity),accept,failed)

    def handle_event(self,event):
        if self._relocate.handle_event(event):
            self.app.async_rescue_action('relocate')
            return
        if self._renderer.handle_event(event):
            return
        for index,button in enumerate(self._mode_btns):
            if button.handle_event(event):
                self._mode=('block','unblock','gate')[index]
                self._selected_edge=self._selected_node=None
                self._renderer.selected_edge=self._renderer.selected_node=None
                self._preview=self._preview_requested=None
                return
        if self._mode=='gate':
            for index,button in enumerate(self._level_btns):
                if button.handle_event(event):
                    self._intensity=index+1
                    self._preview=None
                    self._request_preview()
                    return
        if self._execute.handle_event(event):
            if self._mode=='gate' and self._selected_node is not None:
                self.app.async_gate(self._selected_node,self._intensity)
            elif self._selected_edge:
                a,b=self._selected_edge
                operation=self.app.async_block_road if self._mode=='block' else self.app.async_unblock_road
                operation(a,b,self._label(a),self._label(b))
            return
        if self._clear.handle_event(event):
            self.app.async_gate(clear=True)
        if self._btn_step.handle_event(event):
            self.app.async_step()
        if self._btn_restart.handle_event(event):
            self.app.async_restart()
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self._renderer.viewport.collidepoint(event.pos):
            if self._mode=='gate':
                self._selected_node=self._renderer.hit_test_node(*event.pos,self.graph.nodes)
                self._renderer.selected_node=self._selected_node
                self._preview=None
                self._request_preview()
            else:
                # Clicking a junction cannot accidentally choose an incident road.
                if any(math.dist(event.pos,self._renderer.node_screen_pos(n))<self._renderer.cell*.23 for n in self.graph.nodes.values()):
                    return
                edge=self._renderer.hit_test_edge(*event.pos,self.graph.nodes,self.graph.edges)
                self._selected_edge=(edge['node_a'],edge['node_b']) if edge else None
                self._renderer.selected_edge=self._selected_edge
                self.state.selected_edge=self._selected_edge
        if event.type==pygame.MOUSEWHEEL and self._ctrl_rect.collidepoint(getattr(event,'pos',pygame.mouse.get_pos())):
            self._history_scroll=max(0,self._history_scroll-event.y*28)

    def update(self,dt):
        self._request_preview()
        self._renderer.fleet=self.sim.fleet
        self._renderer.air_rescue=self.sim.air_rescue
        self._renderer.police_service=self.sim.police
        self._renderer.show_coverage=False
        self._renderer.gate_zones=self.sim.disasters.get('gates',[])
        self._renderer.gate_preview=({'node_id':self._selected_node,'radius':self._radius()} if self._mode=='gate' and self._selected_node is not None else None)

    def draw(self,surface):
        pygame.draw.rect(surface,Colors.BG_DEEP,self.rect)
        text(surface,'Disaster control',self.rect.x+24,self.rect.y+22,24,bold=True)
        self._relocate.enabled=(self.state.is_connected and not getattr(getattr(self.app,'op_runner',None),'is_running',False)
                                and self.sim.air_rescue.get('relocation',{}).get('can_relocate',False))
        if self.sim.air_rescue.get('relocation_required'):
            self._relocate.draw(surface)
        d=self.sim.disasters
        text(surface,f"{d.get('fully_blocked_roads',0)} fully blocked   /   {d.get('ambulance_only_roads',0)} ambulance-only   /   {d.get('normal_open_roads',0)} normal roads open",self.rect.x+24,self.rect.y+58,13,Colors.TEXT_SECONDARY)
        card(surface,self._map_rect)
        routes=[{'path':u['path'],'color':Colors.ACCENT_CYAN} for u in self.sim.fleet if len(u.get('path',[]))>1]
        self._renderer.draw(surface,self.graph.nodes,self.graph.edges,self.sim.risk_predictions,route_paths=routes)
        self._draw_controls(surface)

    def _draw_controls(self,surface):
        r=self._ctrl_rect
        card(surface,r)
        x,y,w=r.x+16,r.y,r.width-32
        text(surface,'DISASTER OPTIONS',x,y+20,12,Colors.TEXT_MUTED,True)
        text(surface,'Road links and radius restrictions',x,y+43,12,Colors.TEXT_SECONDARY)
        busy=getattr(getattr(self.app,'op_runner',None),'is_running',False)
        ready=self.state.is_connected and not busy
        for index,button in enumerate(self._mode_btns):
            button.style=('danger','success','warning')[index] if self._mode==('block','unblock','gate')[index] else 'neutral'
            button.draw(surface)
        card(surface,pygame.Rect(x,y+163,w,85))
        if self._mode=='gate':
            text(surface,f'Center sector: {self._label(self._selected_node)}',x+12,y+175,15,bold=True)
            text(surface,'Click a sector, then choose an intensity.',x+12,y+201,11,Colors.TEXT_SECONDARY)
            text(surface,'Purple boundary previews the radius.',x+12,y+220,11,Colors.TEXT_MUTED)
            for index,button in enumerate(self._level_btns):
                button.style='warning' if self._intensity==index+1 else 'neutral'
                button.draw(surface)
            radius=self._radius()
            text(surface,f'Radius: {radius:g} sector units',x,y+435,13,Colors.PURPLE,True)
            count=f"{self._preview['road_count']} road links intersect this radius" if self._preview else 'Select a sector for the affected road count.'
            text(surface,count,x,y+455,11,Colors.TEXT_SECONDARY)
            self._execute.label='UNLEASH GATE OF DEATH'
            self._execute.style='warning'
            self._execute.rect=pygame.Rect(x,y+482,w,40)
            self._execute.enabled=ready and self._selected_node is not None
            self._clear.rect=pygame.Rect(x,y+535,w,30)
            history_y=y+637
        else:
            edge=self.state.get_edge(*self._selected_edge) if self._selected_edge else None
            label=f'{self._label(self._selected_edge[0])} - {self._label(self._selected_edge[1])}' if self._selected_edge else 'No road selected'
            text(surface,label,x+12,y+175,17,bold=True)
            status=('Fully blocked' if edge['blocked'] else 'Ambulances only' if edge.get('temporarily_blocked') else 'Open to all traffic') if edge else 'Click a link between two junctions.'
            text(surface,status,x+12,y+204,12,Colors.TEXT_SECONDARY)
            text(surface,'Select the road itself, between its sectors.',x,y+272,11,Colors.TEXT_SECONDARY)
            text(surface,'Blue outline marks your selected link.',x,y+294,11,Colors.TEXT_MUTED)
            self._execute.label='BLOCK SELECTED ROAD' if self._mode=='block' else 'UNBLOCK SELECTED ROAD'
            self._execute.style='danger' if self._mode=='block' else 'success'
            self._execute.rect=pygame.Rect(x,y+330,w,40)
            self._execute.enabled=ready and edge is not None and (not edge['blocked'] if self._mode=='block' else edge['blocked'] or edge.get('temporarily_blocked',False))
            self._clear.rect=pygame.Rect(x,y+385,w,30)
            history_y=y+490
        self._execute.draw(surface)
        self._clear.enabled=ready and bool(self.sim.disasters.get('gates',[]))
        self._clear.draw(surface)
        legend_y=self._clear.rect.bottom+16
        for i,(caption,color) in enumerate((('Red: fully blocked, including ambulances',Colors.RED),('Amber: temporarily blocked, ambulances only',Colors.ACCENT_AMBER),('Unblock reopens one road for all traffic.',Colors.TEXT_MUTED))):
            text(surface,caption,x,legend_y+i*19,10,color)
        text(surface,'RECENT DISASTER ACTIVITY',x,history_y,10,Colors.TEXT_MUTED,True)
        history=self.sim.disasters.get('history',[])+self.sim.medical_network.get('notifications',[])
        content=pygame.Rect(x,history_y+24,w,max(0,r.bottom-66-history_y-24))
        if content.height>0:
            clip=surface.get_clip()
            surface.set_clip(content.clip(clip))
            lines=[]
            for item in reversed(history):
                message=item['message']
                while message:
                    cut=min(43,len(message))
                    if len(message)>cut and ' ' in message[:cut]:
                        cut=message.rfind(' ',0,cut)
                    lines.append(message[:cut])
                    message=message[cut:].lstrip()
            self._history_scroll=min(self._history_scroll,max(0,len(lines)*17-content.height))
            for i,line in enumerate(lines):
                text(surface,line,x,content.y+i*17-self._history_scroll,10,Colors.TEXT_SECONDARY)
            surface.set_clip(clip)
        self._btn_step.enabled=self.state.is_connected and not busy and not self.sim.is_complete
        self._btn_restart.enabled=not busy
        self._btn_step.draw(surface)
        self._btn_restart.draw(surface)
