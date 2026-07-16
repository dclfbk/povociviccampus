import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import bbox from '@turf/bbox';
import { indicators, number, quantileBreaks } from '../lib/data';

const INITIAL_CENTER = [11.1505, 46.0670];
const INITIAL_ZOOM = 13.7;
const CIVIC_COLORS = {
  'Presidio civico ad alta intensità': '#1a0dab',
  'Servizio civico-relazionale': '#6656d8',
  'Servizio di utilità territoriale': '#2b7a78',
  'Servizio prevalentemente funzionale/attrattivo': '#d28537',
};
const CATEGORY_ICONS = {
  'Servizi pubblici e di comunità': 'building',
  'Cultura, socialità e spazi comuni': 'people',
  'Patrimonio, memoria e fontane': 'landmark',
  'Commercio e servizi di prossimità': 'shop',
  'Ristorazione e agriturismi': 'food',
};
const ICON_SVG = {
  building: '<path d="M5 21h14M7 21V9h10v12M9 12h2v2H9zm4 0h2v2h-2zM9 16h2v2H9zm4 0h2v2h-2zM6 9l6-5 6 5"/>',
  people: '<circle cx="9" cy="8" r="3"/><circle cx="16" cy="9" r="2.5"/><path d="M3.5 20c.4-4 2.4-6 5.5-6s5.1 2 5.5 6M14 15c3.5-.3 5.5 1.5 6 5"/>',
  landmark: '<path d="M3 9h18M5 9v9M9 9v9M15 9v9M19 9v9M3 18h18M2 21h20M12 3l9 4H3z"/>',
  shop: '<path d="M4 10v10h16V10M3 10l2-6h14l2 6M8 20v-6h5v6"/><path d="M3 10c1 2 3 2 4 0 1 2 3 2 4 0 1 2 3 2 4 0 1 2 3 2 4 0"/>',
  food: '<path d="M7 3v8M4 3v5c0 2 1 3 3 3s3-1 3-3V3M7 11v10M16 3c3 3 3 8 0 10v8M16 3v10"/>',
};
const RAMP = ['#f0efff','#c9c4f5','#9388e2','#5f4bc7','#1a0dab'];

function serviceId(feature){
  const p=feature.properties||{};
  return String(feature.id ?? p.fsq_place_id ?? p.id ?? `${p.nome||'poi'}-${feature.geometry?.coordinates?.join('-')||''}`);
}

function markerHtml(category, color) {
  const icon = ICON_SVG[CATEGORY_ICONS[category]] || ICON_SVG.landmark;
  return `<div class="poi-pin" style="--pin:${color}"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${icon}</svg></div>`;
}

function continuousExpression(breaks, inverse=false) {
  const colors = inverse ? [...RAMP].reverse() : RAMP;
  const stops = [];
  breaks.slice(0,5).forEach((b,i)=>stops.push(b, colors[Math.min(i,colors.length-1)]));
  return ['interpolate',['linear'],['to-number',['get','__value'],0], ...stops];
}

export default function MapView({ mode, sections, services, boundary, indicator, selectedProfiles=[], selectedSectionIds=[], selectedPoiIds=[], onSelectSection, onTogglePoi }) {
  const el = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);

  useEffect(()=>{
    if (!el.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: el.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: INITIAL_CENTER,
      zoom: INITIAL_ZOOM,
      minZoom: INITIAL_ZOOM - 2,
      maxZoom: 18,
      attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl({showCompass:false}), 'top-right');
    mapRef.current = map;
    return ()=>{ markersRef.current.forEach(m=>m.remove()); map.remove(); mapRef.current=null; };
  },[]);

  useEffect(()=>{
    const map=mapRef.current;
    if(!map || !boundary) return;
    const ready=()=>{
      if(map.getSource('boundary')) map.getSource('boundary').setData(boundary);
      else map.addSource('boundary',{type:'geojson',data:boundary});
      ['boundary-halo','boundary-line'].forEach(id=>{if(map.getLayer(id))map.removeLayer(id)});
      map.addLayer({id:'boundary-halo',type:'line',source:'boundary',paint:{'line-color':'#ffffff','line-width':6,'line-opacity':0.95}});
      map.addLayer({id:'boundary-line',type:'line',source:'boundary',paint:{'line-color':'#111111','line-width':3.2,'line-dasharray':[2.5,1.5]}});
      const b=bbox(boundary);
      map.setMaxBounds([[b[0]-0.035,b[1]-0.025],[b[2]+0.035,b[3]+0.025]]);
      map.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:45,duration:0,maxZoom:INITIAL_ZOOM});
    };
    map.isStyleLoaded()?ready():map.once('load',ready);
  },[boundary]);

  useEffect(()=>{
    const map=mapRef.current;
    if(!map || !sections) return;
    const ready=()=>{
      const data={...sections,features:sections.features.map(f=>({...f,properties:{...f.properties,__value:Number(f.properties?.[indicator])||0,__id:String(f.properties?.SEZ21_ID ?? f.properties?.SEZ21)}}))};
      if(map.getSource('sections')) map.getSource('sections').setData(data); else map.addSource('sections',{type:'geojson',data});
      ['sections-fill','sections-outline'].forEach(id=>{if(map.getLayer(id))map.removeLayer(id)});
      const meta=indicators[indicator];
      const cats=[...new Set(data.features.map(f=>f.properties?.[indicator]).filter(Boolean))];
      const colors=['#1a0dab','#6b5bd2','#2b7a78','#d28537','#8d4b7b','#566573'];
      const fill=meta?.kind==='categorical'
        ? ['match',['get',indicator],...cats.flatMap((k,i)=>[k,colors[i%colors.length]]),'#d5d8df']
        : continuousExpression(quantileBreaks(data.features,indicator,5),meta?.inverse);
      map.addLayer({id:'sections-fill',type:'fill',source:'sections',layout:{visibility:mode==='sections'?'visible':'none'},paint:{'fill-color':fill,'fill-opacity':0.68}},'boundary-halo');
      map.addLayer({id:'sections-outline',type:'line',source:'sections',layout:{visibility:mode==='sections'?'visible':'none'},paint:{'line-color':['case',['in',['get','__id'],['literal',selectedSectionIds]],'#111827','#ffffff'],'line-width':['case',['in',['get','__id'],['literal',selectedSectionIds]],3,0.8]}},'boundary-halo');
      const filter=selectedProfiles.length?['in',['get','profilo_pubblico'],['literal',selectedProfiles]]:null;
      map.setFilter('sections-fill',filter); map.setFilter('sections-outline',filter);
      map.off('click','sections-fill'); map.on('click','sections-fill',e=>{const f=e.features?.[0]; if(f) onSelectSection?.(f.properties.__id,f.properties)});
      map.off('mousemove','sections-fill'); map.on('mousemove','sections-fill',()=>map.getCanvas().style.cursor='pointer');
      map.off('mouseleave','sections-fill'); map.on('mouseleave','sections-fill',()=>map.getCanvas().style.cursor='');
    };
    map.isStyleLoaded()?ready():map.once('load',ready);
  },[sections,indicator,mode,selectedProfiles,selectedSectionIds,onSelectSection]);

  useEffect(()=>{
    const map=mapRef.current;
    if(!map || !services) return;
    markersRef.current.forEach(m=>m.remove());
    markersRef.current=[];
    if(mode!=='services') return;
    services.features.forEach(feature=>{
      const p=feature.properties||{};
      const id=serviceId(feature);
      const selected=selectedPoiIds.includes(id);
      const color=CIVIC_COLORS[p.categoria_indice_civico]||'#52606d';
      const node=document.createElement('button');
      node.className=`poi-marker${selected?' selected':''}`;
      node.type='button';
      node.title=p.nome||'Punto di interesse';
      node.innerHTML=markerHtml(p.mapcategory,color);
      node.addEventListener('click',e=>{
        e.stopPropagation();
        onTogglePoi?.(id,p);
        new maplibregl.Popup({offset:22,maxWidth:'320px'})
          .setLngLat(feature.geometry.coordinates)
          .setHTML(`<div class="poi-popup"><strong>${p.nome||'Servizio'}</strong><span>${p.mapcategory||'Categoria non indicata'}</span><dl><dt>Profilo civico</dt><dd>${p.categoria_indice_civico||'–'}</dd><dt>Indice civico</dt><dd>${number(p.indice_civico_score,1)}</dd><dt>Natura</dt><dd>${p.natura_calcolata||'–'}</dd><dt>Utenza</dt><dd>${p.utenza_prevalente_calcolata||'–'}</dd></dl></div>`)
          .addTo(map);
      });
      const marker=new maplibregl.Marker({element:node,anchor:'bottom'}).setLngLat(feature.geometry.coordinates).addTo(map);
      markersRef.current.push(marker);
    });
  },[services,mode,selectedPoiIds,onTogglePoi]);

  return <div ref={el} className="map" />;
}
