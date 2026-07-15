"""
Povo Civic Campus — Step 2: bacino residenti e matrice dei quadranti.

Per ogni servizio calcola quanta popolazione residente lo raggiunge a piedi
in 10 e 15 minuti (Dijkstra sul grafo INVERSO: residenti -> servizio, cosi'
la direzione della pendenza e' quella giusta), poi incrocia il bacino
residenti con l'accessibilita' da FBK e con la funzione relazionale del CSV
per classificare ogni luogo in un quadrante:

  PONTE ATTIVO            co-accessibile + funzione relazionale Alta
  PONTE POTENZIALE        co-accessibile + funzione Media/Bassa
  Prossimita' residenziale raggiunto dai residenti ma lontano da FBK
  Orbita campus           vicino a FBK ma bacino residenti sotto soglia
  Margine                 lontano da entrambi i bacini pedonali

Richiede l'output dello step 1 (graph.pkl).

Input  (DATA_DIR): sezioni_censimento.geojson, povo_umap_..._con_calcoli.csv
Input  (OUT_DIR):  graph.pkl
Output (OUT_DIR):  matrice_quadranti.csv, servizi_quadranti.gpkg

NOTA METODOLOGICA: il bacino residenti usa i CENTROIDI delle sezioni di
censimento; nelle sezioni grandi/allungate tende a sottostimare la
popolazione realmente raggiungibile. Le soglie (T_MAX_CITYUSERS,
POP_SOGLIA) sono scelte discrezionali: dichiararle e testarne la
sensibilita' fa parte della documentazione del progetto (azione 17).
"""

import pickle
import warnings

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------- parametri
DATA_DIR = "data"
OUT_DIR = "data/processed"
CRS = "EPSG:25832"

T_MAX_CITYUSERS = 10.0   # min: soglia "raggiungibile da FBK"
T_MAX_RESIDENTI = 10.0   # min: soglia bacino residenti
POP_SOGLIA = 2000        # residenti nel bacino perche' conti "accessibile"
CUTOFF = 15.01           # limite Dijkstra (calcoliamo anche pop_15min)


def main() -> None:
    with open(f"{OUT_DIR}/graph.pkl", "rb") as f:
        G, t_fbk_out, t_fbk_back = pickle.load(f)

    nodes = np.array(list(G.nodes))

    def nearest(x, y):
        i = int(np.argmin((nodes[:, 0] - x) ** 2 + (nodes[:, 1] - y) ** 2))
        return tuple(nodes[i])

    # --- residenti: centroidi delle sezioni popolate, snap alla rete
    sez = gpd.read_file(f"{DATA_DIR}/sezioni_censimento.geojson").to_crs(CRS)
    sez = sez[sez.POP21 > 0].copy()
    sez["node"] = sez.geometry.centroid.apply(lambda p: nearest(p.x, p.y))
    print(f"Sezioni popolate: {len(sez)}, popolazione totale: {sez.POP21.sum()}")

    # --- servizi
    serv = pd.read_csv(f"{DATA_DIR}/povo_umap_tutti_i_servizi_con_calcoli.csv")
    serv_g = gpd.GeoDataFrame(
        serv,
        geometry=[Point(xy) for xy in zip(serv.longitudine, serv.latitudine)],
        crs="EPSG:4326",
    ).to_crs(CRS)
    serv_g["node"] = serv_g.geometry.apply(lambda p: nearest(p.x, p.y))

    # --- bacino residenti per servizio (grafo inverso: origine -> servizio)
    Grev = G.reverse(copy=False)
    pop10, pop15 = [], []
    for n in serv_g.node:
        t = nx.single_source_dijkstra_path_length(Grev, n, weight="t", cutoff=CUTOFF)
        pop10.append(int(sez.loc[sez.node.map(lambda x: t.get(x, 99) <= T_MAX_RESIDENTI), "POP21"].sum()))
        pop15.append(int(sez.loc[sez.node.map(lambda x: t.get(x, 99) <= 15), "POP21"].sum()))
    serv_g["pop_10min"] = pop10
    serv_g["pop_15min"] = pop15

    # --- tempo da FBK: media andata/ritorno (pendenza asimmetrica)
    serv_g["t_FBK"] = serv_g.node.map(
        lambda n: round((t_fbk_out.get(n, np.nan) + t_fbk_back.get(n, np.nan)) / 2, 1)
    )

    # --- quadranti
    serv_g["acc_cityusers"] = serv_g.t_FBK <= T_MAX_CITYUSERS
    serv_g["acc_residenti"] = serv_g.pop_10min >= POP_SOGLIA

    def quadrante(r):
        if r.acc_cityusers and r.acc_residenti:
            if r.funzione_relazionale_calcolata == "Alta":
                return "PONTE ATTIVO"
            return "PONTE POTENZIALE"
        if r.acc_residenti:
            return "Prossimita' residenziale"
        if r.acc_cityusers:
            return "Orbita campus"
        return "Margine"

    serv_g["quadrante"] = serv_g.apply(quadrante, axis=1)

    out = serv_g[
        ["nome", "mapcategory", "t_FBK", "pop_10min", "pop_15min",
         "utenza_prevalente_calcolata", "funzione_relazionale_calcolata",
         "natura_calcolata", "quadrante"]
    ].sort_values(["quadrante", "t_FBK"])

    out.to_csv(f"{OUT_DIR}/matrice_quadranti.csv", index=False)
    serv_g.to_file(f"{OUT_DIR}/servizi_quadranti.gpkg", driver="GPKG")

    print(out.to_string(index=False, max_colwidth=45))
    print("\nQuadranti:", serv_g.quadrante.value_counts().to_dict())


if __name__ == "__main__":
    main()
