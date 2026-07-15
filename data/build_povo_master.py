#!/usr/bin/env python3
"""Prepara e aggiorna il dataset master dei servizi di Povo.

Fase locale (sempre disponibile):
- importa il CSV della Circoscrizione;
- aggiunge campi di provenienza, verifica e matching;
- esporta CSV e GeoJSON master;
- genera template per candidati esterni.

Fase online (opzionale):
- --osm-json: importa un JSON Overpass già scaricato;
- --overture-geojson: importa un GeoJSON Overture places già estratto;
- confronta i punti esterni con il master per distanza e somiglianza del nome.

Il programma non promuove automaticamente i record esterni a servizi confermati.
"""
from __future__ import annotations

import argparse, csv, json, math, re, unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from datetime import date
from typing import Any

from shapely.geometry import Point, shape, mapping


def norm(s: Any) -> str:
    s = '' if s is None else str(s)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1); dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))


def read_csv(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def load_boundary(path: Path):
    obj=json.load(path.open(encoding='utf-8'))
    geoms=[shape(f['geometry']) for f in obj.get('features',[]) if f.get('geometry')]
    if not geoms: raise ValueError('Confine privo di geometrie')
    from shapely.ops import unary_union
    return unary_union(geoms)


def base_rows(csv_path: Path, boundary):
    rows=read_csv(csv_path)
    today=date.today().isoformat()
    out=[]
    for i,r in enumerate(rows,1):
        lat=float(r['latitudine']); lon=float(r['longitudine'])
        inside=boundary.covers(Point(lon,lat))
        x=dict(r)
        x.update({
            'id_povo': f'POVO-CIRC-{i:04d}',
            'fonte_principale':'Circoscrizione di Povo',
            'fonti_riscontro':'',
            'id_osm':'', 'id_overture':'',
            'stato_match':'record_base', 'match_con':'', 'match_score':'', 'distanza_match_m':'',
            'verifica_locale':'confermato_dalla_circoscrizione',
            'qualita_record':'alta' if inside else 'da_controllare_fuori_confine',
            'data_estrazione_esterna':'',
            'data_ultima_verifica': r.get('data_aggiornamento','') or today,
            'dentro_confine_povo': str(bool(inside)).lower(),
        })
        out.append(x)
    return out


def osm_elements(path: Path, boundary):
    obj=json.load(path.open(encoding='utf-8'))
    out=[]
    for e in obj.get('elements',[]):
        tags=e.get('tags',{})
        if 'lat' in e: lat,lon=e['lat'],e['lon']
        elif 'center' in e: lat,lon=e['center']['lat'],e['center']['lon']
        else: continue
        if not boundary.covers(Point(lon,lat)): continue
        name=tags.get('name') or tags.get('brand') or tags.get('operator') or ''
        if not name: continue
        cat=';'.join(f'{k}={tags[k]}' for k in ('amenity','shop','leisure','tourism','office','craft','healthcare') if k in tags)
        out.append({'external_source':'OSM','external_id':f"{e.get('type')}/{e.get('id')}",'nome':name,'categoria_esterna':cat,
                    'latitudine':lat,'longitudine':lon,'indirizzo':tags.get('addr:street','')+' '+tags.get('addr:housenumber',''),
                    'url':tags.get('website') or tags.get('contact:website') or '', 'raw':json.dumps(tags,ensure_ascii=False)})
    return out


def overture_features(path: Path, boundary):
    obj=json.load(path.open(encoding='utf-8'))
    out=[]
    for f in obj.get('features',[]):
        g=shape(f['geometry'])
        p=g if g.geom_type=='Point' else g.representative_point()
        if not boundary.covers(p): continue
        pr=f.get('properties',{})
        names=pr.get('names') or {}
        name=names.get('primary') if isinstance(names,dict) else ''
        if not name: name=pr.get('name','')
        if not name: continue
        cats=pr.get('categories') or {}
        if isinstance(cats,dict): cat=cats.get('primary','')
        else: cat=str(cats)
        out.append({'external_source':'Overture','external_id':str(pr.get('id') or f.get('id') or ''),'nome':name,
                    'categoria_esterna':cat,'latitudine':p.y,'longitudine':p.x,
                    'indirizzo':str(pr.get('addresses') or ''),'url':'','raw':json.dumps(pr,ensure_ascii=False)})
    return out


def match_external(ext, base):
    best=None
    for b in base:
        d=haversine_m(float(ext['latitudine']),float(ext['longitudine']),float(b['latitudine']),float(b['longitudine']))
        ns=SequenceMatcher(None,norm(ext['nome']),norm(b['nome'])).ratio()
        # score: name dominates under 150 m; very close points receive a spatial bonus
        spatial=max(0.0,1.0-d/250.0)
        score=0.72*ns+0.28*spatial
        if best is None or score>best[0]: best=(score,d,b)
    score,d,b=best
    if d<=40 and score>=0.72: status='corrispondenza_probabile'
    elif d<=100 and score>=0.55: status='da_verificare_possibile_match'
    else: status='nuovo_candidato'
    x=dict(ext)
    x.update({'stato_match':status,'match_con':b['id_povo'],'match_nome':b['nome'],
              'match_score':round(score,3),'distanza_match_m':round(d,1),
              'verifica_locale':'da_verificare','qualita_record':'candidato_esterno'})
    return x


def to_geojson(rows,path):
    feats=[]
    for r in rows:
        try: lat=float(r['latitudine']); lon=float(r['longitudine'])
        except: continue
        feats.append({'type':'Feature','properties':{k:v for k,v in r.items() if k not in ('latitudine','longitudine')},
                      'geometry':{'type':'Point','coordinates':[lon,lat]}})
    json.dump({'type':'FeatureCollection','features':feats},path.open('w',encoding='utf-8'),ensure_ascii=False,indent=2)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--master-csv',required=True,type=Path)
    ap.add_argument('--boundary',required=True,type=Path)
    ap.add_argument('--out-dir',required=True,type=Path)
    ap.add_argument('--osm-json',type=Path)
    ap.add_argument('--overture-geojson',type=Path)
    args=ap.parse_args(); args.out_dir.mkdir(parents=True,exist_ok=True)
    boundary=load_boundary(args.boundary)
    base=base_rows(args.master_csv,boundary)
    base_fields=list(base[0].keys())
    write_csv(args.out_dir/'povo_servizi_master_base.csv',base,base_fields)
    to_geojson(base,args.out_dir/'povo_servizi_master_base.geojson')

    ext=[]
    if args.osm_json: ext += osm_elements(args.osm_json,boundary)
    if args.overture_geojson: ext += overture_features(args.overture_geojson,boundary)
    matched=[match_external(e,base) for e in ext]
    ext_fields=['external_source','external_id','nome','categoria_esterna','latitudine','longitudine','indirizzo','url',
                'stato_match','match_con','match_nome','match_score','distanza_match_m','verifica_locale','qualita_record','raw']
    write_csv(args.out_dir/'povo_poi_esterni_confrontati.csv',matched,ext_fields)
    to_geojson(matched,args.out_dir/'povo_poi_esterni_confrontati.geojson')

    summary={
      'record_base':len(base), 'record_base_fuori_confine':sum(r['dentro_confine_povo']=='false' for r in base),
      'record_esterni':len(matched), 'corrispondenze_probabili':sum(r['stato_match']=='corrispondenza_probabile' for r in matched),
      'possibili_match':sum(r['stato_match']=='da_verificare_possibile_match' for r in matched),
      'nuovi_candidati':sum(r['stato_match']=='nuovo_candidato' for r in matched)
    }
    json.dump(summary,(args.out_dir/'sintesi_aggiornamento.json').open('w'),ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__': main()
