"""
Povo Civic Campus — Step 3: mappa di sintesi.

Disegna la mappa statica dell'analisi: rete pedonale colorata per minuti
da FBK (media andata/ritorno, corretti per pendenza), sezioni di
censimento in grigio per densita' abitativa, servizi simbolizzati per
quadrante, marker su FBK e UniTn.

Richiede gli output degli step 1 e 2 (graph.pkl, servizi_quadranti.gpkg).

Output (OUT_DIR): mappa_accessibilita_povo.png
"""

import pickle
import warnings

import geopandas as gpd
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from pyproj import Transformer

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------- parametri
DATA_DIR = "data"
OUT_DIR = "data/processed"
CRS = "EPSG:25832"
T_CAP = 25  # minuti oltre i quali il colore satura

ORIGINS_WGS = {"FBK": (11.15153, 46.06722), "UniTn/DISI": (11.14980, 46.06700)}

STYLES = {
    "PONTE ATTIVO": ("#7b1fa2", "*", 340),
    "PONTE POTENZIALE": ("#1565c0", "P", 200),
    "Orbita campus": ("#e65100", "o", 70),
    "Prossimita' residenziale": ("#2e7d32", "s", 90),
    "Margine": ("#616161", "x", 70),
}


def main() -> None:
    with open(f"{OUT_DIR}/graph.pkl", "rb") as f:
        G, t_out, t_back = pickle.load(f)

    circ = gpd.read_file(f"{DATA_DIR}/circoscrizione.geojson").to_crs(CRS)
    sez = gpd.read_file(f"{DATA_DIR}/sezioni_censimento.geojson").to_crs(CRS)
    sez["dens"] = sez.POP21 / (sez.geometry.area / 10_000)  # abitanti/ettaro
    serv = gpd.read_file(f"{OUT_DIR}/servizi_quadranti.gpkg")

    # archi colorati per tempo medio da FBK
    segs, tvals = [], []
    for u, v in G.edges():
        tu = (t_out.get(u, np.nan) + t_back.get(u, np.nan)) / 2
        tv = (t_out.get(v, np.nan) + t_back.get(v, np.nan)) / 2
        t = np.nanmean([tu, tv])
        if np.isfinite(t):
            segs.append([u, v])
            tvals.append(min(t, T_CAP))

    fig, ax = plt.subplots(figsize=(13, 14), dpi=150)
    sez.plot(ax=ax, column="dens", cmap="Greys", alpha=0.45, vmin=0, vmax=60)
    circ.boundary.plot(ax=ax, color="#333", lw=1.4, ls="--")

    lc = LineCollection(segs, cmap="RdYlGn_r", norm=plt.Normalize(0, T_CAP), linewidths=1.1)
    lc.set_array(np.array(tvals))
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, shrink=0.5, pad=0.01)
    cb.set_label("Minuti a piedi da FBK (media andata/ritorno, corretti per pendenza)")

    for q, (c, m, s) in STYLES.items():
        sub = serv[serv.quadrante == q]
        if len(sub):
            ax.scatter(
                sub.geometry.x, sub.geometry.y, c=c, marker=m, s=s,
                edgecolors="white" if m != "x" else None, linewidths=0.7,
                zorder=5, label=f"{q} ({len(sub)})",
            )

    tr = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    for i, (name, (lon, lat)) in enumerate(ORIGINS_WGS.items()):
        x, y = tr.transform(lon, lat)
        if i == 0:
            ax.scatter([x], [y], marker="^", s=420, c="#b71c1c", edgecolors="white", zorder=6)
            ax.annotate(name, (x, y), textcoords="offset points", xytext=(10, 8),
                        fontsize=12, fontweight="bold", color="#b71c1c")
        else:
            ax.annotate(name, (x, y), textcoords="offset points", xytext=(-72, -14),
                        fontsize=10, color="#b71c1c")

    minx, miny, maxx, maxy = circ.total_bounds
    ax.set_xlim(minx - 150, maxx + 150)
    ax.set_ylim(miny - 150, maxy + 150)
    ax.set_axis_off()
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9, title="Quadrante servizio")
    ax.set_title(
        "Povo Civic Campus — Accessibilita' pedonale da FBK e spazi ponte\n"
        "rete pesata per pendenza (Tobler, DEM 1 m) · grigio: densita' residenti ISTAT 2021",
        fontsize=13,
    )
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/mappa_accessibilita_povo.png", bbox_inches="tight")
    print(f"Mappa salvata in {OUT_DIR}/mappa_accessibilita_povo.png")


if __name__ == "__main__":
    main()
