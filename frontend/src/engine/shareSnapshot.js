const same=(a,b)=>a===b||JSON.stringify(a)===JSON.stringify(b);
// Keep static scene inputs stable while vehicles, events, or GA progress change.
export function shareSnapshot(previous,incoming) {
  if(!previous||previous.sim_id!==incoming.sim_id)return incoming;
  if(previous.revision===incoming.revision&&same(previous.optimization,incoming.optimization)&&same(previous.events,incoming.events))return previous;
  const next={...incoming};
  if(previous.graph&&incoming.graph) {
    next.graph={...incoming.graph};
    for(const key of ['nodes','edges'])if(same(previous.graph[key],incoming.graph[key]))next.graph[key]=previous.graph[key];
    if(same(previous.graph,next.graph))next.graph=previous.graph;
  }
  if(previous.analysis&&incoming.analysis) {
    next.analysis={...incoming.analysis};
    for(const key of Object.keys(incoming.analysis))if(same(previous.analysis[key],incoming.analysis[key]))next.analysis[key]=previous.analysis[key];
  }
  return next;
}
