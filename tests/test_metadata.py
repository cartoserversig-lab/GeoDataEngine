import json

from database.metadata import record_layer_metadata


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
