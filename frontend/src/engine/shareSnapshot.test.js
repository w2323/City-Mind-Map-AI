import test from 'node:test';
import assert from 'node:assert/strict';
import {shareSnapshot} from './shareSnapshot.js';
const snapshot=()=>({sim_id:'a',revision:1,graph:{nodes:[{id:1,node_type:'HOSPITAL'}],edges:[]},analysis:{edgeList:[],coveredNodes:[1]},fleet:[{position:1}],optimization:{status:'idle'},events:{events:[]}});
test('an unchanged poll preserves the scene snapshot',()=>{
  const before=snapshot();assert.equal(shareSnapshot(before,structuredClone(before)),before);
});
test('vehicle changes preserve static graph and road references',()=>{
  const before=snapshot(),next=structuredClone(before);next.revision++;next.fleet[0].position=2;
  const merged=shareSnapshot(before,next);
  assert.equal(merged.graph,before.graph);assert.equal(merged.analysis.edgeList,before.analysis.edgeList);assert.equal(merged.fleet[0].position,2);
});
test('GA progress, construction and city restart are never suppressed',()=>{
  const before=snapshot(),progress=structuredClone(before);progress.optimization.status='running';
  assert.notEqual(shareSnapshot(before,progress),before);
  const built=structuredClone(before);built.revision++;built.graph.nodes[0].node_type='BANK';assert.notEqual(shareSnapshot(before,built).graph,before.graph);
  const reset=structuredClone(before);reset.sim_id='b';assert.equal(shareSnapshot(before,reset),reset);
});
