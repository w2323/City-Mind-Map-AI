import {test,expect} from '@playwright/test';

test.beforeEach(async({request})=>{
  await request.post('/api/start',{data:{seed:42}});
  await request.post('/api/simulation/events/settings',{data:{enabled:false}});
  await request.post('/api/simulation/police/settings',{data:{patrol_enabled:false,automatic_incidents:false}});
});

test('medical dispatch resolves a call through the 3D controls',async({page,request})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const initial=await (await request.get('/api/state')).json();
  await page.goto('/');
  await page.getByRole('button',{name:'MEDICAL DISPATCH',exact:true}).click({timeout:30000});
  const panel=page.getByRole('region',{name:'Medical operations'});
  const depot=initial.fleet[0].depot;
  const edge=initial.graph.edges.find(e=>e.node_a===depot || e.node_b===depot);
  const target=initial.graph.nodes.find(n=>n.id===(edge.node_a===depot?edge.node_b:edge.node_a));
  await panel.getByLabel('Emergency sector').fill(target.label);
  await panel.getByRole('button',{name:'Dispatch ambulance',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).emergencies[0]?.status,{timeout:30000}).toBe('RESOLVED');
  await expect(panel.getByText(/1 resolved/)).toBeVisible();
  await page.screenshot({path:'e2e-artifacts/medical-operations.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('route lab compares real costs and invalidates a changed city',async({page,request})=>{
  await page.goto('/');
  await page.getByRole('button',{name:'ROUTE LAB',exact:true}).click({timeout:30000});
  await page.getByLabel('Route source',{exact:true}).fill('A1');
  await page.getByLabel('Route destination',{exact:true}).fill('O15');
  await page.getByRole('button',{name:'Calculate route',exact:true}).click();
  await expect(page.getByText('Verified: algorithms agree',{exact:true})).toBeVisible();
  await request.post('/api/simulation/disasters/gate',{data:{node_id:0,intensity:1}});
  await expect(page.getByText('Verified: algorithms agree',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Calculate route',exact:true}).click();
  await expect(page.getByText('A*: Unreachable',{exact:true})).toBeVisible();
  await page.getByLabel('Route travel mode').selectOption('ambulance');
  await page.getByRole('button',{name:'Calculate route',exact:true}).click();
  await expect(page.getByText('Verified: algorithms agree',{exact:true})).toBeVisible();
  await expect(page.getByText(/^A\*: cost/)).toBeVisible();
  await page.screenshot({path:'e2e-artifacts/route-lab.png',fullPage:true});
});

test('coverage recommendation constructs a real hospital and ambulance',async({page,request})=>{
  const initial=await (await request.get('/api/state')).json();
  const target=initial.graph.nodes.find(n=>!initial.medical_network.centers.includes(n.id));
  for(const e of initial.graph.edges.filter(e=>e.node_a===target.id || e.node_b===target.id))
    await request.post(`/api/simulation/block_road/${e.node_a}/${e.node_b}`);
  await page.goto('/');
  await page.getByRole('button',{name:'MEDICAL DISPATCH',exact:true}).click({timeout:30000});
  await page.getByRole('button',{name:`Open medical center at ${target.label}`,exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).fleet.length).toBe(initial.fleet.length+1);
  await expect(page.getByText('No additional medical center recommended.')).toBeVisible();
});

test('landing edits, event channels and diagnostics are wired',async({page,request})=>{
  const initial=await (await request.get('/api/state')).json();
  await page.goto('/');
  await page.getByRole('button',{name:'MEDICAL DISPATCH',exact:true}).click({timeout:30000});
  const pad=initial.air_rescue.landing_sites.find(p=>p.available);
  await page.getByLabel('Landing sectors',{exact:true}).fill(pad.label);
  await page.getByRole('button',{name:'Apply landing sites',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).air_rescue.custom_landings).toContain(pad.node_id);
  await page.getByRole('button',{name:'CITY EVENTS',exact:true}).click();
  await expect(page.getByRole('region',{name:'Automatic city events'})).toBeVisible();
  await page.getByRole('button',{name:'Enable all automatic events',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).city_events.enabled).toBe(true);
  await page.getByRole('button',{name:'DIAGNOSTICS',exact:true}).click();
  await page.getByRole('button',{name:'Run diagnostics',exact:true}).click();
  await expect(page.getByText('PASS · Unique sector IDs',{exact:true})).toBeVisible();
});

test('isolated sector unlocks helicopter rescue and completes hospital delivery',async({page,request})=>{
  const initial=await (await request.get('/api/state')).json();
  const target=initial.graph.nodes.find(n=>!initial.medical_network.centers.includes(n.id));
  for(const e of initial.graph.edges.filter(e=>e.node_a===target.id || e.node_b===target.id))
    await request.post(`/api/simulation/block_road/${e.node_a}/${e.node_b}`);
  await page.goto('/');
  await page.getByRole('button',{name:'MEDICAL DISPATCH',exact:true}).click({timeout:30000});
  const panel=page.getByRole('region',{name:'Medical operations'});
  await panel.getByLabel('Emergency sector').fill(target.label);
  await expect(panel.getByRole('button',{name:'Dispatch ambulance',exact:true})).toBeDisabled();
  await panel.getByRole('button',{name:'Helicopter rescue',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).emergencies[0]?.status,{timeout:40000}).toBe('RESOLVED');
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).air_rescue.status,{timeout:20000}).toBe('READY');
  await panel.getByRole('button',{name:'Pause response playback',exact:true}).click();
  await panel.getByRole('button',{name:'Refuel',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).air_rescue.fuel_pct).toBe(100);
});
