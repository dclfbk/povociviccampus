"""
Povo Civic Campus — Step 1
Grafo pedonale pesato per pendenza e tempi di cammino da FBK/UniTn.

Input (cartella DATA):
  - osm_line2.geojson       rete stradale/pedonale OSM
  - povo.tif                DEM 1 m, EPSG:25832 (ETRS89 / UTM 32N)
  - povo_umap_tutti_i_servizi_con_calcoli.csv   41 servizi della circoscrizione

Output (cartella OUT):
  - servizi_accessibilita_fbk.csv   tempi/fasce per servizio
  - graph.pkl                       grafo + tempi da FBK (per gli step successivi)

Metodo:
  1. Filtro della rete alle tipologie percorribili a piedi.
  2. Densificazione dei segmenti a ~25 m e campionamento quota dal DEM.
  3. Grafo DIRETTO: salita e discesa hanno costi diversi.
  4. Velocità con funzione di Tobler: v = 6 * exp(-3.5 * |pendenza + 0.05|) km/h.
     Le scalinate (highway=steps) sono limitate a 1.8 km/h.
  5. Dijkstra dalle origini (FBK, UniTn/DISI) in andata e ritorno.

Uso:
  python 01_grafo_accessibilita.py
"""
import pickle
import warnings

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from shapely.geometry import Point

warnings.filterwarnings("ignore")

# --- Configurazione -------------------------------------------------------
DATA = "/mnt/user-data/uploads"      # adattare al repo: data/raw
OUT = "/home/claude/povo"            # adattare al repo: data/processed
CRS = "EPSG:25832"

WALKABLE = {
    "footway", "path", "steps", "pedestrian", "residential", "service",
    "track", "unclassified", "tertiary", "secondary", "living_street",
    "cycleway",
}

# Origini in WGS84 (lon, lat)
ORIGINS_WGS = {
    "FBK": (11.15153, 46.06722),     # FBK, via Sommarive 18
    "UniTn": (11.14980, 46.06700),   # Polo Ferrari / DISI
}

STEP_M = 25          # passo di densificazione lungo i segmenti
STEPS_KMH = 1.8      # velocità massima sulle scalinate
FLAT_KMH = 4.5       # baseline "terreno piatto" per confronto
BANDS = [0, 5, 10, 15, 20, np.inf]
LABELS = ["0-5 min", "5-10 min", "10-15 min", "15-20 min", ">20 min"]


def tobler_kmh(slope: float) -> float:
    """Velocità di cammino (km/h) secondo la Tobler hiking function."""
    return 6.0 * np.exp(-3.5 * abs(slope + 0.05))


def main() -> None:
    # --- Dati -------------------------------------------------------------
    net = gpd.read_file(f"{DATA}/osm_line2.geojson").to_crs(CRS)
    net = net[net.highway.isin(WALKABLE)].copy()

    serv = pd.read_csv(f"{DATA}/povo_umap_tutti_i_servizi_con_calcoli.csv")
    serv_g = gpd.GeoDataFrame(
        serv,
        geometry=[Point(xy) for xy in zip(serv.longitudine, serv.latitudine)],
        crs="EPSG:4326",
    ).to_crs(CRS)

    dem = rasterio.open(f"{DATA}/povo.tif")

    def elev(xs, ys):
        vals = np.array([v[0] for v in dem.sample(zip(xs, ys))], dtype=float)
        vals[vals <= 0] = np.nan  # 0 = nodata implicito nel raster
        return vals

    # --- Grafo diretto ------------------------------------------------------
    G = nx.DiGraph()
    for _, row in net.iterrows():
        line = row.geometry
        is_steps = row.highway == "steps"
        n_pts = max(2, int(line.length // STEP_M) + 1)
        pts = [line.interpolate(d) for d in np.linspace(0, line.length, n_pts)]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        zs = elev(xs, ys)
        for i in range(len(pts) - 1):
            a = (round(xs[i], 1), round(ys[i], 1))
            b = (round(xs[i + 1], 1), round(ys[i + 1], 1))
            d = float(np.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]))
            if d < 0.5:
                continue
            dz = (
                0.0
                if (np.isnan(zs[i]) or np.isnan(zs[i + 1]))
                else float(zs[i + 1] - zs[i])
            )
            for u, v, ddz in [(a, b, dz), (b, a, -dz)]:
                v_kmh = tobler_kmh(ddz / d)
                if is_steps:
                    v_kmh = min(v_kmh, STEPS_KMH)
                t = (d / 1000.0) / v_kmh * 60.0          # minuti, pendenza
                t_flat = (d / 1000.0) / FLAT_KMH * 60.0  # minuti, piatto
                if G.has_edge(u, v):
                    if t < G[u][v]["t"]:
                        G[u][v].update(t=t, t_flat=t_flat, d=d)
                else:
                    G.add_edge(u, v, t=t, t_flat=t_flat, d=d)

    # componente connessa principale
    comp = max(nx.weakly_connected_components(G), key=len)
    G = G.subgraph(comp).copy()
    nodes = np.array(list(G.nodes))
    print(f"Grafo: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi diretti")

    def nearest_node(x, y):
        i = int(np.argmin((nodes[:, 0] - x) ** 2 + (nodes[:, 1] - y) ** 2))
        return tuple(nodes[i])

    tr = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    origins = {
        k: nearest_node(*tr.transform(lon, lat))
        for k, (lon, lat) in ORIGINS_WGS.items()
    }

    # --- Dijkstra andata + ritorno -----------------------------------------
    results = {}
    for name, o in origins.items():
        t_out = nx.single_source_dijkstra_path_length(G, o, weight="t")
        t_back = nx.single_source_dijkstra_path_length(
            G.reverse(copy=False), o, weight="t"
        )
        t_flat = nx.single_source_dijkstra_path_length(G, o, weight="t_flat")
        d_m = nx.single_source_dijkstra_path_length(G, o, weight="d")
        results[name] = (t_out, t_back, t_flat, d_m)

    # --- Servizi: snap e classificazione -----------------------------------
    rows = []
    for _, r in serv_g.iterrows():
        n = nearest_node(r.geometry.x, r.geometry.y)
        snap_d = float(np.hypot(n[0] - r.geometry.x, n[1] - r.geometry.y))
        rec = dict(
            nome=r["nome"],
            categoria=r["mapcategory"],
            utenza=r["utenza_prevalente_calcolata"],
            funzione=r["funzione_relazionale_calcolata"],
            natura=r["natura_calcolata"],
            snap_m=round(snap_d, 1),
        )
        for name, (t_out, t_back, t_flat, d_m) in results.items():
            rec[f"t_{name}_andata"] = round(t_out.get(n, np.nan), 1)
            rec[f"t_{name}_ritorno"] = round(t_back.get(n, np.nan), 1)
            rec[f"t_{name}_piatto"] = round(t_flat.get(n, np.nan), 1)
            rec[f"dist_{name}_m"] = round(d_m.get(n, np.nan))
        rows.append(rec)

    df = pd.DataFrame(rows)
    df["t_FBK_medio"] = ((df.t_FBK_andata + df.t_FBK_ritorno) / 2).round(1)
    df["fascia_FBK"] = pd.cut(df.t_FBK_medio, BANDS, labels=LABELS)
    df["penalita_pendenza_%"] = (
        (df.t_FBK_medio / df.t_FBK_piatto - 1) * 100
    ).round(0)

    df = df.sort_values("t_FBK_medio")
    df.to_csv(f"{OUT}/servizi_accessibilita_fbk.csv", index=False)
    print(df.fascia_FBK.value_counts().sort_index().to_string())

    with open(f"{OUT}/graph.pkl", "wb") as f:
        pickle.dump((G, results["FBK"][0], results["FBK"][1]), f)
    print(f"Salvati: {OUT}/servizi_accessibilita_fbk.csv, {OUT}/graph.pkl")


if __name__ == "__main__":
    main()
