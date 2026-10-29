"""Render all desktop screens offscreen using a real initialized Python model."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root.parent))
import pygame
from app import application
from app.state import ActiveScreen, ConnectionStatus
from core.simulation_engine import Simulation
application.BackgroundPoller.start = lambda self: None
model = Simulation(seed=42, verbose=False)
model.initialize()
app = application.Application()
payload = model.state.to_dict()
from config.simulation_config import SimConfig
payload['config'] = {'ga_generations': SimConfig.GA_GENERATIONS}
payload['optimization'] = {'status': 'idle', 'generation': 0}
app.state.update_sim(payload)
app.state.connection = ConnectionStatus.CONNECTED
out = root / 'artifacts'
out.mkdir(exist_ok=True)
for index, screen in enumerate(ActiveScreen):
    app.navigate(screen)
    app._active_screen.update(.016)
    app.draw_frame()
    pygame.image.save(app.window, str(out / f'{index+1}_{screen.name.lower()}.png'))
app.navigate(ActiveScreen.DASHBOARD)
target=next(n for n in reversed(model.graph.nodes) if n not in model.state.medical_network.centers)
for neighbor in list(model.graph.get_neighbors(target)):
    model.block_road_manually(target,neighbor)
app.state.update_sim(model.state.to_dict())
screen=app._active_screen
screen.on_state_updated()
app.draw_frame()
pygame.image.save(app.window,str(out/'10_coverage_alert.png'))
screen._modal=None
screen._inp_node.text=model.graph.nodes[target].label
model.state.air_rescue.dispatch(target,model.state.step)
for _ in range(3):
    model.step_forward()
app.state.update_sim(model.state.to_dict())
screen.on_state_updated()
screen._modal=None
screen.update(1)
app.draw_frame()
pygame.image.save(app.window,str(out/'11_air_rescue.png'))
screen._modal='landings'
app.draw_frame()
pygame.image.save(app.window,str(out/'12_landing_sites.png'))
app.navigate(ActiveScreen.GOD_MODE)
screen=app._active_screen
for level,name in [(1,'13_first_gate'),(8,'14_eighth_gate')]:
    model.state.disasters.clear(model.state.step)
    model.state.disasters.unleash(112,level,model.state.step)
    app.state.update_sim(model.state.to_dict())
    screen.on_state_updated()
    screen._mode='gate'
    screen._intensity=level
    screen._selected_node=112
    screen.update(.016)
    app.draw_frame()
    pygame.image.save(app.window,str(out/(name+'.png')))
model.state.disasters.clear(model.state.step)
police=model.state.police
root_node=police.stations[1]['node_id']
incident=next(iter(model.graph.get_neighbors(root_node)))
police.report(incident,'DISTURBANCE',3,model.state.step)
for _ in range(2):
    model.step_forward()
app.state.update_sim(model.state.to_dict())
app.navigate(ActiveScreen.POLICE)
screen=app._active_screen
screen.update(.016)
app.draw_frame()
pygame.image.save(app.window,str(out/'15_police_response.png'))
from core.police_service import compare_strategies
screen._compare=compare_strategies(model.graph,seed=42,steps=80)
screen._modal=True
app.draw_frame()
pygame.image.save(app.window,str(out/'16_police_comparison.png'))
example=Simulation(seed=42,verbose=False)
example.initialize()
example.state.police.report(36,'THEFT',1,0)  # G3, a clean single-incident radius example.
app.state.update_sim(example.state.to_dict())
app.navigate(ActiveScreen.RISK_HEATMAP)
screen=app._active_screen
screen._selected_node=36
screen._renderer.selected_node=36
screen.update(.016)
app.draw_frame()
pygame.image.save(app.window,str(out/'17_crime_area_g3.png'))
assert screen._renderer.police_service['crime_areas'][0]['node_id']==36
assert app.state.backend_graph.nodes[37]['risk_level']=='HIGH'
example.state.police.configure(0,patrol_enabled=False)
example.state.police.report(224,'INJURY',2,0)
app.state.update_sim(example.state.to_dict())
app.navigate(ActiveScreen.POLICE)
screen=app._active_screen
screen.update(.016)
app.draw_frame()
pygame.image.save(app.window,str(out/'18_joint_police_ambulance.png'))
example.state.disasters.unleash(example.state.fleet.units[0]['depot'],1,0)
example.state.disasters.unleash(example.state.air_rescue.landed_node,1,0)
app.state.update_sim(example.state.to_dict())
app.navigate(ActiveScreen.GOD_MODE)
screen=app._active_screen
screen._mode='gate'
screen._selected_node=example.state.air_rescue.landed_node
screen._intensity=1
screen.update(.016)
app.draw_frame()
assert screen._relocate.enabled
pygame.image.save(app.window,str(out/'19_gate_vehicle_outage.png'))
app.navigate(ActiveScreen.DASHBOARD)
screen=app._active_screen
screen._modal=None
screen.update(.016)
app.draw_frame()
pygame.image.save(app.window,str(out/'20_assisted_relocation.png'))
patrol_example=Simulation(seed=42,verbose=False)
patrol_example.initialize()
for _ in range(12):
    patrol_example.step_forward()
app.state.update_sim(patrol_example.state.to_dict())
app.navigate(ActiveScreen.POLICE)
screen=app._active_screen
screen.update(.016)
app.draw_frame()
pygame.image.save(app.window,str(out/'21_heatmap_patrols.png'))
print('Heatmap patrol policy:',patrol_example.state.police.to_dict(12)['patrol_policy'])
patrol_example.events.close()
example.events.close()
app.close()
model.events.close()
print('Rendered all nine screens to',out)

