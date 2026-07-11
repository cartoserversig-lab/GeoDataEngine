import geopandas as gpd
from shapely.geometry import Point, box

from processing.clipping import clip_all_vector_layers, clip_to_boundary


def test_clip_to_boundary_no_buffer(tmp_path):
    points = gpd.GeoDataFrame(
        {"id": [1, 2, 3]},
        geometry=[Point(0, 0), Point(5, 5), Point(20, 20)],
        crs="EPSG:2154",
    )
    input_path = tmp_path / "points.gpkg"
    points.to_file(input_path, driver="GPKG")

    boundary = gpd.GeoDataFrame(
        geometry=[box(-1, -1, 10, 10)], crs="EPSG:2154"
    )

    clipped = clip_to_boundary(input_path, boundary)

    assert len(clipped) == 2
    assert set(clipped["id"]) == {1, 2}


def test_clip_to_boundary_with_buffer(tmp_path):
    points = gpd.GeoDataFrame(
        {"id": [1, 2, 3]},
        geometry=[Point(0, 0), Point(5, 5), Point(15, 15)],
        crs="EPSG:2154",
    )
    input_path = tmp_path / "points.gpkg"
    points.to_file(input_path, driver="GPKG")

    boundary = gpd.GeoDataFrame(
        geometry=[box(-1, -1, 10, 10)], crs="EPSG:2154"
    )

    clipped_no_buffer = clip_to_boundary(
        input_path, boundary, buffer_distance=0
    )
    assert len(clipped_no_buffer) == 2

    clipped_with_buffer = clip_to_boundary(
        input_path, boundary, buffer_distance=10
    )
    assert len(clipped_with_buffer) == 3


def test_clip_to_boundary_writes_output(tmp_path):
    points = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[Point(0, 0), Point(20, 20)],
        crs="EPSG:2154",
    )
    input_path = tmp_path / "points.gpkg"
    points.to_file(input_path, driver="GPKG")

    boundary = gpd.GeoDataFrame(
        geometry=[box(-1, -1, 10, 10)], crs="EPSG:2154"
    )
    output_path = tmp_path / "clipped.gpkg"

    clip_to_boundary(input_path, boundary, output_path=output_path)

    assert output_path.exists()
    assert len(gpd.read_file(output_path)) == 1


def test_clip_all_vector_layers(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    inside = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(0, 0)], crs="EPSG:2154"
    )
    (raw_dir / "theme_a").mkdir(parents=True)
    inside.to_file(raw_dir / "theme_a" / "layer_inside.gpkg", driver="GPKG")

    outside = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(100, 100)], crs="EPSG:2154"
    )
    (raw_dir / "theme_b").mkdir(parents=True)
    outside.to_file(raw_dir / "theme_b" / "layer_outside.gpkg", driver="GPKG")

    boundary = gpd.GeoDataFrame(
        geometry=[box(-1, -1, 10, 10)], crs="EPSG:2154"
    )

    written = clip_all_vector_layers(raw_dir, processed_dir, boundary)

    assert len(written) == 1
    relative_path = next(iter(written))
    assert relative_path.replace("\\", "/") == "theme_a/layer_inside.gpkg"

    output_path = written[relative_path]
    assert output_path.exists()
    assert not (processed_dir / "theme_b" / "layer_outside.gpkg").exists()
