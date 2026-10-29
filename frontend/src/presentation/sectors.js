// Display metadata only. Existing backend node types, IDs and routes are unchanged.
export const SECTORS = {
  RESIDENTIAL: {name:'Residential sector', description:'Homes, apartments and local services.'},
  BANK: {name:'Financial sector', description:'Banks, jewellery shops and valuable businesses.'},
  HOSPITAL: {name:'Medical sector', description:'Hospitals, clinics and pharmacies.'},
  POLICE: {name:'Police services sector', description:'Police and related public-safety services.'},
  SCHOOL: {name:'Education sector', description:'Schools and related education services.'},
  INDUSTRIAL: {name:'Industrial sector', description:'Factories, warehouses and industrial activity.'},
  POWER_PLANT: {name:'Energy sector', description:'Power generation and utility services.'},
  AMBULANCE_DEPOT: {name:'Medical depot sector', description:'Ambulance and emergency support services.'},
  EMPTY: {name:'Open-space sector', description:'Parks, public space or undeveloped land.'},
};
export const sectorInfo = type => SECTORS[type] || {name:`${type} sector`, description:'Mixed sector activity.'};
export const sectorText = message => String(message).replace(/\b(nodes?|cells)\b/gi, word => {
  const replacement=word.toLowerCase()==='cells'?'sector units':word.toLowerCase()==='nodes'?'sectors':'sector';
  return word===word.toUpperCase()?replacement.toUpperCase():word[0]===word[0].toUpperCase()?replacement[0].toUpperCase()+replacement.slice(1):replacement;
});
