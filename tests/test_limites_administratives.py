from core.config import Entity
from download.limites_administratives import resolve_bbox


def test_resolve_bbox_uses_entity_bbox_if_present():
    entity = Entity(
        nom="Test",
        type_entite="commune",
        code_insee="38185",
        bbox=(913000.0, 6456000.0, 916500.0, 6458500.0),
    )

    assert resolve_bbox(entity) == entity.bbox
