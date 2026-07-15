import { useEffect, useMemo, useState } from 'react';
import MapView from './components/MapView';
import DistributionChart from './components/DistributionChart';
import { indicators, loadJson, number, sum } from './lib/data';

const TABS=[['services','Servizi e luoghi'],['sections','Sezioni e territorio'],['method','Dati e metodologia']];
const SERVICE_DIMENSIONS = {
  category: { field:'mapcategory', label:'Categoria' },
  civic: { field:'categoria_indice_civico', label:'Profilo civico' },
  nature: { field:'natura_calcolata', label:'Natura' },
  users: { field:'utenza_prevalente_calcolata', label:'Utenza' },
};

function unique(features, field){ return [...new Set(features.map(f=>f.properties?.[field]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'it')); }
function rows(features, field){
  const counts={};
  features.forEach(f=>{const k=f.properties?.[field]||'Non classificato';counts[k]=(counts[k]||0)+1});
  return Object.entries(counts).map(([label,value])=>({label,value}));
}
function filterServices(features, filters, ignored=null){
  return features.filter(f=>Object.entries(SERVICE_DIMENSIONS).every(([key,meta])=>{
    if(key===ignored || !filters[key].length) return true;
    return filters[key].includes(f.properties?.[meta.field]||'Non classificato');
  }));
}

export default function App(){
  const [data,setData]=useState({});
  const [error,setError]=useState('');
  const [tab,setTab]=useState('services');
  const [indicator,setIndicator]=useState('profilo_pubblico');
  const [profiles,setProfiles]=useState([]);
  const [selectedIds,setSelectedIds]=useState([]);
  const [selectedProps,setSelectedProps]=useState(null);
  const [selectedPoi,setSelectedPoi]=useState(null);
  const [filters,setFilters]=useState({category:[],civic:[],nature:[],users:[]});

  useEffect(()=>{Promise.all([
    loadJson('data/sezioni.geojson'),loadJson('data/servizi.geojson'),loadJson('data/confine.geojson')
  ]).then(([sections,services,boundary])=>setData({sections,services,boundary})).catch(e=>setError(e.message))},[]);

  const sections=data.sections?.features||[];
  const allServices=data.services?.features||[];
  const visibleServices=useMemo(()=>filterServices(allServices,filters),[allServices,filters]);
  const visibleSections=useMemo(()=>profiles.length?sections.filter(f=>profiles.includes(f.properties?.profilo_pubblico)):sections,[sections,profiles]);
  const activeFilterCount=Object.values(filters).reduce((n,v)=>n+v.length,0);

  function toggleFilter(key,value){
    setFilters(current=>({...current,[key]:current[key].includes(value)?current[key].filter(v=>v!==value):[...current[key],value]}));
  }
  function resetFilters(){setFilters({category:[],civic:[],nature:[],users:[]});setSelectedPoi(null)}
  function toggleProfile(name){setProfiles(p=>p.includes(name)?p.filter(x=>x!==name):[...p,name]);}
  function selectSection(id,props){setSelectedIds([id]);setSelectedProps(props)}
  function distributionFor(key){return rows(filterServices(allServices,filters,key),SERVICE_DIMENSIONS[key].field)}

  if(error)return <div className="fatal">Errore: {error}</div>;
  if(!data.sections)return <div className="loading">Caricamento dati territoriali…</div>;

  return <div className="app">
    <header className="site-header">
      <div className="eyebrow">Analisi territoriale interattiva</div>
      <h1>Povo Civic Campus</h1>
      <p>Servizi, luoghi e struttura sociofunzionale della Circoscrizione di Povo</p>
      <div className="data-dates"><span>Servizi: rilevazione 2026</span><span>Dati demografici: 2023</span></div>
    </header>
    <nav className="tabs" aria-label="Sezioni della dashboard">{TABS.map(([id,label])=><button key={id} className={tab===id?'active':''} onClick={()=>setTab(id)}>{label}</button>)}</nav>

    <main>
      {tab==='services'&&<>
        <section className="context-block">
          <div><div className="eyebrow">Vista principale</div><h2>Servizi e luoghi della Circoscrizione</h2><p>La mappa localizza i punti di interesse censiti nel 2026. <b>La forma dell’icona</b> identifica la categoria, mentre <b>il colore</b> rappresenta il profilo dell’indice civico. Grafici, filtri e mappa sono collegati: ogni selezione aggiorna l’intera vista.</p></div>
          <div className="reading-key"><b>Come leggere la vista</b><span>Icona → categoria del servizio</span><span>Colore → profilo civico</span><span>Barra percentuale → composizione</span><span>Barre ordinate → valori assoluti</span><span>Tratteggio nero → confine circoscrizionale</span></div>
        </section>
        <section className="kpi-grid">
          <article><strong>{visibleServices.length}</strong><span>servizi mostrati su {allServices.length}</span></article>
          <article><strong>{new Set(visibleServices.map(f=>f.properties.mapcategory)).size}</strong><span>categorie visibili</span></article>
          <article><strong>{number(visibleServices.reduce((a,f)=>a+(Number(f.properties.indice_civico_score)||0),0)/(visibleServices.length||1),1)}</strong><span>indice civico medio</span></article>
          <article><strong>{activeFilterCount}</strong><span>filtri attivi</span></article>
        </section>
        <section className="filter-summary">
          <div><b>Stai osservando:</b> {visibleServices.length} di {allServices.length} servizi</div>
          <div className="chips">{Object.entries(filters).flatMap(([key,values])=>values.map(v=><button key={`${key}-${v}`} onClick={()=>toggleFilter(key,v)}>{SERVICE_DIMENSIONS[key].label}: {v} ×</button>))}{activeFilterCount===0&&<span>Nessun filtro applicato</span>}</div>
          {activeFilterCount>0&&<button className="clear-all" onClick={resetFilters}>Rimuovi tutti i filtri</button>}
        </section>
        <section className="service-workspace">
          <div className="map-shell">
            <div className="map-toolbar filter-toolbar">
              {Object.entries(SERVICE_DIMENSIONS).map(([key,meta])=><label key={key}>{meta.label}<select value="" onChange={e=>{if(e.target.value)toggleFilter(key,e.target.value)}}><option value="">Tutti</option>{unique(allServices,meta.field).map(v=><option key={v} value={v}>{v}</option>)}</select></label>)}
              <button className="reset" onClick={resetFilters} disabled={!activeFilterCount}>Azzera filtri</button>
            </div>
            <MapView mode="services" services={{...data.services,features:visibleServices}} sections={data.sections} boundary={data.boundary} indicator={indicator} onSelectPoi={setSelectedPoi}/>
            <div className="map-legend">
              <b>Profilo civico</b>
              <span><i style={{background:'#1a0dab'}}/>Presidio civico ad alta intensità</span>
              <span><i style={{background:'#6656d8'}}/>Servizio civico-relazionale</span>
              <span><i style={{background:'#2b7a78'}}/>Utilità territoriale</span>
              <span><i style={{background:'#d28537'}}/>Funzionale / attrattivo</span>
            </div>
          </div>
          <aside className="map-context">
            <h3>Cosa stai vedendo</h3>
            <p>I punti mostrati rispettano contemporaneamente tutti i filtri attivi. Selezioni multiple nella stessa dimensione sono alternative; filtri di dimensioni diverse si combinano.</p>
            {selectedPoi?<div className="detail"><div className="eyebrow">POI selezionato</div><h3>{selectedPoi.nome}</h3><dl><dt>Categoria</dt><dd>{selectedPoi.mapcategory||'–'}</dd><dt>Profilo civico</dt><dd>{selectedPoi.categoria_indice_civico||'–'}</dd><dt>Indice</dt><dd>{number(selectedPoi.indice_civico_score,1)}</dd><dt>Natura</dt><dd>{selectedPoi.natura_calcolata||'–'}</dd><dt>Utenza</dt><dd>{selectedPoi.utenza_prevalente_calcolata||'–'}</dd><dt>Funzione relazionale</dt><dd>{selectedPoi.funzione_relazionale_calcolata||'–'}</dd></dl></div>:<div className="empty-detail">Seleziona un punto sulla mappa per leggerne la scheda.</div>}
          </aside>
        </section>
        <section className="charts-grid">
          <DistributionChart title="Distribuzione dei servizi per categoria" description="Numero di punti di interesse per categoria. Clicca una barra o un segmento per filtrare la mappa." rows={distributionFor('category')} selected={filters.category} onToggle={v=>toggleFilter('category',v)}/>
          <DistributionChart title="Distribuzione per profilo civico" description="Il profilo civico sintetizza natura, utenza e funzione relazionale del servizio." rows={distributionFor('civic')} selected={filters.civic} onToggle={v=>toggleFilter('civic',v)}/>
          <DistributionChart title="Natura dei soggetti che offrono i servizi" description="Confronto fra soggetti pubblici, privati, associativi e forme miste." rows={distributionFor('nature')} selected={filters.nature} onToggle={v=>toggleFilter('nature',v)}/>
          <DistributionChart title="A chi si rivolgono i servizi" description="Distinzione fra servizi rivolti prevalentemente ai residenti, ai city users o a entrambe le popolazioni." rows={distributionFor('users')} selected={filters.users} onToggle={v=>toggleFilter('users',v)}/>
        </section>
      </>}

      {tab==='sections'&&<>
        <section className="context-block compact"><div><div className="eyebrow">Analisi territoriale</div><h2>Sezioni di censimento e profili sociofunzionali</h2><p>Questa vista descrive la struttura demografica e funzionale del territorio attraverso le sezioni di censimento. <b>I dati demografici sono riferiti al 2023.</b></p></div></section>
        <section className="kpi-grid"><article><strong>{visibleSections.length}</strong><span>sezioni mostrate</span></article><article><strong>{number(sum(visibleSections,'popolazione_rif'))}</strong><span>abitanti (2023)</span></article><article><strong>{number(sum(visibleSections,'famiglie_rif'))}</strong><span>famiglie (2023)</span></article><article><strong>{number(sum(visibleSections,'abitazioni_rif'))}</strong><span>abitazioni (2023)</span></article></section>
        <section className="section-workspace">
          <div className="map-shell"><div className="map-toolbar"><label>Indicatore<select value={indicator} onChange={e=>setIndicator(e.target.value)}>{Object.entries(indicators).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></label><button className="reset" onClick={()=>{setProfiles([]);setSelectedIds([]);setSelectedProps(null)}}>Azzera selezione</button></div><MapView mode="sections" sections={data.sections} services={data.services} boundary={data.boundary} indicator={indicator} selectedProfiles={profiles} selectedSectionIds={selectedIds} onSelectSection={selectSection}/></div>
          <aside className="map-context"><h3>Contesto della vista</h3><p>Ogni poligono è una sezione di censimento. La colorazione dipende dall’indicatore selezionato; scegliendo il profilo sociofunzionale vengono mostrate le quattro tipologie territoriali individuate dall’analisi.</p><p className="note-2023">Dati demografici: anno 2023.</p>{selectedProps&&<div className="detail"><h3>Sezione {selectedProps.SEZ21_ID||selectedProps.SEZ21}</h3><dl><dt>Profilo</dt><dd>{selectedProps.profilo_pubblico||'–'}</dd><dt>Abitanti (2023)</dt><dd>{number(selectedProps.popolazione_rif)}</dd><dt>Famiglie (2023)</dt><dd>{number(selectedProps.famiglie_rif)}</dd><dt>Servizi entro 5 min</dt><dd>{number(selectedProps.servizi_5_min)}</dd><dt>Servizi entro 15 min</dt><dd>{number(selectedProps.servizi_15_min)}</dd></dl></div>}</aside>
        </section>
        <section className="charts-grid one-column"><DistributionChart title="Sezioni per profilo sociofunzionale" description="Numero di sezioni appartenenti a ciascun profilo. Clicca per filtrare la mappa." rows={rows(sections,'profilo_pubblico')} selected={profiles} onToggle={toggleProfile} valueLabel="sezioni"/></section>
      </>}

      {tab==='method'&&<section className="method-page"><div className="eyebrow">Trasparenza</div><h2>Dati e metodologia</h2><p>La dashboard integra fonti con temporalità diverse. I punti di interesse e i servizi sono stati verificati nel 2026; le variabili demografiche associate alle sezioni di censimento si riferiscono al 2023.</p><div className="method-grid"><article><h3>Servizi e luoghi</h3><p>Ogni punto è classificato per categoria, natura del soggetto, utenza prevalente e funzione relazionale. Da queste dimensioni deriva l’indice civico utilizzato per la colorazione.</p></article><article><h3>Sezioni e territorio</h3><p>I profili sociofunzionali derivano dall’elaborazione congiunta di variabili demografiche, territoriali, di accesso ai servizi e di mobilità.</p></article><article><h3>Interazione</h3><p>I filtri operano con logica AND fra dimensioni diverse e OR fra valori della stessa dimensione. I grafici conservano il contesto della propria dimensione per facilitare il confronto.</p></article></div></section>}
    </main>
    <footer>Povo Civic Campus · dashboard sperimentale · dati demografici 2023 · servizi 2026</footer>
  </div>;
}
