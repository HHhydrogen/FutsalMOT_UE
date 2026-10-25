"""只检查服装清单桥接，不冒充动态材质/MRQ验收。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from pose_seeded_kit_plan import ROOT, build_binding
from grf_ue_bridge.appearance import build_appearance_manifest


class ExistingSeededKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.frames = Path(self.temp.name) / "frames.jsonl"
        self.frames.write_text('{"frame_index":0}\n', encoding="utf-8")
        config = json.loads((ROOT / "python/configs/player_appearance_smoke_10frames_1cam.json").read_text())
        self.catalog = config["ue"]["appearance"]
        ids = [side + str(i) for side in "LR" for i in range(5)]
        self.meta = dict(episode_id="test", randomness=dict(root_seed=42, ue_visual_seed=123),
            entities=[dict(id=e, team="left" if e.startswith("L") else "right", is_goalkeeper=e.endswith("0")) for e in ids])
        self.targets = [dict(entity_id=e, actor_object_name="Actor_"+e,
            component_object_name="MPFBVisual", calibration_player_id=3+i%7) for i, e in enumerate(ids)]
        self.manifest = build_appearance_manifest(self.meta, self.frames, self.catalog)

    def test_reuses_exact_existing_kits_without_mesh_skin_or_randomization(self):
        before = copy.deepcopy((self.meta, self.targets, self.manifest))
        plan = build_binding(self.manifest, self.meta, self.frames, self.catalog, self.targets)
        self.assertEqual(plan["kit_classes"], self.manifest["kit_classes"])
        self.assertEqual(len(set(plan["kit_classes"].values())), 4)
        original = {r["entity_id"]: r for r in self.manifest["entities"]}
        for row in plan["entities"]:
            self.assertEqual(row["kit_set_id"], original[row["entity_id"]]["kit_set_id"])
            self.assertEqual(set(row["semantic_materials"]), {"Jersey", "Shorts"})
            self.assertFalse({"mesh", "skin_texture", "anim_class", "jersey_number"} & row.keys())
        self.assertEqual((self.meta, self.targets, self.manifest), before)
        self.assertFalse(plan["render_authorized"])
        self.assertFalse(plan["runtime_material_readback_verified"])

    def test_tampered_kit_or_trajectory_is_rejected_by_original_validator(self):
        bad = copy.deepcopy(self.manifest)
        bad["entities"][0]["kit_set_id"] = "99"
        with self.assertRaises(ValueError):
            build_binding(bad, self.meta, self.frames, self.catalog, self.targets)
        self.frames.write_text("changed\n")
        with self.assertRaises(ValueError):
            build_binding(self.manifest, self.meta, self.frames, self.catalog, self.targets)

    def test_duplicate_or_hidden_driver_targets_are_rejected(self):
        for bad in (self.targets[:-1], self.targets+[self.targets[0]]):
            with self.assertRaises(ValueError):
                build_binding(self.manifest, self.meta, self.frames, self.catalog, bad)
        bad = copy.deepcopy(self.targets)
        bad[0]["component_object_name"] = "DriverMesh"
        with self.assertRaises(ValueError):
            build_binding(self.manifest, self.meta, self.frames, self.catalog, bad)

    def test_numbers_scope_is_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad["policy"] = "futsalmot_appearance_v2"
        bad["version"] = 2
        with self.assertRaises(ValueError):
            build_binding(bad, self.meta, self.frames, self.catalog, self.targets)


if __name__ == "__main__":
    unittest.main()
