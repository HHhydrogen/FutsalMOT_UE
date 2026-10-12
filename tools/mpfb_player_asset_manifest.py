"""Shared asset ownership and export metadata for MPFB Player_N assets."""

from pathlib import Path


CHARACTERS_ROOT = Path(r"D:\projects\FutsalMOT_blender\characters")
EXPORT_DATA_SCALE = 100.0
EXPORT_ARMATURE_OBJECT_SCALE = 0.01

HAIR_OBJECTS = {
    3: "Human.afro01",
    4: "Human.short01",
    5: "Human.short02",
    6: "Human.short03",
    7: "Human.short04",
    8: "Human.littleright_bobcut_hair",
    9: "Human.cortu_short_messy_hair",
}

SHARED_TEXTURES = {
    "body": "T_MPFB_Skin_BaseColor.png",
    "eyebrow": "T_MPFB_Eyebrow_BaseColor.png",
    "eyes": "T_MPFB_Eyes_BaseColor.png",
    "shoes": "T_MPFB_Shoes_BaseColor.png",
    "jersey": "T_MPFB_Jersey_BaseColor.png",
    "shorts": "T_MPFB_Shorts_BaseColor.png",
}

UE_ROOT = "/Game/FutsalMOT/Characters/MPFB"
MALE_SKIN_TEXTURE_DIR = UE_ROOT + "/Textures/Skins/Male"

MALE_SKIN_TEXTURES = (
    ("young_african_male/young_darkskinned_male_diffuse.png", "T_MPFB_Skin_Young_African_Dark"),
    ("middleage_asian_male/middleage_lightskinned_male_diffuse2.png", "T_MPFB_Skin_MiddleAge_Asian_Light"),
    ("young_caucasian_male/young_lightskinned_male_diffuse.png", "T_MPFB_Skin_Young_Caucasian_Light"),
    ("old_asian_male/old_lightskinned_male_diffuse2.png", "T_MPFB_Skin_Old_Asian_Light"),
    ("middleage_caucasian_male/middleage_lightskinned_male_diffuse.png", "T_MPFB_Skin_MiddleAge_Caucasian_Light"),
    ("middleage_african_male/middleage_darkskinned_male_diffuse.png", "T_MPFB_Skin_MiddleAge_African_Dark"),
    ("young_asian_male/young_lightskinned_male_diffuse3.png", "T_MPFB_Skin_Young_Asian_Light"),
    ("old_african_male/old_darkskinned_male_diffuse.png", "T_MPFB_Skin_Old_African_Dark"),
    ("old_caucasian_male/old_lightskinned_male_diffuse.png", "T_MPFB_Skin_Old_Caucasian_Light"),
)
SHARED_MATERIALS = {
    "body": "middleage_lightskinned_male_diffuse2_Mat",
    "eyebrow": "eyebrow001_Mat",
    "eyes": "blue_eye_Mat",
    "shoes": "shoes06_diffuse_Mat",
    "jersey": "jersey_001_Mat",
    "shorts": "short_001_Mat",
}


def male_skin_manifest() -> list[dict[str, str]]:
    """Return CC0 male skin diffuse sources and their UE texture names."""
    return [
        {
            "source_member": f"skins/{relative_path}",
            "ue_asset_name": asset_name,
        }
        for relative_path, asset_name in MALE_SKIN_TEXTURES
    ]


def shared_asset_path(asset_type: str, asset_name: str) -> str:
    """Return a shared Texture or Material content path."""
    folders = {"texture": "Textures", "material": "Materials"}
    try:
        folder = folders[asset_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported shared asset type: {asset_type}") from exc
    return f"{UE_ROOT}/{folder}/{asset_name}"


def player_asset_path(player_id: int, asset_type: str, asset_name: str) -> str:
    """Return a player-private Texture or Material content path."""
    folders = {"texture": "Textures", "material": "Materials", "mesh": "Mesh"}
    try:
        folder = folders[asset_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported player asset type: {asset_type}") from exc
    return f"{UE_ROOT}/Players/Player_{player_id:03d}/{folder}/{asset_name}"


def material_category_for_slot(slot_name: str) -> str:
    """Map a source FBX material slot name to its shared/private category."""
    normalized = slot_name.casefold()
    if "afro01" in normalized or "short01" in normalized or "short02" in normalized:
        return "hair"
    if "bobcut_hair" in normalized or "messy_hair" in normalized:
        return "hair"
    if "body" in normalized:
        return "body"
    if "eyebrow" in normalized:
        return "eyebrow"
    if "low-poly" in normalized or "low_poly" in normalized:
        return "eyes"
    if "shoes06" in normalized or "shoe" in normalized:
        return "shoes"
    if "short" in normalized or "futsalmot_shorts" in normalized:
        return "shorts"
    if slot_name == "材质" or "jersey" in normalized:
        return "jersey"
    raise ValueError(f"Unrecognized MPFB material slot: {slot_name}")


def player_hair_object(player_id: int) -> str:
    """Return the source Blender object used for this player's hair."""
    try:
        return HAIR_OBJECTS[player_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported MPFB player id: {player_id}") from exc


def player_hair_asset_names(player_id: int) -> tuple[str, str]:
    """Return the private hair texture and material asset names."""
    suffix = {
        3: "afro01",
        4: "short01",
        5: "short02",
        6: "short03",
        7: "short04",
        8: "littleright_bobcut_hair",
        9: "cortu_short_messy_hair",
    }[player_id]
    texture_name = {
        3: "afro_diffuse",
        4: "short01_diffuse",
        5: "short02_diffuse",
        6: "short03_diffuse",
        7: "short04_diffuse",
        8: "hairtex",
        9: "short_messy_diff",
    }[player_id]
    return texture_name, f"M_Player{player_id:03d}_Hair"


def classify_texture_destination(player_id: int, object_name: str) -> str:
    """Return ``player_hair`` for the private hair mesh, otherwise ``shared``."""
    return "player_hair" if object_name == player_hair_object(player_id) else "shared"


def scaled_child_location(location, armature_object_scale=EXPORT_ARMATURE_OBJECT_SCALE):
    """Preserve a child mesh's world offset under the scaled export armature."""
    if armature_object_scale == 0:
        raise ValueError("armature_object_scale must be non-zero")
    return tuple(float(component) / armature_object_scale for component in location)


def source_directory(player_id: int) -> Path:
    """Return a Player_N directory, including Player_005's lowercase source name."""
    directory_name = "player_005" if player_id == 5 else f"Player_{player_id:03d}"
    return CHARACTERS_ROOT / directory_name


def source_blend_path(player_id: int) -> Path:
    return source_directory(player_id) / f"MPFB_Player_{player_id:03d}.blend"


def export_directory(player_id: int) -> Path:
    return source_directory(player_id) / "export"


def export_fbx_path(player_id: int) -> Path:
    return export_directory(player_id) / f"MPFB_Player_{player_id:03d}_SOP.fbx"
