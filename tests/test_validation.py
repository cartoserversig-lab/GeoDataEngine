import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point

from processing.validation import check_crs_consistency


def test_check_crs_consistency_all_ok(tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154")
    gdf.to_file(tmp_path / "ok.gpkg", driver="GPKG")

    issues = check_crs_consistency(tmp_path, expected_crs="EPSG:2154")

    assert issues == []


def test_check_crs_consistency_detects_vector_mismatch(tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(5, 45)], crs="EPSG:4326")
    gdf.to_file(tmp_path / "mismatch.gpkg", driver="GPKG")

    issues = check_crs_consistency(tmp_path, expected_crs="EPSG:2154")

    assert len(issues) == 1
    assert issues[0].crs_trouve == "EPSG:4326"
    assert issues[0].crs_attendu == "EPSG:2154"


def test_check_crs_consistency_detects_raster_mismatch(tmp_path):
    data = np.zeros((1, 2, 2), dtype="uint8")
    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 1,
        "dtype": "uint8",
        "crs": "EPSG:4326",
        "transform": rasterio.transform.from_bounds(0, 0, 1, 1, 2, 2),
    }
    path = tmp_path / "mismatch.tif"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    issues = check_crs_consistency(tmp_path, expected_crs="EPSG:2154")

    assert len(issues) == 1
    assert issues[0].crs_trouve == "EPSG:4326"
