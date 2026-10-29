import {useEffect,useRef,useState} from 'react';

// Drag locally; commit once when released. Slow API steps never fight the thumb.
export default function SettingRange({label,value,onCommit,disabled=false}) {
  const [draft,setDraft]=useState(value),[saving,setSaving]=useState(false);
  const editing=useRef(false),sent=useRef(value);
  useEffect(()=>{if(!editing.current&&!saving){setDraft(value);sent.current=value;}},[value,saving]);
  async function commit() {
    editing.current=false;
    if(sent.current===draft)return;
    sent.current=draft;setSaving(true);
    try {await onCommit(draft);} finally {setSaving(false);}
  }
  return <label>{label} · {Math.round(draft*100)}%
    <input aria-label={label} type="range" min="0" max="100" value={Math.round(draft*100)} disabled={disabled} onChange={e=>{editing.current=true;setDraft(Number(e.target.value)/100);}} onPointerUp={commit} onKeyUp={commit} onBlur={commit}/>
    {saving&&<small role="status">Saving setting…</small>}
  </label>;
}
