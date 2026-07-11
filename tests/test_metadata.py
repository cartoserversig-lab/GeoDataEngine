import json

from database.metadata import find_metadata_record, record_layer_metadata, record_processing


def test_record_layer_metadata_creates_file(tmp_path):
    output_path = record_layer_metadata(
        layer="test_layer",
        source="Test Source",
        producteur="Test",
        fichier=tmp_path / "test_layer.gpkg",
        crs="EPSG:2154",
        metadata_dir=tmp_path,
    )

    assert output_path.exists()
    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["couche"] == "test_layer"
    assert records[0]["crs"] == "EPSG:2154"
    assert records[0]["resolution"] is None
    assert records[0]["traitements_appliques"] == []


def test_record_layer_metadata_appends(tmp_path):
    record_layer_metadata(
        layer="layer_1",
        source="S",
        producteur="P",
        fichier="a.gpkg",
        crs="EPSG:2154",
        metadata_dir=tmp_path,
    )
    output_path = record_layer_metadata(
        layer="layer_2",
        source="S",
        producteur="P",
        fichier="b.gpkg",
        crs="EPSG:2154",
        metadata_dir=tmp_path,
        resolution=0.2,
        traitements=["reprojection"],
    )

    records = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(records) == 2
    assert records[1]["couche"] == "layer_2"
    assert records[1]["resolution"] == 0.2
    assert records[1]["traitements_appliques"] == ["reprojection"]


def test_find_metadata_record_matches_relative_and_absolute_paths(tmp_path):
    record_layer_metadata(
        layer="layer_1",
        source="S",
        producteur="P",
        fichier=tmp_path / "layer_1.gpkg",
        metadata_dir=tmp_path,
    )

    found_absolute = find_metadata_record(tmp_path / "layer_1.gpkg", metadata_dir=tmp_path)
    assert found_absolute is not None
    assert found_absolute["couche"] == "layer_1"

    found_none = find_metadata_record(tmp_path / "inexistant.gpkg", metadata_dir=tmp_path)
    assert found_none is None


def test_record_processing_inherits_from_source_and_accumulates_traitements(tmp_path):
    record_layer_metadata(
        layer="bd_topo_batiment",
        source="BD TOPO (IGN)",
        producteur="IGN",
        fichier=tmp_path / "raw.gpkg",
        crs="EPSG:2154",
        metadata_dir=tmp_path,
    )

    record_processing(
        tmp_path / "raw.gpkg", tmp_path / "clipped.gpkg", "decoupage (buffer=50m)", metadata_dir=tmp_path
    )
    record_processing(
        tmp_path / "clipped.gpkg",
        tmp_path / "reprojected.gpkg",
        "reprojection vers EPSG:2154",
        metadata_dir=tmp_path,
    )

    record = find_metadata_record(tmp_path / "reprojected.gpkg", metadata_dir=tmp_path)
    assert record["source"] == "BD TOPO (IGN)"
    assert record["producteur"] == "IGN"
    assert record["crs"] == "EPSG:2154"
    assert record["traitements_appliques"] == ["decoupage (buffer=50m)", "reprojection vers EPSG:2154"]


def test_record_processing_without_source_record_uses_placeholder(tmp_path):
    record_processing(
        tmp_path / "inconnu.las", tmp_path / "sortie.las", "fusion de 2 dalle(s) LAZ", metadata_dir=tmp_path
    )

    record = find_metadata_record(tmp_path / "sortie.las", metadata_dir=tmp_path)
    assert record["source"] == "inconnue"
    assert record["producteur"] == "inconnue"
    assert record["traitements_appliques"] == ["fusion de 2 dalle(s) LAZ"]
