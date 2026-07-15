import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView';
import Stats from './components/Stats';
import ChartPanel from './components/ChartPanel';
import ServiceChart from './components/ServiceChart';
import { indicators, loadJson, number } from './lib/data';

const TABS=[['overview','Panoramica'],['sections','Sezioni'],['services','Servizi'],['clusters','Cluster'],['accessibility','Accessibilità']];

export default function App(){
 const [data,setData]=useState({}); const [error,setError]=useState('');
 const [tab,setTab]=useState('overview'); const [indicator,setIndicator]=useState('popolazione_rif');
 const [aggregate,setAggregate]=useState('popolazione_rif'); const [profiles,setProfiles]=useState([]);
 const [selectedIds,setSelectedIds]=useState([]); const [selectedProps,setSelectedProps]=useState(null);
 const [origin,setOrigin]=useState('fbk'); const [minutes,setMinutes]=useState(10); const [showIso,setShowIso]=useState(false);
 useEffect(()=>{Promise.all([
  loadJson('./data/sezioni.geojson'),loadJson('./data/servizi.geojson'),loadJson('./data/confine.geojson'),loadJson('./data/campus.json'),loadJson('./data/isocrone.geojson')
 ]).then(([sections,services,boundary,campus,isocrones])=>setData({sections,services,boundary,campus,isocrones})).catch(e=>setError(e.message))},[]);
 const sections=data.sections?.features||[]; const services=data.services?.features||[];
 const visibleSections=useMemo(()=>profiles.length?sections.filter(f=>profiles.includes(f.properties?.profilo_pubblico)):sections,[sections,profiles]);
 const mode=tab==='services'?'services':tab==='accessibility'?'accessibility':'sections';
 function toggleProfile(name){setProfiles(p=>p.includes(name)?p.filter(x=>x!==name):[name]);}
 function selectSection(id,props){setSelectedIds(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);setSelectedProps(props)}
 if(error)return <div className="fatal">Errore: {error}</div>;
 if(!data.sections)return <div className="loading">Caricamento dati territoriali…</div>;
 return <div className="app">
  <header className="site-header"><div><h1>Povo Civic Campus</h1><p>Servizi, popolazione, accessibilità e profili sociofunzionali</p></div></header>
  <nav className="tabs">{TABS.map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}</button>)}</nav>
  <main>
   <Stats sections={visibleSections} services={services}/>
   <section className="workspace">
    <div className="map-shell">
     <div className="map-toolbar">
      {tab!=='services'&&tab!=='accessibility'&&<label>Indicatore<select value={indicator} onChange={e=>setIndicator(e.target.value)}>{Object.entries(indicators).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></label>}
      {tab==='accessibility'&&<><label>Origine<select value={origin} onChange={e=>setOrigin(e.target.value)}><option value="fbk">FBK</option><option value="povo0">Povo 0</option><option value="povo1">Povo 1</option><option value="povo2">Povo 2</option></select></label><div className="segmented">{[5,10,15].map(m=><button className={minutes===m?'active':''} onClick={()=>setMinutes(m)} key={m}>{m} min</button>)}</div><label className="check"><input type="checkbox" checked={showIso} onChange={e=>setShowIso(e.target.checked)}/> Mostra isocrona</label></>}
      <button className="reset" onClick={()=>{setProfiles([]);setSelectedIds([]);setSelectedProps(null)}}>Azzera selezione</button>
     </div>
     <MapView {...data} mode={mode} indicator={tab==='clusters'?'profilo_pubblico':indicator} selectedProfiles={profiles} selectedSectionIds={selectedIds} onSelectSection={selectSection} origin={origin} minutes={minutes} showIsochrones={showIso}/>
     {tab==='accessibility'&&data.isocrones.features.length===0&&<div className="map-note">Le coordinate degli ingressi sono attive. Il layer delle 12 isocrone sarà visualizzato appena viene aggiunto il file <code>public/data/isocrone.geojson</code>.</div>}
    </div>
    <aside className="side-panel">
      {tab==='services'?<><div className="panel-title"><span>Servizi e indice civico</span><strong>{services.length}</strong></div><ServiceChart services={services}/></>:
       tab==='accessibility'?<><div className="panel-title"><span>Accessibilità pedonale</span><strong>{minutes} min</strong></div><p className="lead">Confronto dagli ingressi dei campus. Le isocrone sono previste a 5, 10 e 15 minuti e potranno essere calcolate con penalizzazione della pendenza.</p><div className="origin-list">{data.campus.features.map(f=><div key={f.properties.id}><b>{f.properties.nome}</b><span>{f.geometry.coordinates[1].toFixed(6)}, {f.geometry.coordinates[0].toFixed(6)}</span></div>)}</div></>:
       <><div className="panel-title"><span>Profili sociofunzionali</span><strong>{visibleSections.length}</strong></div><label>Aggrega per<select value={aggregate} onChange={e=>setAggregate(e.target.value)}><option value="popolazione_rif">Abitanti</option><option value="famiglie_rif">Famiglie</option><option value="abitazioni_rif">Abitazioni</option><option value="sezioni">Numero di sezioni</option></select></label><ChartPanel features={sections} activeIndicator={indicator} aggregate={aggregate} onCategoryClick={toggleProfile}/></>}
      {selectedProps&&<div className="detail"><h3>Sezione {selectedProps.SEZ21_ID||selectedProps.SEZ21}</h3><dl><dt>Profilo</dt><dd>{selectedProps.profilo_pubblico||'–'}</dd><dt>Abitanti</dt><dd>{number(selectedProps.popolazione_rif)}</dd><dt>Famiglie</dt><dd>{number(selectedProps.famiglie_rif)}</dd><dt>Servizi entro 5 min</dt><dd>{number(selectedProps.servizi_5_min)}</dd><dt>Servizi entro 15 min</dt><dd>{number(selectedProps.servizi_15_min)}</dd><dt>Tempo alla fermata</dt><dd>{number(selectedProps.tempo_fermata_min,1)} min</dd></dl></div>}
    </aside>
   </section>
  </main>
  <footer>Progetto sperimentale di analisi territoriale · dati e metodologia</footer>
 </div>
}
