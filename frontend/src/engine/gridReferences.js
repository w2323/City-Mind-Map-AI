export const toDisplayNode=node=>({...node,row:node.col,col:node.row});
export const toDisplayAir=air=>air?.position?{...air,position:[air.position[1],air.position[0]]}:air;
export function gridLetter(index) {
  let label='';
  do {label=String.fromCharCode(65+index%26)+label;index=Math.floor(index/26)-1;} while(index>=0);
  return label;
}
export function gridReferences(numberCount,letterCount) {
  const entries=[],right=(numberCount-1)*8+12,bottom=(letterCount-1)*8+12;
  for(let i=0;i<numberCount;i++)for(const z of [-7,bottom])entries.push({x:i*8,z,text:String(i+1)});
  for(let i=0;i<letterCount;i++)for(const x of [-7,right])entries.push({x,z:i*8,text:gridLetter(i)});
  return entries;
}
