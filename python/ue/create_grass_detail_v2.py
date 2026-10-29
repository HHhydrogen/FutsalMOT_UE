"""复用原草地母图创建可调细草纹及三档深浅实例，不修改历史资产。"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/src'))
from grf_ue_bridge.grass_detail import CATALOG, MATERIAL_ROOT, PARAMETERS


def main():
    import unreal
    lib = unreal.MaterialEditingLibrary
    dirty = lambda: [p.get_path_name() for p in
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) +
        list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
    assert unreal.EditorLevelLibrary.get_editor_world().get_path_name().split('.')[0] == '/Game/FutsalMOT/Maps/L_FutsalCourt'
    assert not unreal.EditorLevelLibrary.get_pie_worlds(False)
    assert not unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering()
    assert not dirty(), dirty()
    assert not unreal.EditorAssetLibrary.does_directory_exist(MATERIAL_ROOT), '新资产已存在，不覆盖'
    source_path = '/Game/FutsalMOT/Materials/M_Futsal_Field_Grass'
    source = unreal.load_asset(source_path)
    assert source and source.get_class().get_name() == 'Material'
    source_file = ROOT / 'Content/FutsalMOT/Materials/M_Futsal_Field_Grass.uasset'
    source_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    evidence = ROOT / 'Saved/FloorDiversity/green_v2'
    intent = evidence / 'creation_intent.json'
    assert not intent.exists(), '已有创建事务，不隐式重放'
    intent.write_text(json.dumps({'source': source_path, 'source_sha256': source_sha,
                                 'target': MATERIAL_ROOT, 'parameters': PARAMETERS}, indent=2), encoding='utf-8')
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.duplicate_asset('M_GrassDetail_v2', MATERIAL_ROOT, source)
    assert material
    nodes = {n.get_name(): n for n in lib.get_material_expressions(material)}

    def scalar(name, value, x, y):
        node = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('default_value', value)
        node.set_editor_property('group', 'Green Grass')
        return node

    tiling = scalar('GrassUVTiling', PARAMETERS['GrassUVTiling'], -1000, -450)
    assert lib.connect_material_expressions(tiling, '', nodes['MaterialExpressionMultiply_1'], 'B')
    # 原图已使用FlattenNormal，直接复用函数和中性法线语义。
    flatness = scalar('GrassNormalFlatness', PARAMETERS['GrassNormalFlatness'], -500, 250)
    assert lib.connect_material_expressions(flatness, '', nodes['MaterialExpressionMaterialFunctionCall_0'], 'Flatness')
    contrast = scalar('GrassStripeContrast', PARAMETERS['GrassStripeContrast'], -500, 600)
    low = lib.create_material_expression(material, unreal.MaterialExpressionSubtract, -250, 550)
    low.set_editor_property('const_a', 1.0)
    assert lib.connect_material_expressions(contrast, '', low, 'B')
    high = lib.create_material_expression(material, unreal.MaterialExpressionAdd, -250, 700)
    high.set_editor_property('const_a', 1.0)
    assert lib.connect_material_expressions(contrast, '', high, 'B')
    stripes = nodes['MaterialExpressionLinearInterpolate_0']
    assert lib.connect_material_expressions(low, '', stripes, 'A')
    assert lib.connect_material_expressions(high, '', stripes, 'B')
    original_base = lib.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    original_output = lib.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
    gain = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, 600, 0)
    gain.set_editor_property('parameter_name', 'GreenAlbedoGain')
    gain.set_editor_property('default_value', unreal.LinearColor(1, 1, 1, 1))
    gain.set_editor_property('group', 'Green Grass')
    multiply = lib.create_material_expression(material, unreal.MaterialExpressionMultiply, 800, 0)
    assert lib.connect_material_expressions(original_base, original_output, multiply, 'A')
    assert lib.connect_material_expressions(gain, '', multiply, 'B')
    assert lib.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
    lib.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material)
    report = {'status': 'created_wait_user_visual_acceptance', 'source_sha256': source_sha,
              'parent': material.get_path_name(), 'variants': [], 'parameters': PARAMETERS,
              'geometry_unchanged': True, 'historical_assets_unchanged': True}
    for variant in CATALOG:
        name = 'MI_' + variant['id']
        instance = tools.create_asset(name, MATERIAL_ROOT, unreal.MaterialInstanceConstant,
                                      unreal.MaterialInstanceConstantFactoryNew())
        assert instance
        lib.set_material_instance_parent(instance, material)
        lib.set_material_instance_scalar_parameter_value(instance, 'Param', 0.08)
        for parameter, value in PARAMETERS.items():
            lib.set_material_instance_scalar_parameter_value(instance, parameter, value)
            assert abs(float(lib.get_material_instance_scalar_parameter_value(instance, parameter)) - value) < 1e-6
        value = variant['albedo_gain_linear']
        lib.set_material_instance_vector_parameter_value(instance, 'GreenAlbedoGain', unreal.LinearColor(*value, 1))
        actual = lib.get_material_instance_vector_parameter_value(instance, 'GreenAlbedoGain')
        assert all(abs(a-b)<1e-6 for a,b in zip(value, [actual.r, actual.g, actual.b]))
        assert unreal.EditorAssetLibrary.save_loaded_asset(instance)
        report['variants'].append(dict(variant, material=instance.get_path_name()))
    assert hashlib.sha256(source_file.read_bytes()).hexdigest() == source_sha
    assert not dirty(), dirty()
    report['dirty_after'] = []
    (evidence / 'creation_complete.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
