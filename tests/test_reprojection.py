import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point

from processing.reprojection import reproject_raster, reproject_to_target_crs, reproject_vector


def test_reproject_vector(tmp_path):
    path = tmp_path / "points.gpkg"
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(5, 45)], crs="EPSG:4326")
    gdf.to_file(path, driver="GPKG")

    reproject_vector(path, target_crs="EPSG:2154")

    result = gpd.read_file(path)
    assert result.crs.to_string() == "EPSG:2154"


def test_reproject_raster(tmp_path):
    path = tmp_path / "raster.tif"
    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": rasterio.transform.from_bounds(0, 40, 1, 41, 2, 2),
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.zeros((1, 2, 2), dtype="uint8"))

    reproject_raster(path, target_crs="EPSG:2154")

    with rasterio.open(path) as src:
        assert src.crs.to_string() == "EPSG:2154"


def test_reproject_to_target_crs_dispatches_by_extension(tmp_path):
    path = tmp_path / "points.gpkg"
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(5, 45)], crs="EPSG:4326")
    gdf.to_file(path, driver="GPKG")

    reproject_to_target_crs(path, target_crs="EPSG:2154")

    result = gpd.read_file(path)
    assert result.crs.to_string() == "EPSG:2154"
