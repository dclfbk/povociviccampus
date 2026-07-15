# Povo Civic Campus — Pipeline di accessibilità

Tre script in sequenza, pensati per la cartella `scripts/` del repository
(con i dati grezzi in `data/` e gli output in `data/processed/`; i percorsi
si cambiano nelle costanti `DATA_DIR` / `OUT_DIR` in testa a ogni script).

```
pip install geopandas networkx rasterio matplotlib

python 01_grafo_accessibilita.py   # grafo pedonale + tempi da FBK/UniTn
python 02_matrice_quadranti.py     # bacino residenti + quadranti
python 03_mappa.py                 # mappa di sintesi PNG
```

## Cosa fa ogni step

**01 — Grafo e tempi.** Filtra la rete OSM (`osm_line2.geojson`) ai soli
tipi percorribili a piedi, densifica i segmenti ogni ~25 m, campiona la
quota sul DEM 1 m (`povo.tif`, EPSG:25832) e costruisce un grafo **diretto**:
ogni segmento produce due archi con tempi diversi, perché la velocità di
cammino segue la funzione di Tobler (`6·e^(−3.5·|s+0.05|)` km/h, con le
scalinate limitate a 1,8 km/h). Poi Dijkstra da FBK e dal Polo UniTn e
classificazione dei 41 servizi in fasce di tempo.
→ `servizi_accessibilita_fbk.csv`, `graph.pkl`

**02 — Quadranti.** Per ogni servizio calcola la popolazione residente
(ISTAT 2021, centroidi delle sezioni di censimento) che lo raggiunge in
10/15 minuti, usando il grafo inverso così la pendenza è nella direzione
giusta (residente → servizio). Incrocia bacino residenti, tempo da FBK e
`funzione_relazionale_calcolata` del CSV della circoscrizione per assegnare
il quadrante: PONTE ATTIVO, PONTE POTENZIALE, Prossimità residenziale,
Orbita campus, Margine.
→ `matrice_quadranti.csv`, `servizi_quadranti.gpkg`

**03 — Mappa.** Rete colorata per minuti da FBK, densità residenti in
grigio, servizi simbolizzati per quadrante.
→ `mappa_accessibilita_povo.png`

## Parametri e scelte da dichiarare (azione 17 del TODO)

- Soglie dei quadranti: ≤10 min da FBK e ≥2.000 residenti nel bacino
  (`T_MAX_CITYUSERS`, `POP_SOGLIA` nello step 02). Sono discrezionali:
  vale la pena un'analisi di sensibilità.
- Il bacino residenti usa i **centroidi** di sezione: nelle sezioni grandi
  sottostima. Miglioria prevista: dasymetric mapping distribuendo POP21
  sugli edifici di `osm_poly.geojson`.
- La "penalità pendenza" confronta Tobler con una baseline piatta a
  4,5 km/h: su percorsi favorevoli può risultare negativa (Tobler in
  leggera discesa supera i 5 km/h).
- Origini FBK/UniTn: coordinate puntuali degli ingressi principali; per
  un'analisi più fine si possono usare più ingressi per campus.
- Lo snap servizio→nodo è al nodo più vicino in linea d'aria; la colonna
  `snap_m` nello step 01 permette di controllare i casi anomali.

## Dati di input attesi in `DATA_DIR`

| File | Fonte | Uso |
|---|---|---|
| `osm_line2.geojson` | OpenStreetMap | rete pedonale |
| `povo.tif` | DEM 1 m (EPSG:25832) | pendenze |
| `povo_umap_tutti_i_servizi_con_calcoli.csv` | Circoscrizione | 41 servizi |
| `sezioni_censimento.geojson` | ISTAT 2021 | popolazione |
| `circoscrizione.geojson` | Comune di Trento | perimetro (solo mappa) |
