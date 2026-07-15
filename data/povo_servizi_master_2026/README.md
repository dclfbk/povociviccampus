# Dataset master dei servizi di Povo

## File prodotti

- `povo_servizi_master_base.csv`: i 41 record forniti dalla Circoscrizione, con campi di provenienza, verifica e matching.
- `povo_servizi_master_base.geojson`: versione geografica pronta per QGIS e uMap.
- `povo_poi_esterni_confrontati.csv`: risultati del confronto con OSM/Overture; nella prima esecuzione è vuoto finché non si forniscono gli estratti esterni.
- `povo_poi_esterni_confrontati.geojson`: equivalente geografico.
- `sintesi_aggiornamento.json`: conteggi di controllo.
- `query_osm_povo.overpassql`: query per scaricare i POI attuali da OpenStreetMap.
- `build_povo_master.py`: pipeline riproducibile per importare e confrontare OSM e Overture.

## Regola di pubblicazione

I dati della Circoscrizione restano la base autorevole locale. I punti OSM e Overture sono candidati o riscontri: non vengono aggiunti automaticamente tra i servizi confermati senza verifica.

## Esecuzione dopo il download delle fonti esterne

```bash
python build_povo_master.py \
  --master-csv povo_umap_tutti_i_servizi_con_calcoli.csv \
  --boundary circoscrizione.geojson \
  --osm-json osm_povo_overpass.json \
  --overture-geojson overture_places_povo.geojson \
  --out-dir output
```

## Significato di `stato_match`

- `corrispondenza_probabile`: punto molto vicino e nome compatibile;
- `da_verificare_possibile_match`: possibile duplicato o variante del nome;
- `nuovo_candidato`: nessuna corrispondenza sufficientemente forte;
- `record_base`: record originario della Circoscrizione.
