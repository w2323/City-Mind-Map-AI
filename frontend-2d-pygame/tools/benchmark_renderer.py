"""Repeatable offscreen renderer benchmark; timings exclude display/vsync."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import sys, json, time, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pygame
from app.theme import Fonts
from visualization.graph_renderer import GraphRenderer
pygame.init()
Fonts.init()
nodes = {r*15+c: {'id':r*15+c,'row':r,'col':c,'node_type':'RESIDENTIAL','population':100,'risk_level':'LOW','accessible':True} for r in range(15) for c in range(15)}
edges=[]
for r in range(15):
    for c in range(15):
        u=r*15+c
        for v in ([u+1] if c<14 else [])+([u+15] if r<14 else []):
            edges.append({'node_a':u,'node_b':v,'cost':1.0,'blocked':False})
surface=pygame.Surface((1440,900))
renderer=GraphRenderer(pygame.Rect(260,48,900,824))
renderer.fit_to_view()
for _ in range(10): renderer.draw(surface,nodes,edges)
times=[]
for _ in range(300):
    start=time.perf_counter()
    renderer.draw(surface,nodes,edges)
    times.append((time.perf_counter()-start)*1000)
print(json.dumps({'frames':len(times),'median_ms':round(statistics.median(times),4),'p95_ms':round(sorted(times)[int(len(times)*.95)],4),'mean_ms':round(statistics.mean(times),4)}))
pygame.quit()
