import test from 'node:test';
import assert from 'node:assert/strict';
import {referenceRoute} from './referenceRoute.js';

const graph={nodes:[{id:10,risk_level:'LOW'},{id:20,risk_level:'HIGH'},{id:30,risk_level:'LOW'},{id:40,risk_level:'LOW'}],edges:[
  {node_a:10,node_b:20,cost:1}, {node_a:20,node_b:30,cost:1}, {node_a:10,node_b:30,cost:2.5},
]};
test('risk weighted path beats fewer geometric steps and uses IDs rather than array indices',()=>{
  assert.deepEqual(referenceRoute(graph,10,30).path,[10,30]);
  assert.deepEqual(referenceRoute(graph,30,10).path,[30,10]);
  assert.equal(referenceRoute(graph,10,20).path_cost,2);
  assert.equal(referenceRoute(graph,20,10).path_cost,1);
});
test('normal traffic cannot cross gates, ambulances can, and full blocks stop both',()=>{
  const isolated={...graph,edges:[{node_a:10,node_b:20,cost:1,temporarily_blocked:true}]};
  assert.equal(referenceRoute(isolated,10,20).reachable,false);
  assert.equal(referenceRoute(isolated,10,20,'ambulance').path_cost,2);
  isolated.edges[0].blocked=true;
  assert.equal(referenceRoute(isolated,10,20,'ambulance').reachable,false);
});
test('self routes cost zero and disconnected destinations have no path',()=>{
  assert.deepEqual(referenceRoute(graph,10,10).path,[10]);
  assert.equal(referenceRoute(graph,10,10).path_cost,0);
  assert.deepEqual(referenceRoute(graph,10,40).path,[]);
});
