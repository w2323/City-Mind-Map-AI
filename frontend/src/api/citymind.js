import api from './client';
export const getState = async () => (await api.get('/state')).data;
export const getGraph = async () => (await api.get('/graph')).data;
export const startSimulation = async () => (await api.post('/start',undefined,{timeout:45000})).data;
export const stepSimulation = async () => (await api.post('/simulation/step')).data;
export const changeRoad = async (action, a, b) => (await api.post(`/simulation/${action}_road/${a}/${b}`)).data;
export const unleashGate = async (node_id, intensity) => (await api.post('/simulation/disasters/gate', { node_id, intensity })).data;
export const clearGates = async () => (await api.post('/simulation/disasters/gates/clear')).data;
export const previewGate = async (node_id, intensity, signal) => (await api.post('/simulation/disasters/gate/preview', {node_id,intensity}, {signal})).data;
export const helicopterAction = async (action, payload) => (await api.post(`/simulation/helicopter/${action}`, payload)).data;
export const dispatchEmergency = async node => (await api.post('/simulation/emergencies', {node})).data;
export const addMedicalCenter = async node => (await api.post('/simulation/medical_centers', {node})).data;
export const calculateRoute = async (src, dst, travel_mode, signal) => (await api.post('/simulation/route', {src, dst, travel_mode}, {signal})).data;
export const cityEventSettings = async settings => (await api.post('/simulation/events/settings',settings)).data;
export const policeAction = async (action, payload) => {
  const path = action === 'medical' ? `reports/${payload.report_id}/medical_rescue` :
    ({report:'reports',settings:'settings',plan:'stations/plan',station:'stations',compare:'compare'})[action];
  if (!path) throw new Error('Unknown police action');
  return (await api.post(`/simulation/police/${path}`,action==='medical'?undefined:payload,{timeout:action==='compare'?90000:action==='plan'?60000:15000})).data;
};
export const getAmbulanceRoutes = async (id, signal) => (await api.get(`/simulation/ambulance_routes/${id}`, { signal })).data;
export const optimization = async (action, runs) => (await api.post(`/simulation/optimization/${action}`, action === 'start' ? { runs } : undefined)).data;
export async function exportMetrics() {
  const { data } = await api.get('/metrics/export', { responseType: 'blob' });
  const url = URL.createObjectURL(data);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'citymind-metrics.csv';
  a.click();
  URL.revokeObjectURL(url);
}
