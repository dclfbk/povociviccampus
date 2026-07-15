# POI + Popular Times per zona (GeoJSON)

Dato un GeoJSON con il poligono di una zona (es. la circoscrizione di Povo),
lo script estrae tutti i POI interni e per ciascuno recupera i **Popular
Times** di Google Maps: affluenza per giorno della settimana e ora (scala
0–100), affluenza live corrente, tempo medio di permanenza/attesa, rating.

> **Importante — "numero di persone":** Google non fornisce mai conteggi
> assoluti. I valori sono percentuali relative al picco del singolo luogo
> (100 = ora di punta di *quel* posto). Nessuna libreria o API può darti il
> numero di persone reale.
>
> **Nota legale:** i Popular Times non sono esposti dall'API ufficiale
> Google Places; si ottengono via scraping (zona grigia rispetto ai ToS di
> Google — cfr. issue #90 di m-wrzr/populartimes). Usa pause generose e
> volumi contenuti.

## Installazione

```bash
pip install shapely requests
pip install --upgrade git+https://github.com/GrocerCheck/LivePopularTimes
```

## Uso

### Modalità 1 — Overpass/OSM (default, gratuita, senza chiave)

I POI vengono presi da OpenStreetMap (Overpass API), filtrati
punto-nel-poligono, e per ciascuno si cerca la scheda Google per
`nome + indirizzo`:

```bash
python3 poi_popular_times.py circoscrizione.geojson \
    --city-hint "Povo, Trento" \
    --outdir output_povo
```

`--city-hint` è usato come indirizzo di ripiego per i POI OSM senza
`addr:*`, e migliora molto il matching su Google.

### Modalità 2 — Google Places (richiede API key, più completa)

Copre il poligono con una griglia esagonale di Nearby Search (~93 celle con
raggio 300 m su Povo), deduplica per `place_id`, filtra nel poligono e poi
recupera i popular times per ogni `place_id` (matching perfetto, nessuna
ambiguità di nome):

```bash
python3 poi_popular_times.py circoscrizione.geojson \
    --mode google --api-key "$GOOGLE_KEY" --radius 300 \
    --outdir output_povo
```

Attenzione ai costi: ogni cella è almeno una chiamata Nearby Search
(fatturabile oltre la quota mensile gratuita), più una "Find Place" per POI
per i popular times.

### Opzioni utili

| Opzione | Descrizione |
|---|---|
| `--limit 10` | processa solo i primi 10 POI (per testare) |
| `--skip-populartimes` | solo censimento POI, senza popular times |
| `--categories amenity shop` | limita le chiavi OSM interrogate |
| `--sleep 3` | pausa tra richieste popular times (default 2 s) |
| `--radius 250` | raggio celle Nearby Search in modalità google |

## Output

- `places.csv` — un POI per riga: id, nome, categoria, indirizzo,
  coordinate, rating, n. recensioni, affluenza live, permanenza media,
  flag `has_populartimes`
- `popular_times_long.csv` — formato lungo pronto per pandas/analisi:
  `source_id, name, day, day_it, hour (0–23), popularity_percent (0–100)`
- `places.geojson` — i POI georiferiti con i popular times nelle
  properties (caricabile in QGIS, Folium, uMap…)

## Note pratiche

- Molti POI di paese (piccoli negozi, uffici) **non hanno** popular times:
  Google li calcola solo dove ha abbastanza dati di localizzazione. Su una
  zona come Povo aspettati dati per bar, ristoranti, supermercati, palestre,
  poli universitari — non per tutto.
- La modalità Overpass dipende dalla qualità del matching nome→scheda
  Google: qualche falso negativo è fisiologico. La modalità Google con
  `place_id` è più affidabile.
- Overpass ha rate limit pubblici: se la query fallisce, riprova o usa un
  altro endpoint (es. `overpass.kumi.systems`).
