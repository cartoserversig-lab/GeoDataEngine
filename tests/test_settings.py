from core.config import Settings, load_settings


def test_load_settings_missing_file_returns_defaults(tmp_path):
    settings = load_settings(tmp_path / "absent.toml")

    assert settings == Settings()


def test_load_settings_parses_file(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text(
        "buffer_decoupe = 75.0\n"
        "buffer_telechargement = 300.0\n"
        "include_lidar = true\n"
        "include_ortho = false\n"
        "auto_reproject = false\n"
        "classify_lidar_from_vectors = true\n",
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.buffer_decoupe == 75.0
    assert settings.buffer_telechargement == 300.0
    assert settings.include_lidar is True
    assert settings.include_ortho is False
    assert settings.auto_reproject is False
    assert settings.classify_lidar_from_vectors is True


def test_load_settings_partial_file_uses_defaults_for_missing_keys(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text("buffer_decoupe = 10.0\n", encoding="utf-8")

    settings = load_settings(path)

    assert settings.buffer_decoupe == 10.0
    assert settings.buffer_telechargement == Settings().buffer_telechargement
    assert settings.include_lidar is False
