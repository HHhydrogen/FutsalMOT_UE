import json
import unreal


ROOT = "/Game/FutsalMOT/Tests/MPFB_Runtime"
LEVEL = ROOT + "/L_MPFB_RuntimeTest"
FLOOR_MAT = ROOT + "/M_MPFB_TestFloor"
PAWN_BP = ROOT + "/BP_MPFB_InspectPawn"
CONTROLLER_BP = ROOT + "/BP_MPFB_InspectController"
GAMEMODE_BP = ROOT + "/BP_MPFB_RuntimeTestGameMode"
CHARACTER_BP = "/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayer_MPFB_Test"


def asset(path):
    return unreal.load_asset(path)


def save(path):
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)


def ensure_bp(path, parent_class):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return asset(path)
    bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(path, parent_class)
    if not bp:
        raise RuntimeError("无法创建蓝图: " + path)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    save(path)
    return bp


def ensure_material():
    if unreal.EditorAssetLibrary.does_asset_exist(FLOOR_MAT):
        return asset(FLOOR_MAT)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_MPFB_TestFloor", ROOT, unreal.Material, unreal.MaterialFactoryNew()
    )
    if not mat:
        raise RuntimeError("无法创建地面材质")
    mat.set_editor_property("two_sided", False)
    color = unreal.MaterialExpressionConstant3Vector()
    color.set_editor_property("constant", unreal.LinearColor(0.42, 0.45, 0.48, 1.0))
    rough = unreal.MaterialExpressionConstant()
    rough.set_editor_property("r", 0.82)
    unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, 0, 0)
    unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, 240, 0)
    expressions = unreal.MaterialEditingLibrary.get_material_expressions(mat)
    color = next(x for x in expressions if isinstance(x, unreal.MaterialExpressionConstant3Vector))
    rough = next(x for x in expressions if isinstance(x, unreal.MaterialExpressionConstant))
    color.set_editor_property("constant", unreal.LinearColor(0.42, 0.45, 0.48, 1.0))
    rough.set_editor_property("r", 0.82)
    unreal.MaterialEditingLibrary.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mat.post_edit_change()
    save(FLOOR_MAT)
    return mat


def make_transform(location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    return unreal.Transform(
        unreal.Vector(*location),
        unreal.Rotator(*rotation),
        unreal.Vector(*scale),
    )


def spawn(subsystem, cls, label, transform):
    actor = subsystem.spawn_actor_from_class(cls, transform.translation, transform.rotation.rotator())
    if not actor:
        raise RuntimeError("无法生成 Actor: " + label)
    actor.set_actor_label(label)
    actor.set_actor_transform(transform, False, True)
    return actor


def add_static_mesh(subsystem, mesh, material, label, location, scale):
    actor = spawn(subsystem, unreal.StaticMeshActor, label, make_transform(location, scale=scale))
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    comp.set_editor_property("static_mesh", mesh)
    if material:
        comp.set_material(0, material)
    return actor


def main():
    unreal.EditorAssetLibrary.make_directory(ROOT)
    pawn_bp = ensure_bp(PAWN_BP, unreal.load_class(None, "/Script/FutsalMOT.MPFBInspectPawn"))
    controller_bp = ensure_bp(CONTROLLER_BP, unreal.load_class(None, "/Script/FutsalMOT.MPFBInspectController"))
    gamemode_bp = ensure_bp(GAMEMODE_BP, unreal.load_class(None, "/Script/FutsalMOT.MPFBRuntimeTestGameMode"))
    for bp in (pawn_bp, controller_bp, gamemode_bp):
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    floor_mat = ensure_material()

    if not unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
        world = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "L_MPFB_RuntimeTest", ROOT, unreal.World, unreal.WorldFactory()
        )
        if not world:
            raise RuntimeError("无法创建测试关卡")
        save(LEVEL)
    unreal.EditorLoadingAndSavingUtils.load_map(LEVEL)
    world = unreal.EditorLevelLibrary.get_editor_world()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # 仅清理本测试关卡中的旧测试 Actor，避免重复运行脚本产生重叠物体。
    for actor in list(subsystem.get_all_level_actors()):
        if actor.get_actor_label().startswith("MPFBTest_"):
            subsystem.destroy_actor(actor)

    cube = asset("/Engine/BasicShapes/Cube")
    floor = add_static_mesh(subsystem, cube, floor_mat, "MPFBTest_Floor", (0, 0, -10), (20, 20, 0.1))
    add_static_mesh(subsystem, cube, floor_mat, "MPFBTest_XReference", (1000, 0, 2), (10, 0.025, 0.02))
    add_static_mesh(subsystem, cube, floor_mat, "MPFBTest_YReference", (0, 1000, 3), (0.025, 10, 0.02))

    directional = spawn(subsystem, unreal.DirectionalLight, "MPFBTest_DirectionalLight", make_transform(rotation=(-35, -35, 25)))
    directional_component = directional.get_component_by_class(unreal.DirectionalLightComponent)
    directional_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    directional_component.set_editor_property("intensity", 4.0)

    sky = spawn(subsystem, unreal.SkyLight, "MPFBTest_SkyLight", make_transform(location=(0, 0, 800)))
    sky_component = sky.get_component_by_class(unreal.SkyLightComponent)
    sky_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    try:
        sky_component.set_editor_property("real_time_capture", True)
    except Exception:
        pass

    spawn(subsystem, unreal.SkyAtmosphere, "MPFBTest_SkyAtmosphere", make_transform())
    fog = spawn(subsystem, unreal.ExponentialHeightFog, "MPFBTest_HeightFog", make_transform())
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    fog_component.set_editor_property("fog_density", 0.003)

    start = spawn(subsystem, unreal.PlayerStart, "MPFBTest_PlayerStart", make_transform((1200, -1200, 700), (0, 45, 0)))
    start.set_actor_label("MPFBTest_PlayerStart")

    character_asset = unreal.load_asset(CHARACTER_BP)
    character_class = unreal.BlueprintEditorLibrary.generated_class(character_asset) if character_asset else None
    if not character_class:
        raise RuntimeError("找不到现有角色类: " + CHARACTER_BP)
    character = spawn(subsystem, character_class, "MPFBTest_RuntimeRetargetCharacter", make_transform((0, 0, 100)))
    character.set_actor_label("MPFBTest_RuntimeRetargetCharacter")
    try:
        character.set_editor_property("auto_possess_player", unreal.AutoReceiveInput.DISABLED)
    except Exception:
        pass
    try:
        character.set_editor_property("auto_receive_input", unreal.AutoReceiveInput.DISABLED)
    except Exception:
        pass

    world_settings = world.get_world_settings()
    gamemode_class = unreal.load_class(None, GAMEMODE_BP + "_C")
    world_settings.set_editor_property("default_game_mode", gamemode_class)

    unreal.EditorLevelLibrary.save_current_level()
    save(PAWN_BP)
    save(CONTROLLER_BP)
    save(GAMEMODE_BP)
    save(FLOOR_MAT)
    save(LEVEL)

    actors = []
    for actor in subsystem.get_all_level_actors():
        actors.append({"label": actor.get_actor_label(), "class": actor.get_class().get_name(), "location": actor.get_actor_location().to_tuple()})
    result = {
        "level": LEVEL,
        "pawn": PAWN_BP,
        "controller": CONTROLLER_BP,
        "gamemode": GAMEMODE_BP,
        "material": FLOOR_MAT,
        "character": character.get_class().get_name(),
        "character_location": character.get_actor_location().to_tuple(),
        "actors": actors,
    }
    unreal.log(json.dumps(result, ensure_ascii=False))
    return result


main()
