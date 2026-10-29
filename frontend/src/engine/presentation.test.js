import test from 'node:test';
import assert from 'node:assert/strict';
import {gridReferences,toDisplayNode,toDisplayAir,gridLetter} from './gridReferences.js';
import {signalPhase,signalJunctions,advanceTraffic} from './trafficSignals.js';
import {createMutationQueue} from './mutationQueue.js';
test('numbers increase horizontally, letters vertically, with backend IDs and labels preserved',()=>{
  const a2=toDisplayNode({id:15,label:'A2',row:1,col:0}),b1=toDisplayNode({id:1,label:'B1',row:0,col:1});
  assert.equal(a2.col*8,8);assert.equal(a2.row*8,0);assert.equal(a2.label,'A2');assert.equal(a2.id,15);
  assert.equal(b1.col*8,0);assert.equal(b1.row*8,8);
  assert.deepEqual(toDisplayAir({position:[2,3],target:15}),{position:[3,2],target:15});
  const axes=gridReferences(15,15);assert.equal(axes.length,60);assert.ok(axes.some(e=>e.text==='15'&&e.x===112&&e.z===-7));assert.ok(axes.some(e=>e.text==='O'&&e.x===-7&&e.z===112));
  assert.equal(gridLetter(26),'AA');
});
test('signal phases do not give conflicting green lights and cars wait at red',()=>{
  for(let t=0;t<24;t+=.25){const s=signalPhase(t,0);assert.ok(!(s.horizontal!=='red'&&s.vertical!=='red'));}
  assert.equal(advanceTraffic(.78,.05,4,'red'),.78);
  assert.equal(advanceTraffic(.78,.05,4,'amber'),.78);
  assert.ok(advanceTraffic(.78,.05,4,'green')>.78);
  assert.ok(advanceTraffic(.9,.05,4,'red')>.9); // clear an already-entered intersection
  const nodes={0:{id:0,row:1,col:1},1:{id:1,row:1,col:0},2:{id:2,row:0,col:1},3:{id:3,row:1,col:2}};
  const edges=[1,2,3].map(id=>({nodeA:0,nodeB:id}));
  assert.equal(signalJunctions(edges,nodes).length,1);edges[0].blocked=true;assert.equal(signalJunctions(edges,nodes).length,0);
});
test('operator actions wait for in-flight steps and are never discarded',async()=>{
  const queue=createMutationQueue(),events=[];let finish;
  const step=queue.run(()=>new Promise(resolve=>{events.push('step');finish=resolve;}));
  const action=queue.run(()=>{events.push('police');return true;});
  await Promise.resolve();assert.deepEqual(events,['step']);finish();await step;assert.equal(await action,true);assert.deepEqual(events,['step','police']);
  await assert.rejects(queue.run(()=>{throw new Error('invalid request');}));
  assert.equal(await queue.run(()=>42),42);
});
