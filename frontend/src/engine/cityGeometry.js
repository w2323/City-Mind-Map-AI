// Sector centers are intersections. Buildings occupy the block beside them,
// leaving the backend road coordinates clear for vehicles and walking.
export const CELL=8;
export const PLOT_OFFSET=4;
export const plotPosition=n=>[n.col*CELL+PLOT_OFFSET,n.row*CELL+PLOT_OFFSET];
export function buildingHeight(n) {
  if(!n||n.node_type==='EMPTY')return .2;
  const seed=(n.id*16807+13)%997;
  return (['INDUSTRIAL','POWER_PLANT'].includes(n.node_type)?2:n.node_type==='HOSPITAL'?4:n.node_type==='BANK'?9:n.node_type==='SCHOOL'?2:3+seed%10)*.78+.4;
}
export function buildCity(nodes) {
  const batches={walls:[],glass:[],roofs:[],paving:[],grass:[],trunks:[],leaves:[],poles:[],lamps:[],marks:[]};
  const add=(batch,p,s,c,node)=>batches[batch].push({p,s,c,node});
  for(const n of nodes) {
    const [x,z]=plotPosition(n),seed=(n.id*16807+13)%997;
    const empty=n.node_type==='EMPTY';
    add('paving',[x,.06,z],[5.3,.12,5.3],'#b6b6a7',n.id);
    if(empty) {
      add('grass',[x,.15,z],[4.7,.15,4.7],'#5b8063',n.id);
      for(let i=0;i<3;i++) {
        const tx=x-1.4+(i%2)*2.5,tz=z-1.4+Math.floor(i/2)*2.5;
        add('trunks',[tx,.9,tz],[.16,1.5,.16],'#79634e');
        add('leaves',[tx,2,tz],[1.35,1.8,1.35],i%2?'#426c52':'#648658');
      }
      continue;
    }
    const hospital=n.node_type==='HOSPITAL',bank=n.node_type==='BANK';
    const industrial=['INDUSTRIAL','POWER_PLANT'].includes(n.node_type);
    const floors=industrial?2:hospital?4:bank?9:n.node_type==='SCHOOL'?2:3+seed%10;
    const h=floors*.78,w=industrial?4.5:3.2+(seed%3)*.3,d=industrial?4.2:3.4;
    const tint=hospital?'#e8e7dc':bank?'#8b9eaa':industrial?'#b4a89b':['#c8bbaa','#b8c1c1','#c2ac95','#d5d0c4'][seed%4];
    add('walls',[x,h/2+.15,z],[w,h,d],tint,n.id);
    add('roofs',[x,h+.27,z],[w+.12,.24,d+.12],industrial?'#657477':'#556977');
    add('roofs',[x+.4,h+.6,z-.4],[w*.35,.5,d*.25],'#8b989b');
    if(bank) {
      add('walls',[x,h+1.2,z],[w*.7,1.8,d*.7],'#aec1c5',n.id);
      add('poles',[x,h+3,z],[.06,2,.06],'#a8b8bd');
    }
    // Windows use one instanced batch across the entire city.
    for(let f=0;f<floors;f++) for(let j=0;j<3;j++) {
      const y=.65+f*.78,c=(seed+f+j)%5===0?'#e1d5ac':'#547989';
      add('glass',[x-w/2+.55+j*(w-1.1)/2,y,z+d/2+.012],[.4,.4,.025],c);
      add('glass',[x-w/2+.55+j*(w-1.1)/2,y,z-d/2-.012],[.4,.4,.025],c);
      add('glass',[x+w/2+.012,y,z-d/2+.6+j*(d-1.2)/2],[.025,.4,.4],c);
      add('glass',[x-w/2-.012,y,z-d/2+.6+j*(d-1.2)/2],[.025,.4,.4],c);
    }
    add('glass',[x,.7,z+d/2+.03],[.6,1.1,.04],'#284a59');
    if(hospital) {
      add('marks',[x,h+.42,z],[1.5,.1,.4],'#e45e50');
      add('marks',[x,h+.43,z],[.4,.1,1.5],'#e45e50');
    }
    if(industrial) for(let i=0;i<2;i++) {
      add('walls',[x-1+i*2,h+1,z-1],[.45,2.5,.45],'#8c8c83',n.id);
      add('marks',[x-1+i*2,h+1.9,z-1],[.48,.3,.48],'#b77d65');
    }
    // Simple streetscape, deliberately without hundreds of dynamic lights.
    if(n.id%2===0) {
      add('poles',[n.col*CELL+1.4,1.6,n.row*CELL+1.4],[.06,3.2,.06],'#64777d');
      add('lamps',[n.col*CELL+1.4,3.2,n.row*CELL+1.15],[.3,.1,.65],'#ffdf9d');
    }
  }
  return batches;
}
