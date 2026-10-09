from pathlib import Path


SCRIPT = Path(__file__).with_name("export_player003_sop.py")
DOC = Path(__file__).parents[1] / "Docs" / "MPFB_PLAYER003_IMPORT_EXPORT_SOP.md"


def test_player003_sop_uses_the_verified_player002_unit_contract():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "EXPORT_DATA_SCALE = 100.0" in source
    assert "EXPORT_ARMATURE_OBJECT_SCALE = 0.01" in source
    assert "obj.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4), shape_keys=False)" in source
    assert "copy_armature.data.transform(Matrix.Scale(EXPORT_DATA_SCALE, 4))" in source
    assert "copy_armature.scale = (EXPORT_ARMATURE_OBJECT_SCALE,) * 3" in source
    assert "use_mesh_modifiers=True" in source
    assert "use_mesh_modifiers_render=True" in source
    assert "obj.location = src.location / EXPORT_ARMATURE_OBJECT_SCALE" in source


def test_player003_sop_documents_the_pants_offset_compensation():
    assert DOC.is_file()
    source = DOC.read_text(encoding="utf-8")

    assert "Mask modifier" in source
    assert "Human.futsalmot_shorts_male_v2" in source
    assert "EXPORT_ARMATURE_OBJECT_SCALE" in source
    assert "MPFB_Player_003_PrePantsFix" in source
