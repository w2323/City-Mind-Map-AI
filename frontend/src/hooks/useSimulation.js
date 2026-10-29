import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getState, startSimulation, stepSimulation, changeRoad, unleashGate, clearGates, optimization, policeAction, helicopterAction, cityEventSettings, dispatchEmergency, addMedicalCenter } from '../api/citymind';
import {shareSnapshot} from '../engine/shareSnapshot';
import {createMutationQueue} from '../engine/mutationQueue';

export function useSimulation() {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connectionError,setConnectionError] = useState(null);
  const [message,setMessage]=useState('');
  const [connected, setConnected] = useState(false);
  const [stepping, setStepping] = useState(false);
  const [starting, setStarting] = useState(false);
  const [acting,setActing] = useState(false);
  const busy = useRef(false);
  const pendingActions=useRef(0),stepPending=useRef(false);
  const queue=useRef(null);
  if(!queue.current)queue.current=createMutationQueue();
  const sequence = useRef(0);
  const mounted = useRef(true);
  const accept = useCallback((data, ticket) => {
    if (mounted.current && ticket === sequence.current) {
      setState(previous=>shareSnapshot(previous,data.state || data));
      setConnected(true);
      setConnectionError(null);
    }
  }, []);
  const loadData = useCallback(async () => {
    if (busy.current) return;
    const ticket = ++sequence.current;
    try {
      accept(await getState(), ticket);
    } catch (err) {
      if (mounted.current && ticket === sequence.current) {
        setConnectionError(err.message || 'Cannot connect to the CityMind backend.');
        setConnected(false);
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [accept]);
  const mutate = useCallback(async (fn, startingAction = false, stepAction = false) => {
    if(stepAction&&(stepPending.current||pendingActions.current))return false;
    if(stepAction){stepPending.current=true;setStepping(true);}
    else {pendingActions.current++;setActing(true);if(startingAction)setStarting(true);}
    busy.current = true;
    try {
      return await queue.current.run(async()=>{
        if(!mounted.current)return false;
        if(!stepAction){setError(null);setMessage('');}
        const ticket=++sequence.current;
        const data=await fn();
        accept(data,ticket);
        if(!stepAction&&mounted.current&&data.message)setMessage(data.message);
        return true;
      });
    } catch (err) {
      if (mounted.current) {
        const detail=err.response?.data?.detail;
        setError(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>item.msg).join('; '):err.message);
      }
      return false;
    } finally {
      if(stepAction){stepPending.current=false;if(mounted.current)setStepping(false);}
      else {pendingActions.current--;if(mounted.current){setActing(pendingActions.current>0);if(startingAction)setStarting(false);}}
      busy.current=stepPending.current||pendingActions.current>0;
    }
  }, [accept]);
  const handleStart = useCallback(() => mutate(startSimulation, true), [mutate]);
  const handleStep = useCallback(() => mutate(stepSimulation,false,true), [mutate]);
  const handleRoad = useCallback((action,a,b) => mutate(() => changeRoad(action,a,b)), [mutate]);
  const handleGate = useCallback((node,intensity) => mutate(() => unleashGate(node,intensity)), [mutate]);
  const handleClearGates = useCallback(() => mutate(clearGates), [mutate]);
  const handlePolice = useCallback((action,payload) => mutate(()=>policeAction(action,payload)),[mutate]);
  const handleHelicopter = useCallback((action, payload) => mutate(()=>helicopterAction(action, payload)),[mutate]);
  const handleDispatch = useCallback(node => mutate(()=>dispatchEmergency(node)),[mutate]);
  const handleCenter = useCallback(node => mutate(()=>addMedicalCenter(node)),[mutate]);
  const handleCityEvents = useCallback(settings => mutate(()=>cityEventSettings(settings)),[mutate]);
  const handleOptimization = useCallback((action, runs = 1) => mutate(() => optimization(action, runs)), [mutate]);
  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    let timer;
    const poll = async () => {
      await loadData();
      if (!cancelled) timer = setTimeout(poll, 1000);
    };
    poll();
    return () => { cancelled = true; mounted.current = false; sequence.current++; clearTimeout(timer); };
  }, [loadData]);
  const stats = useMemo(() => state ? {
    ...state.analysis,
    police: state.police_deployments,
    ambulances: state.ambulances,
    floods: state.flood_events,
    disasters: state.disasters,
    step: state.step,
    maxSteps: state.max_steps,
    isComplete: state.is_complete,
    events: state.events.events,
    metrics: state.events.metrics,
    router: state.router,
    activeRoutes: state.active_routes,
    civiliansRemaining: state.router?.civilians_remaining || [],
    optimization: state.optimization,
    config: state.config,
  } : null, [state]);
  return { state, graph: state?.graph, stats, loading, error:error || connectionError, clearError:()=>setError(null), message,clearMessage:()=>setMessage(''), connected, stepping, starting, acting,
    handleStart, handleStep, handleRoad, handleGate, handleClearGates, handlePolice, handleHelicopter, handleCityEvents, handleDispatch, handleCenter, handleOptimization, loadData };
}
