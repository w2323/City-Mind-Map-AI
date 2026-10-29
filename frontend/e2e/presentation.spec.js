import {test,expect} from '@playwright/test';
import * as THREE from 'three';
import {toDisplayNode} from '../src/engine/gridReferences.js';

test.beforeEach(async({request})=>{
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
});

test('grid references are on by default and traffic signals cycle without a rendering regression',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');
  const city=page.getByTestId('city-viewport');
  await expect(city).toHaveAttribute('data-grid-columns','1–15');
  await expect(city).toHaveAttribute('data-grid-rows','A–O');
  await expect.poll(async()=>Number(await city.getAttribute('data-signal-count'))).toBeGreaterThan(0);
  await expect(city).toHaveAttribute('data-signal-phase',/horizontal/);
  const phase=await city.getAttribute('data-signal-phase');
  await expect.poll(()=>city.getAttribute('data-signal-phase'),{timeout:14000}).not.toBe(phase);
  await expect(city).toHaveAttribute('data-draw-calls',/\d+/);
  expect(Number(await city.getAttribute('data-draw-calls'))).toBeLessThan(250);
  await page.getByRole('button',{name:'CITY MAP',exact:true}).click();
  await expect(page.getByLabel('Sector Labels',{exact:true})).toBeChecked();
  await page.getByLabel('Traffic Signals',{exact:true}).uncheck();
  await expect(city).toHaveAttribute('data-signal-count','0');
  await page.getByLabel('Traffic Signals',{exact:true}).check();
  await page.getByRole('button',{name:'Close workspace',exact:true}).click();
  await page.getByRole('button',{name:'Map overview',exact:true}).click();
  await expect.poll(async()=>Number((await city.getAttribute('data-camera-position')).split(',')[1])).toBe(190);
  const bounds=await page.locator('canvas').boundingBox(),camera=new THREE.PerspectiveCamera(50,bounds.width/bounds.height,.1,450);
  camera.position.fromArray((await city.getAttribute('data-camera-position')).split(',').map(Number));camera.quaternion.fromArray((await city.getAttribute('data-camera-direction')).split(',').map(Number)).normalize();camera.updateMatrixWorld();
  const project=(row,col)=>{const n=toDisplayNode({row,col});return new THREE.Vector3(n.col*8,0,n.row*8).project(camera);};
  const a1=project(0,0),a2=project(1,0),b1=project(0,1);
  expect(a2.x).toBeGreaterThan(a1.x);expect(Math.abs(a2.y-a1.y)).toBeLessThan(.001);
  expect(b1.y).toBeLessThan(a1.y);expect(Math.abs(b1.x-a1.x)).toBeLessThan(.001);
  await page.screenshot({path:'e2e-artifacts/presentation-grid.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('police controls remain clickable during a slow playback step and probability sliders commit once',async({page,request})=>{
  let held=false,release,notify;
  const seen=new Promise(resolve=>notify=resolve);
  await page.route('**/api/simulation/step',async route=>{
    if(!held){held=true;notify();await new Promise(resolve=>release=resolve);}
    await route.continue();
  });
  await page.goto('/');
  await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click();
  const panel=page.getByRole('region',{name:'Police operations'});
  await page.getByRole('button',{name:'PLAY SIMULATION',exact:true}).click();
  await seen;
  try {
    const patrol=panel.getByRole('button',{name:'Patrols: ON',exact:true});
    await expect(patrol).toBeEnabled();
    await patrol.click();
    await expect(panel.getByRole('status')).toContainText('Saving your police action');
  } finally {release?.();}
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).police.settings.patrol_enabled).toBe(false);
  await page.getByRole('button',{name:'PAUSE PLAYBACK',exact:true}).click();
  await expect(panel.getByRole('button',{name:'Patrols: OFF',exact:true})).toBeEnabled();
  const writes=[];
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/police/settings')&&r.postDataJSON()?.auto_probability!=null)writes.push(r.postDataJSON().auto_probability);});
  const slider=panel.getByLabel('Automatic incident chance',{exact:true});
  await slider.scrollIntoViewIfNeeded();
  const box=await slider.boundingBox();
  await page.mouse.move(box.x+box.width*.15,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(box.x+box.width*.75,box.y+box.height/2,{steps:14});await page.mouse.up();
  const expected=Number(await slider.inputValue())/100;
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).police.settings.auto_probability).toBe(expected);
  expect(writes).toHaveLength(1);
  await page.screenshot({path:'e2e-artifacts/presentation-police.png',fullPage:true});
});

test('police planning explains unavailable actions and constructs a selected station through the interface',async({page,request})=>{
  const initial=await (await request.get('/api/state')).json();
  const target=initial.graph.nodes.find(n=>n.node_type!=='BANK'&&!initial.police.stations.some(s=>s.node_id===n.id)&&!initial.medical_network.centers.includes(n.id));
  for(const e of initial.graph.edges.filter(e=>e.node_a===target.id||e.node_b===target.id))await request.post(`/api/simulation/block_road/${e.node_a}/${e.node_b}`);
  await page.goto('/');await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click();
  const panel=page.getByRole('region',{name:'Police operations'});
  const construct=panel.getByRole('button',{name:'Open recommended station',exact:true});
  await expect(construct).toBeDisabled();
  await expect(panel.getByRole('note')).toContainText('Calculate station recommendations first');
  await page.getByRole('button',{name:'PLAY SIMULATION',exact:true}).click();
  await panel.getByRole('button',{name:'Plan police stations',exact:true}).click();
  await expect(page.getByRole('button',{name:'PLAY SIMULATION',exact:true})).toBeVisible();
  await expect(construct).toBeEnabled({timeout:20000});
  await panel.getByLabel('Recommended station site',{exact:true}).selectOption(target.label);
  await construct.click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).police.stations.length).toBe(initial.police.stations.length+1);
  const state=await (await request.get('/api/state')).json();
  expect(state.police.units.length).toBeGreaterThan(initial.police.units.length);
  expect(state.police.stations.some(s=>s.node_id===target.id)).toBe(true);
  await expect(panel.getByRole('button',{name:'Refuel helicopter',exact:true})).toHaveAttribute('title','Fuel is already full.');
});

test('police comparison survives a slow response and leaves other controls usable',async({page})=>{
  await page.route('**/api/simulation/police/compare',async route=>{
    const response=await route.fetch();
    await new Promise(resolve=>setTimeout(resolve,17000));
    await route.fulfill({response});
  });
  await page.goto('/');await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click();
  const panel=page.getByRole('region',{name:'Police operations'});
  await panel.getByLabel('Police comparison steps',{exact:true}).fill('20');
  await panel.getByLabel('Police comparison report count',{exact:true}).fill('1');
  await panel.getByRole('button',{name:'Compare police strategies',exact:true}).click();
  await expect(panel.getByRole('status')).toContainText('Running both strategies');
  await expect(panel.getByRole('button',{name:'Patrols: ON',exact:true})).toBeEnabled();
  await expect(panel.getByRole('cell',{name:'risk_weighted',exact:true})).toBeVisible({timeout:60000});
  await expect(panel.getByRole('cell',{name:'uniform',exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Compare police strategies',exact:true})).toBeEnabled();
  await expect(panel.getByRole('alert')).toHaveCount(0);
});
