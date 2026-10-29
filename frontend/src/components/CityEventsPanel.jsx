import SettingRange from './SettingRange';
export default function CityEventsPanel({events={},busy,onChange,onPlay}) {
  const settings=events.settings || {};
  async function change(payload) {
    if(await onChange(payload)) {
      if(Object.entries(payload).some(([k,v])=>k.endsWith('enabled') && v===true))onPlay();
    }
  }
  return <section aria-label="Automatic city events" style={{position:'fixed',top:80,left:18,zIndex:120,width:350,maxHeight:'80vh',overflowY:'auto',padding:18,background:'#111e31',border:'1px solid #38bdf8',borderRadius:12,color:'white',fontSize:13}}>
    <h2>Automatic city events</h2>
    <p>Playback generates real medical calls, crime reports and temporary road closures. Pause playback to freeze the city.</p>
    <button disabled={busy} onClick={()=>change({enabled:!events.enabled})}>{events.enabled?'Pause automatic events':'Enable all automatic events'}</button>
    {[['medical_enabled','Medical emergencies','medical_probability'],['crime_enabled','Crime reports','crime_probability'],['roads_enabled','Road closures','road_probability']].map(([key,label,rate])=><div key={key} style={{padding:'12px 0',borderBottom:'1px solid #334155'}}>
      <label><input type="checkbox" checked={!!settings[key]} disabled={busy} onChange={e=>change({[key]:e.target.checked})} /> {label}</label>
      <SettingRange label={`${label} chance`} value={settings[rate] || 0} onCommit={value=>change({[rate]:value})}/>
    </div>)}
    <p>Generated: {events.generated_medical || 0} medical · {events.generated_crimes || 0} crime · {events.generated_road_closures || 0} closures</p>
    <p>{events.active_road_closures?.length || 0}/{events.max_road_closures || 3} temporary closures active. They expire after {events.road_duration_steps?.join('–') || '8–15'} steps.</p>
    <p>Existing calls continue and scheduled roads reopen after automatic events are switched off. Manual closures and Gate restrictions remain under your control.</p>
  </section>;
}
