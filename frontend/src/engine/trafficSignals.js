export function signalPhase(time,nodeId) {
  const phase=((time+(nodeId%4)*1.5)%12+12)%12;
  return {horizontal:phase<5?'green':phase<6?'amber':'red',vertical:phase<6?'red':phase<11?'green':'amber'};
}
export function advanceTraffic(previous,delta,speed,light='green') {
  let next=previous+Math.min(delta,.05)*speed*.075;
  if(light!=='green'&&previous<=.78&&next>.78)next=.78;
  return next%1;
}
export function signalJunctions(edges,nodes) {
  const connected=new Map();
  for(const e of edges) {
    if(e.candidate||e.blocked||e.temporarily_blocked)continue;
    const a=nodes[e.nodeA],b=nodes[e.nodeB];if(!a||!b)continue;
    for(const n of [a,b]) {
      if(!connected.has(n.id))connected.set(n.id,{node:n,degree:0,horizontal:false,vertical:false});
      const item=connected.get(n.id);item.degree++;item.horizontal ||= a.row===b.row;item.vertical ||= a.col===b.col;
    }
  }
  return [...connected.values()].filter(s=>s.degree>=3&&s.horizontal&&s.vertical&&s.node.id%3===0).sort((a,b)=>b.degree-a.degree||a.node.id-b.node.id).slice(0,32).map(s=>s.node);
}
