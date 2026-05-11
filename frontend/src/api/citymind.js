import api from "./client";

// GET /state
export const getState = async () => {
  const res = await api.get("/state");
  return res.data;
};

// GET /graph
export const getGraph = async () => {
  const res = await api.get("/graph");
  return res.data;
};

// POST /start
export const startSimulation = async () => {
  const res = await api.post("/start");
  return res.data;
};

// POST /step
export const stepSimulation = async () => {
  const res = await api.post("/simulation/step");
  return res.data;
};
