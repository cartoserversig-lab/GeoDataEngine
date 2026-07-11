import pytest

from core.config import ConfigError, load_entities


def test_load_entities_ok(tmp_path):
    csv_file = tmp_path / "entites.csv"
    csv_file.write_text(
        "nom_entite;type_entite;code_insee;bbox\n"
        "Grenoble;commune;38185;[913000,6456000,916500,6458500]\n",
        encoding="utf-8",
    )

    entities = load_entities(csv_file)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.nom == "Grenoble"
    assert entity.type_entite == "commune"
    assert entity.code_insee == "38185"
    assert entity.bbox == (913000.0, 6456000.0, 916500.0, 6458500.0)


def test_load_entities_colonne_manquante(tmp_path):
    csv_file = tmp_path / "entites.csv"
    csv_file.write_text(
        "nom_entite;code_insee;bbox\nTest;38185;[1,2,3,4]\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_entities(csv_file)


def test_load_entities_bbox_incoherente(tmp_path):
    csv_file = tmp_path / "entites.csv"
    csv_file.write_text(
        "nom_entite;type_entite;code_insee;bbox\n"
        "Test;commune;38185;[10,20,5,40]\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_entities(csv_file)


def test_load_entities_bbox_absente(tmp_path):
    csv_file = tmp_path / "entites.csv"
    csv_file.write_text(
        "nom_entite;type_entite;code_insee\nTest;commune;38185\n",
        encoding="utf-8",
    )

    entities = load_entities(csv_file)

    assert len(entities) == 1
    assert entities[0].bbox is None


def test_load_entities_bbox_vide(tmp_path):
    csv_file = tmp_path / "entites.csv"
    csv_file.write_text(
        "nom_entite;type_entite;code_insee;bbox\nTest;commune;38185;\n",
        encoding="utf-8",
    )

    entities = load_entities(csv_file)

    assert len(entities) == 1
    assert entities[0].bbox is None
