export function getLabelFromNode(node) {
  if (!node) return '';
  const colLetter = String.fromCharCode(65 + node.col);
  const rowNum = node.row + 1;
  return `${colLetter}${rowNum}`;
}

export function getNodeIdFromLabel(label, nodes) {
  const match = label.toUpperCase().match(/^([A-Z])(\d+)$/);
  if (!match) return null;
  const col = match[1].charCodeAt(0) - 65;
  const row = parseInt(match[2], 10) - 1;
  
  for (const id in nodes) {
    if (nodes[id].col === col && nodes[id].row === row) {
      return Number(id);
    }
  }
  return null;
}

export function runDijkstra(graphNodes, edges, startId) {
  const dist = {};
  const prev = {};
  const unvisited = new Set();
  
  const adj = {};
  for (const id in graphNodes) {
    dist[id] = Infinity;
    prev[id] = null;
    unvisited.add(Number(id));
    adj[id] = [];
  }
  dist[startId] = 0;
  
  for (const edge of edges) {
    if (edge.blocked) continue;
    adj[edge.nodeA].push(edge.nodeB);
    adj[edge.nodeB].push(edge.nodeA);
  }
  
  while (unvisited.size > 0) {
    let u = null;
    let minDist = Infinity;
    for (const id of unvisited) {
      if (dist[id] < minDist) {
        minDist = dist[id];
        u = id;
      }
    }
    if (u === null) break; // unreachable nodes remaining
    unvisited.delete(u);
    
    for (const v of adj[u]) {
      if (unvisited.has(v)) {
        const alt = dist[u] + 1;
        if (alt < dist[v]) {
          dist[v] = alt;
          prev[v] = u;
        }
      }
    }
  }
  
  return { dist, prev };
}

export function getPath(prev, targetId) {
  const path = [];
  let u = targetId;
  if (prev[u] !== null || u === targetId) {
    while (u !== undefined && u !== null) {
      path.unshift(u);
      u = prev[u];
    }
  }
  return path.length > 1 ? path : [];
}

export class UnionFind {
  constructor(n) {
    this.parent = Array.from({ length: n }, (_, i) => i);
    this.rank = new Array(n).fill(0);
  }

  find(x) {
    if (this.parent[x] !== x) {
      this.parent[x] = this.find(this.parent[x]);
    }
    return this.parent[x];
  }

  union(x, y) {
    let px = this.find(x);
    let py = this.find(y);
    if (px === py) return false;
    if (this.rank[px] < this.rank[py]) {
      this.parent[px] = py;
    } else if (this.rank[px] > this.rank[py]) {
      this.parent[py] = px;
    } else {
      this.parent[py] = px;
      this.rank[px]++;
    }
    return true;
  }
}

export function getMST(edges, numNodes) {
  const uf = new UnionFind(numNodes);
  const mst = [];
  const extra = [];
  
  // Assumes edges are somewhat sorted or uniform. The backend already provides 
  // an optimized edge list. We'll just build an arbitrary spanning tree from it.
  for (const edge of edges) {
    if (uf.union(edge.nodeA, edge.nodeB)) {
      mst.push(edge);
    } else {
      extra.push(edge);
    }
  }
  
  return { mst, extra };
}
