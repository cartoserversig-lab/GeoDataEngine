import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point, Polygon

from pathlib import Path

from processing.validation import (
    CrsIssue,
    GeometryIssue,
    check_all_vector_layers,
    check_crs_consistency,
    check_vector_layer,
    write_quality_report,
)


def test_check_crs_consistency_all_ok(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    )
    gdf.to_file(tmp_path / "ok.gpkg", driver="GPKG")

    issues = check_crs_consistency(tmp_path, expected_crs="EPSG:2154")

    assert issues == []


def test_check_crs_consistency_detects_vector_mismatch(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(5, 45)], crs="EPSG:4326"
    )
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


# Emprise de test utilisee pour les controles de coherence spatiale
# (evite de dependre de FRANCE_METROPOLITAINE_BOUNDS dans les tests).
_TEST_BOUNDS = (0.0, 0.0, 1_000_000.0, 1_000_000.0)


def test_check_vector_layer_no_issues(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:2154"
    )
    path = tmp_path / "ok.gpkg"
    gdf.to_file(path, driver="GPKG")

    issues = check_vector_layer(path, sane_bounds=_TEST_BOUNDS)

    assert issues == []


def test_check_vector_layer_detects_missing_crs(tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)])
    path = tmp_path / "no_crs.gpkg"
    gdf.to_file(path, driver="GPKG")

    issues = check_vector_layer(path, sane_bounds=_TEST_BOUNDS)

    assert any("coordonnees non identifie" in i.probleme.lower() for i in issues)


def test_check_vector_layer_detects_invalid_geometry(tmp_path):
    # Polygone "papillon" auto-intersectant : geometrie invalide classique.
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bowtie], crs="EPSG:2154")
    path = tmp_path / "invalid.gpkg"
    gdf.to_file(path, driver="GPKG")

    issues = check_vector_layer(path, sane_bounds=_TEST_BOUNDS)

    assert any("invalide" in i.probleme.lower() for i in issues)


def test_check_vector_layer_detects_out_of_bounds(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(50_000_000, 50_000_000)], crs="EPSG:2154"
    )
    path = tmp_path / "far_away.gpkg"
    gdf.to_file(path, driver="GPKG")

    issues = check_vector_layer(path, sane_bounds=_TEST_BOUNDS)

    assert any("hors de l'emprise" in i.probleme.lower() for i in issues)


def test_check_all_vector_layers_handles_multi_layer_gpkg(tmp_path):
    path = tmp_path / "multi.gpkg"
    good = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154")
    good.to_file(path, layer="layer_ok", driver="GPKG")

    bad = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(50_000_000, 0)], crs="EPSG:2154")
    bad.to_file(path, layer="layer_bad", driver="GPKG")

    results = check_all_vector_layers(tmp_path, sane_bounds=_TEST_BOUNDS)

    assert "multi.gpkg::layer_ok" not in results
    assert "multi.gpkg::layer_bad" in results


def test_write_quality_report_ok(tmp_path):
    output_path = tmp_path / "logs" / "rapport.txt"

    write_quality_report([], {}, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "OK : aucune incoherence detectee." in content
    assert "OK : aucun probleme detecte." in content


def test_write_quality_report_with_issues(tmp_path):
    crs_issues = [
        CrsIssue(fichier=Path("a.gpkg"), couche=None, crs_trouve="EPSG:4326", crs_attendu="EPSG:2154")
    ]
    geometry_issues = {
        "b.gpkg": [
            GeometryIssue(fichier=Path("b.gpkg"), couche=None, index=0, probleme="Geometrie invalide")
        ]
    }
    output_path = tmp_path / "logs" / "rapport.txt"

    write_quality_report(crs_issues, geometry_issues, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "a.gpkg" in content
    assert "EPSG:4326" in content
    assert "b.gpkg" in content
    assert "Geometrie invalide" in content
