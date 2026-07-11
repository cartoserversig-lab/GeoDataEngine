import fiona
import geopandas as gpd
from shapely.geometry import Point

from database.geopackage import compile_geopackage


def test_compile_geopackage_names_layers_by_theme(tmp_path):
    processed_dir = tmp_path / "processed"

    (processed_dir / "bd_topo").mkdir(parents=True)
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    ).to_file(processed_dir / "bd_topo" / "batiment.gpkg", driver="GPKG")

    (processed_dir / "adresses").mkdir(parents=True)
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(1, 1)], crs="EPSG:2154"
    ).to_file(processed_dir / "adresses" / "adresses_38348.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gpkg"

    compile_geopackage(processed_dir, output_path)

    layers = set(fiona.listlayers(output_path))
    assert layers == {"bd_topo_batiment", "adresses_38348"}


def test_compile_geopackage_skips_empty_layers(tmp_path):
    processed_dir = tmp_path / "processed"
    (processed_dir / "bd_topo").mkdir(parents=True)

    non_empty = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    )
    non_empty.to_file(processed_dir / "bd_topo" / "batiment.gpkg", driver="GPKG")

    empty = gpd.GeoDataFrame({"id": []}, geometry=[], crs="EPSG:2154")
    empty.to_file(processed_dir / "bd_topo" / "vide.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gpkg"

    compile_geopackage(processed_dir, output_path)

    assert fiona.listlayers(output_path) == ["bd_topo_batiment"]
