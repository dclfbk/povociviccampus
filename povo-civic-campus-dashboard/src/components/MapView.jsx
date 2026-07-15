import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import bbox from '@turf/bbox';
import { indicators, number, quantileBreaks } from '../lib/data';

const CLUSTER_COLORS = ['#1a0dab','#6b5bd2','#2b7a78','#d28537','#8d4b7b','#566573'];
const RAMP = ['#f0efff','#c9c4f5','#9388e2','#5f4bc7','#1a0dab'];

function continuousExpression(breaks, inverse=false) {
  const colors = inverse ? [...RAMP].reverse() : RAMP;
  const stops = [];
  breaks.slice(0,5).forEach((b,i)=>stops.push(b, colors[Math.min(i,colors.length-1)]));
  return ['interpolate',['linear'],['to-number',['get','__value'],0], ...stops];
}

export default function MapView({ sections, services, boundary, campus, isochrones, mode, indicator, selectedProfiles, selectedSectionIds, onSelectSection, origin, minutes, showIsochrones }) {
  const el = useRef(null); const mapRef = useRef(null);

  useEffect(()=>{
    if (!el.current || mapRef.current) return;
    const map = new maplibregl.Map({ container:el.current, style:'https://tiles.openfreemap.org/styles/liberty', center:[11.15,46.067], zoom:13.2 });
    map.addControl(new maplibregl.NavigationControl({showCompass:false}), 'top-right');
    map.on('load',()=>{ if(boundary) { const b=bbox(boundary); map.fitBounds([[b[0],b[1]],[b[2],b[3]]],{padding:35,duration:0}); } });
    mapRef.current=map; return()=>{map.remove();mapRef.current=null};
  },[]);

  useEffect(()=>{
    const map=mapRef.current; if(!map || !map.loaded() || !sections) return;
    const ready=()=>{
      const data={...sections,features:sections.features.map(f=>({...f,properties:{...f.properties,__value:Number(f.properties?.[indicator])||0,__id:String(f.properties?.SEZ21_ID ?? f.properties?.SEZ21)}}))};
      if(map.getSource('sections')) map.getSource('sections').setData(data); else map.addSource('sections',{type:'geojson',data,promoteId:'__id'});
      ['sections-fill','sections-outline'].forEach(id=>{if(map.getLayer(id))map.removeLayer(id)});
      const meta=indicators[indicator];
      let fill;
      if(meta?.kind==='categorical') fill=['match',['get',indicator],...Object.keys(data.features.reduce((a,f)=>(a[f.properties[indicator]]=1,a),{})).flatMap((k,i)=>[k,CLUSTER_COLORS[i%CLUSTER_COLORS.length]]),'#ccc'];
      else fill=continuousExpression(quantileBreaks(data.features,indicator,5),meta?.inverse);
      map.addLayer({id:'sections-fill',type:'fill',source:'sections',paint:{'fill-color':fill,'fill-opacity':mode==='services'?0.12:0.66}});
      map.addLayer({id:'sections-outline',type:'line',source:'sections',paint:{'line-color':['case',['in',['get','__id'],['literal',selectedSectionIds]],'#111827','#ffffff'],'line-width':['case',['in',['get','__id'],['literal',selectedSectionIds]],2.5,0.8]}});
      const filter=selectedProfiles.length?['in',['get','profilo_pubblico'],['literal',selectedProfiles]]:null;
      map.setFilter('sections-fill',filter); map.setFilter('sections-outline',filter);
      map.off('click','sections-fill'); map.on('click','sections-fill',e=>{const f=e.features?.[0]; if(f) onSelectSection?.(f.properties.__id,f.properties)});
      map.off('mousemove','sections-fill'); map.on('mousemove','sections-fill',()=>map.getCanvas().style.cursor='pointer');
      map.off('mouseleave','sections-fill'); map.on('mouseleave','sections-fill',()=>map.getCanvas().style.cursor='');
    };
    map.isStyleLoaded()?ready():map.once('load',ready);
  },[sections,indicator,mode,selectedProfiles,selectedSectionIds]);

  useEffect(()=>{
    const map=mapRef.current; if(!map || !map.loaded() || !services) return;
    const ready=()=>{
      if(map.getSource('services')) map.getSource('services').setData(services); else map.addSource('services',{type:'geojson',data:services});
      if(map.getLayer('services'))map.removeLayer('services');
      map.addLayer({id:'services',type:'circle',source:'services',layout:{visibility:mode==='services'?'visible':'none'},paint:{'circle-radius':['interpolate',['linear'],['to-number',['get','indice_civico_score'],0],0,4,100,10],'circle-color':['match',['get','categoria_indice_civico'],'Presidio civico ad alta intensità','#1a0dab','Servizio civico-relazionale','#6b5bd2','Servizio di utilità territoriale','#2b7a78','#d28537'],'circle-stroke-color':'#fff','circle-stroke-width':1.4}});
      map.off('click','services'); map.on('click','services',e=>{const p=e.features?.[0]?.properties||{}; new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<strong>${p.nome||'Servizio'}</strong><br>${p.mapcategory||''}<br>Indice civico: ${number(p.indice_civico_score,1)}`).addTo(map)});
    }; map.isStyleLoaded()?ready():map.once('load',ready);
  },[services,mode]);

  useEffect(()=>{
    const map=mapRef.current; if(!map || !campus) return;
    const ready=()=>{
      if(map.getSource('campus'))map.getSource('campus').setData(campus);else map.addSource('campus',{type:'geojson',data:campus});
      if(map.getLayer('campus'))map.removeLayer('campus');
      map.addLayer({id:'campus',type:'circle',source:'campus',layout:{visibility:mode==='accessibility'?'visible':'none'},paint:{'circle-radius':7,'circle-color':'#111827','circle-stroke-color':'#fff','circle-stroke-width':2}});
    }; map.isStyleLoaded()?ready():map.once('load',ready);
  },[campus,mode]);

  useEffect(()=>{
    const map=mapRef.current; if(!map || !isochrones) return;
    const ready=()=>{
      if(map.getSource('isochrones'))map.getSource('isochrones').setData(isochrones);else map.addSource('isochrones',{type:'geojson',data:isochrones});
      ['iso-fill','iso-line'].forEach(id=>{if(map.getLayer(id))map.removeLayer(id)});
      map.addLayer({id:'iso-fill',type:'fill',source:'isochrones',layout:{visibility:mode==='accessibility'&&showIsochrones?'visible':'none'},filter:['all',['==',['get','origine'],origin],['==',['to-number',['get','minuti']],minutes]],paint:{'fill-color':'#1a0dab','fill-opacity':0.24}});
      map.addLayer({id:'iso-line',type:'line',source:'isochrones',layout:{visibility:mode==='accessibility'&&showIsochrones?'visible':'none'},filter:['all',['==',['get','origine'],origin],['==',['to-number',['get','minuti']],minutes]],paint:{'line-color':'#1a0dab','line-width':2}});
    }; map.isStyleLoaded()?ready():map.once('load',ready);
  },[isochrones,mode,origin,minutes,showIsochrones]);

  return <div ref={el} className="map" />;
}
