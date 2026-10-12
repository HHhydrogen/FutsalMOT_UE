import unittest

from tools.mpfb_player_asset_manifest import (
    MALE_SKIN_TEXTURE_DIR,
    male_skin_manifest,
    classify_texture_destination,
    material_category_for_slot,
    player_hair_object,
    player_hair_asset_names,
    player_asset_path,
    shared_asset_path,
    scaled_child_location,
)


class MpfbPlayerAssetManifestTests(unittest.TestCase):
    def test_male_skin_manifest_contains_only_the_nine_male_diffuse_textures(self):
        manifest = male_skin_manifest()

        self.assertEqual(len(manifest), 9)
        self.assertEqual(
            {item["source_member"] for item in manifest},
            {
                "skins/young_african_male/young_darkskinned_male_diffuse.png",
                "skins/middleage_asian_male/middleage_lightskinned_male_diffuse2.png",
                "skins/young_caucasian_male/young_lightskinned_male_diffuse.png",
                "skins/old_asian_male/old_lightskinned_male_diffuse2.png",
                "skins/middleage_caucasian_male/middleage_lightskinned_male_diffuse.png",
                "skins/middleage_african_male/middleage_darkskinned_male_diffuse.png",
                "skins/young_asian_male/young_lightskinned_male_diffuse3.png",
                "skins/old_african_male/old_darkskinned_male_diffuse.png",
                "skins/old_caucasian_male/old_lightskinned_male_diffuse.png",
            },
        )
        self.assertTrue(
            all(item["source_member"].startswith("skins/") for item in manifest)
        )
        self.assertTrue(
            all("_male/" in item["source_member"] for item in manifest)
        )
        self.assertTrue(
            all(item["ue_asset_name"].startswith("T_MPFB_Skin_") for item in manifest)
        )
        self.assertEqual(
            MALE_SKIN_TEXTURE_DIR,
            "/Game/FutsalMOT/Characters/MPFB/Textures/Skins/Male",
        )

    def test_each_player_routes_only_its_hair_to_its_private_folder(self):
        expected_hair_objects = {
            3: "Human.afro01",
            4: "Human.short01",
            5: "Human.short02",
            6: "Human.short03",
            7: "Human.short04",
            8: "Human.littleright_bobcut_hair",
            9: "Human.cortu_short_messy_hair",
        }

        for player_id, expected_object in expected_hair_objects.items():
            with self.subTest(player_id=player_id):
                self.assertEqual(player_hair_object(player_id), expected_object)
                texture_name, material_name = player_hair_asset_names(player_id)
                self.assertTrue(texture_name)
                self.assertEqual(material_name, f"M_Player{player_id:03d}_Hair")
                self.assertEqual(
                    classify_texture_destination(player_id, expected_object),
                    "player_hair",
                )
                self.assertEqual(
                    classify_texture_destination(player_id, "Human.body"),
                    "shared",
                )

    def test_child_translation_is_compensated_for_armature_scale(self):
        self.assertEqual(
            scaled_child_location((0.0, 0.0, -0.0670812577), 0.01),
            (0.0, 0.0, -6.70812577),
        )

    def test_shared_assets_are_separate_from_player_hair_assets(self):
        self.assertEqual(
            shared_asset_path("texture", "T_MPFB_Skin_BaseColor"),
            "/Game/FutsalMOT/Characters/MPFB/Textures/T_MPFB_Skin_BaseColor",
        )
        self.assertEqual(
            shared_asset_path("material", "M_MPFB_Body"),
            "/Game/FutsalMOT/Characters/MPFB/Materials/M_MPFB_Body",
        )
        self.assertEqual(
            player_asset_path(3, "material", "M_Player003_Hair"),
            "/Game/FutsalMOT/Characters/MPFB/Players/Player_003/Materials/M_Player003_Hair",
        )

    def test_material_slots_route_to_shared_or_private_materials(self):
        slots = {
            "Human_body": "body",
            "Human_afro01": "hair",
            "Human_eyebrow001": "eyebrow",
            "材质": "jersey",
            "Human_futsalmot_shorts_male_final": "shorts",
            "Human_low-poly": "eyes",
            "Human_shoes06": "shoes",
            "Human.littleright_bobcut_hair": "hair",
            "Human.cortu_short_messy_hair": "hair",
        }
        for slot_name, expected in slots.items():
            with self.subTest(slot_name=slot_name):
                self.assertEqual(material_category_for_slot(slot_name), expected)


if __name__ == "__main__":
    unittest.main()
