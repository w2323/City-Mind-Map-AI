// Independent Dijkstra reference, matching the Pygame route lab's destination-risk costs.
export function referenceRoute(graph, src, dst, mode='normal') {
  const nodes = new Map(graph.nodes.map(n=>[n.id,n]));
  const adj = new Map(graph.nodes.map(n=>[n.id,[]]));
  const multipliers = {HIGH:2, MEDIUM:1.5, LOW:1, NONE:1};
  for(const e of graph.edges) {
    if(e.blocked || (mode==='normal' && e.temporarily_blocked)) continue;
    for(const [a,b] of [[e.node_a,e.node_b],[e.node_b,e.node_a]]) {
      if(!nodes.has(a) || !nodes.has(b)) continue;
      const multiplier = multipliers[nodes.get(b).risk_level] || 1;
      adj.get(a).push({from:a,to:b,base:e.cost,cost:e.cost*multiplier,multiplier});
    }
  }
  const dist = new Map([[src,0]]), prev = new Map(), pending = new Set(nodes.keys());
  while(pending.size) {
    let u, best=Infinity;
    for(const id of pending) if((dist.get(id) ?? Infinity)<best) {u=id;best=dist.get(id);}
    if(u===undefined) break;
    pending.delete(u);
    if(u===dst) break;
    for(const edge of adj.get(u) || []) if(best+edge.cost<(dist.get(edge.to) ?? Infinity)) {
      dist.set(edge.to,best+edge.cost);prev.set(edge.to,edge);
    }
  }
  if(!dist.has(dst)) return {reachable:false,path:[],path_cost:null,breakdown:[]};
  const path=[dst], breakdown=[];
  while(path[0]!==src) {const edge=prev.get(path[0]);breakdown.unshift(edge);path.unshift(edge.from);}
  return {reachable:true,path,path_cost:dist.get(dst),breakdown};
}
