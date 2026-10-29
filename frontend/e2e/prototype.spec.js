import { test, expect } from '@playwright/test';

test('Gate alerts disable exposed ambulances and assistant relocation flies to a safe pad', async ({page,request})=>{
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
  await page.goto('/');
  await expect(page.getByRole('button',{name:'POLICE OPERATIONS',exact:true})).toBeVisible({timeout:30000});
  const initial=await (await request.get('/api/state')).json();
  expect(initial.fleet.every(u=>u.radius===undefined)).toBe(true);
  expect(initial.air_rescue.landing_sites.length).toBeGreaterThan(1);
  expect(initial.air_rescue.landing_sites.every(p=>p.kind==='BUILDING' && !initial.medical_network.centers.includes(p.node_id))).toBe(true);
  await request.post('/api/simulation/disasters/gate',{data:{node_id:initial.fleet[0].depot,intensity:1}});
  await expect(page.getByRole('status').filter({hasText:'Out of service'})).toContainText(initial.fleet[0].id,{timeout:10000});
  await request.post('/api/simulation/disasters/gate',{data:{node_id:initial.air_rescue.landed_node,intensity:1}});
  const alert=page.getByRole('alert').filter({hasText:'Assistant required: helicopter'});
  await expect(alert).toBeVisible({timeout:10000});
  await alert.getByRole('button',{name:'Relocate helicopter',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).air_rescue.landed_node,{timeout:20000}).not.toBe(initial.air_rescue.landed_node);
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).air_rescue.status,{timeout:20000}).toBe('READY');
  const state=await (await request.get('/api/state')).json();
  expect(state.air_rescue.fuel).toBeLessThan(initial.air_rescue.fuel);
  expect(state.air_rescue.landing_nodes).toContain(state.air_rescue.landed_node);
  expect(state.medical_network.centers).not.toContain(state.air_rescue.landed_node);
  expect(errors).toEqual([]);
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
});

test('live controls use Python state, GA, metrics export and comparison views', async ({ page, request }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button', { name: '📊 DASHBOARD' })).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('225 sectors',{exact:true})).toBeVisible();
  await page.getByTitle('Open Controls').click();
  await page.getByRole('button', { name: 'PLAY SIMULATION', exact: true }).click();
  await expect.poll(async () => (await (await request.get('/api/state')).json()).step, { timeout: 15000 }).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'PAUSE PLAYBACK', exact: true }).click();
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect.poll(async () => (await (await request.get('/api/state')).json()).optimization.status, { timeout: 15000 }).toBe('completed');
  await expect(page.getByText('OPTIMIZATION COMPLETE', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '📊 DASHBOARD' }).click();
  await expect(page.getByRole('heading', { name: 'NETWORK HEALTH', exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'EXPORT METRICS (CSV)', exact: true }).click();
  expect((await downloadPromise).suggestedFilename()).toBe('citymind-metrics.csv');
  await page.getByLabel('Close dashboard').click();
  await page.getByLabel('Comparison view',{exact:true}).selectOption({ label: 'Side-by-side Comparison' });
  await expect(page.locator('canvas')).toHaveCount(2);
  await page.getByLabel('Comparison view',{exact:true}).selectOption({ label: 'Single Algorithm' });
  await expect(page.locator('canvas')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('Gate of Death blocks normal traffic while preserving ambulance routes', async ({ page, request }) => {
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button',{name:'DISASTERS',exact:true}).click({timeout:30000});
  await expect(page.getByRole('button',{name:/flood/i})).toHaveCount(0);
  await page.getByRole('button',{name:'Unleash Gate of Death',exact:true}).click();
  await expect(page.getByLabel('Gate intensity').locator('option')).toHaveCount(8);
  await page.getByLabel('Gate center sector').fill('H8');
  await page.getByLabel('Gate intensity').selectOption('8');
  await page.getByRole('button',{name:'Unleash selected gate',exact:true}).click();
  await expect.poll(async()=>{
    const state=await (await request.get('/api/state')).json();
    return state.disasters.gates[0]?.radius;
  }, {timeout:15000}).toBe(8);
  const normal=await (await request.post('/api/simulation/route',{data:{src:112,dst:0,travel_mode:'normal'}})).json();
  const ambulance=await (await request.post('/api/simulation/route',{data:{src:112,dst:0,travel_mode:'ambulance'}})).json();
  expect(normal.reachable).toBe(false);
  expect(ambulance.reachable).toBe(true);
  await page.getByRole('button',{name:'Clear gate restrictions',exact:true}).click();
  await expect.poll(async()=>(await (await request.get('/api/state')).json()).disasters.gates.length,{timeout:15000}).toBe(0);
  expect(errors).toEqual([]);
});

test('police reports dispatch moving cars, coordinate medical help and compare deployments', async ({ page, request }) => {
  test.setTimeout(120000);
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
  await page.goto('/');
  await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click({timeout:30000});
  const panel=page.getByRole('region',{name:'Police operations'});
  await expect(panel.getByText('Stations and patrol fleet', {exact:true})).toBeVisible();
  await expect(panel.getByText(/High: dedicated continuous circuits/)).toBeVisible();
  await expect(panel.getByText(/High areas with assigned patrol:/)).toBeVisible();
  const initial=await (await request.get('/api/state')).json();
  expect(initial.police.banks).toHaveLength(3);
  expect(initial.police.banks.every(b=>b.protected && b.grid_blocks<=3)).toBe(true);
  await expect(panel.getByText(/^Financial sector [A-O]\d+ · PS-/)).toHaveCount(3);
  await panel.getByLabel('Crime report sector').fill(initial.police.banks[0].label);
  await panel.getByLabel('Crime incident type').selectOption('INJURY');
  await panel.getByLabel('Crime severity').selectOption('1');
  await panel.getByRole('button',{name:'Report and dispatch police',exact:true}).click();
  await expect.poll(async()=>{
    const state=await (await request.get('/api/state')).json();
    return state.police.reports[0]?.status;
  },{timeout:35000}).toBe('RESOLVED');
  const state=await (await request.get('/api/state')).json();
  expect(state.police.reports[0].police_status).toBe('COMPLETE');
  expect(state.police.reports[0].medical_status).toBe('RESOLVED');
  expect(state.events.metrics.civilians_rescued).toBe(1);
  expect(state.police.units.some(u=>u.position!==u.home)).toBe(true);
  await page.getByRole('button',{name:'PAUSE PLAYBACK',exact:true}).click();
  await panel.getByRole('button',{name:'Plan police stations',exact:true}).click();
  await expect(panel.getByText(/Proposed sites:/)).toBeVisible({timeout:15000});
  await panel.getByLabel('Police comparison seed').fill('42');
  await panel.getByRole('button',{name:'Compare police strategies',exact:true}).click();
  await expect(panel.getByRole('cell',{name:'risk_weighted',exact:true})).toBeVisible({timeout:75000});
  await expect(panel.getByRole('cell',{name:'uniform',exact:true})).toBeVisible();
  await page.screenshot({path:'e2e-artifacts/police-operations.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('patrol OFF parks other cars throughout manual crime dispatch', async ({ page, request }) => {
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
  for(let step=0;step<3;step++) await request.post('/api/simulation/step');
  await page.goto('/');
  await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click({timeout:30000});
  const panel=page.getByRole('region',{name:'Police operations'});
  await panel.getByRole('button',{name:'Patrols: ON',exact:true}).click();
  await expect(panel.getByRole('button',{name:'Patrols: OFF',exact:true})).toBeVisible();
  const frozen=await (await request.get('/api/state')).json();
  const parked=Object.fromEntries(frozen.police.units.map(u=>[u.id,u.position]));
  expect(frozen.police.units.every(u=>u.status==='AVAILABLE' && !u.path.length)).toBe(true);
  const target=frozen.graph.nodes.find(n=>!Object.values(parked).includes(n.id)).label;
  await panel.getByLabel('Crime report sector').fill(target);
  await panel.getByRole('button',{name:'Report and dispatch police',exact:true}).click();
  await expect.poll(async()=>{
    const state=await (await request.get('/api/state')).json();
    const incident=state.police.reports[0];
    if(!incident) return null;
    expect(state.police.settings.patrol_enabled).toBe(false);
    expect(state.police.units.some(u=>u.status==='PATROLLING')).toBe(false);
    for(const unit of state.police.units) {
      if(unit.id!==incident.unit_id) expect(unit.position).toBe(parked[unit.id]);
    }
    return incident.status;
  },{timeout:45000}).toBe('RESOLVED');
  await page.screenshot({path:'e2e-artifacts/police-patrol-off.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('crime heatmap keeps dense residential nodes low until a report is submitted', async ({ page, request }) => {
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await request.post('/api/start',{data:{seed:42,automatic_events:false}});
  const initial=await (await request.get('/api/state')).json();
  const target=initial.graph.nodes.find(n=>n.node_type==='RESIDENTIAL' && n.risk_features.dense_residential && n.risk_level==='LOW');
  expect(target).toBeTruthy();
  const hospitals=initial.graph.nodes.filter(n=>n.node_type==='HOSPITAL');
  const banks=initial.graph.nodes.filter(n=>n.node_type==='BANK');
  expect(new Set(initial.police.banks.map(b=>b.police_direction)).size).toBe(3);
  for(const bank of banks) {
    expect(bank.risk_level).toBe('HIGH');
    for(const hospital of hospitals) expect(Math.abs(bank.row-hospital.row)+Math.abs(bank.col-hospital.col)).toBeGreaterThanOrEqual(4);
  }
  await page.goto('/');
  await page.getByTitle('Open Controls').click({timeout:30000});
  const row=page.locator('.toggle-row').filter({hasText:'Crime Heatmap'});
  await row.locator('.toggle-switch').click();
  await expect(row.locator('.toggle-switch')).toHaveClass(/toggle-switch--on/);
  await page.getByRole('button',{name:'POLICE OPERATIONS',exact:true}).click();
  const panel=page.getByRole('region',{name:'Police operations'});
  await panel.getByLabel('Crime report sector').fill(target.label);
  await panel.getByRole('button',{name:'Report and dispatch police',exact:true}).click();
  await expect.poll(async()=>{
    const state=await (await request.get('/api/state')).json();
    return state.graph.nodes.find(n=>n.id===target.id).risk_level;
  },{timeout:15000}).toBe('HIGH');
  const affected=await (await request.get('/api/state')).json();
  expect(affected.police.crime_areas[0].radius).toBe(3);
  const neighbor=affected.graph.nodes.find(n=>Math.abs(n.row-target.row)+Math.abs(n.col-target.col)===1);
  expect(neighbor.risk_level).toBe('HIGH');
  expect(neighbor.risk_features.nearby_report_count).toBeGreaterThan(0);
  await expect(panel.getByText(/Reported crime affects a radius of 3 sector units/)).toBeVisible();
  await page.screenshot({path:'e2e-artifacts/crime-heatmap.png',fullPage:true});
  expect(errors).toEqual([]);
});
