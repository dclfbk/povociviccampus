from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.mask import mask

DTM_CRS = CRS.from_epsg(25832)

dtm_files = sorted(Path("../data/").glob("dtm*_wor.tif"))
boundary_path = Path("../data/circoscrizione.geojson")

# Confine della Circoscrizione
boundary = gpd.read_file(boundary_path)
boundary = boundary.to_crs(DTM_CRS)

datasets = []

for path in dtm_files:
    src = rasterio.open(path)

    # I file hanno coordinate corrette ma non dichiarano il CRS.
    if src.crs is None:
        vrt = rasterio.vrt.WarpedVRT(src, crs=DTM_CRS)
        datasets.append(vrt)
    elif src.crs != DTM_CRS:
        raise ValueError(
            f"{path.name}: CRS inatteso {src.crs}; previsto EPSG:25832"
        )
    else:
        datasets.append(src)

mosaic, mosaic_transform = merge(datasets)
