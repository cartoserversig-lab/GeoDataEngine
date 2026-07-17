import os
import stat

import fiona
import geopandas as gpd
from shapely.geometry import Point, Polygon

from database.filegdb import compile_filegdb


def test_compile_filegdb_names_layers_by_theme(tmp_path):
    processed_dir = tmp_path / "processed"

    (processed_dir / "bd_topo").mkdir(parents=True)
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    ).to_file(processed_dir / "bd_topo" / "batiment.gpkg", driver="GPKG")

    (processed_dir / "adresses").mkdir(parents=True)
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(1, 1)], crs="EPSG:2154"
    ).to_file(processed_dir / "adresses" / "adresses_38348.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gdb"

    compile_filegdb(processed_dir, output_path)

    layers = set(fiona.listlayers(str(output_path)))
    assert layers == {"bd_topo_batiment", "adresses_38348"}


def test_compile_filegdb_skips_empty_layers(tmp_path):
    processed_dir = tmp_path / "processed"
    (processed_dir / "bd_topo").mkdir(parents=True)

    non_empty = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    )
    non_empty.to_file(processed_dir / "bd_topo" / "batiment.gpkg", driver="GPKG")

    empty = gpd.GeoDataFrame({"id": []}, geometry=[], crs="EPSG:2154")
    empty.to_file(processed_dir / "bd_topo" / "vide.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gdb"

    compile_filegdb(processed_dir, output_path)

    assert fiona.listlayers(str(output_path)) == ["bd_topo_batiment"]


def test_compile_filegdb_splits_mixed_geometry_layers(tmp_path):
    processed_dir = tmp_path / "processed"
    (processed_dir / "infrastructures").mkdir(parents=True)

    mixed = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[Point(0, 0), Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:2154",
    )
    mixed.to_file(processed_dir / "infrastructures" / "commerces.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gdb"

    compile_filegdb(processed_dir, output_path)

    layers = set(fiona.listlayers(str(output_path)))
    assert layers == {"infrastructures_commerces_point", "infrastructures_commerces_polygone"}

    with fiona.open(str(output_path), layer="infrastructures_commerces_point") as src:
        assert len(src) == 1
    with fiona.open(str(output_path), layer="infrastructures_commerces_polygone") as src:
        assert len(src) == 1


def test_compile_filegdb_replaces_readonly_existing_gdb(tmp_path):
    # Reproduit un dossier .gdb existant dont OneDrive (Files On-Demand) a
    # marque le contenu en lecture seule apres un run precedent :
    # shutil.rmtree doit s'en accommoder plutot que lever une erreur.
    processed_dir = tmp_path / "processed"
    (processed_dir / "bd_topo").mkdir(parents=True)
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    ).to_file(processed_dir / "bd_topo" / "batiment.gpkg", driver="GPKG")

    output_path = tmp_path / "database" / "projet.gdb"
    output_path.mkdir(parents=True)
    stale_file = output_path / "stale.txt"
    stale_file.write_text("ancien contenu")
    os.chmod(stale_file, stat.S_IREAD)

    compile_filegdb(processed_dir, output_path)

    assert fiona.listlayers(str(output_path)) == ["bd_topo_batiment"]
