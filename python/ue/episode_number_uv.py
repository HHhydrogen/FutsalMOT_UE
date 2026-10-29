"""在原 v1 随机外观事务之上叠加 UV 号码；不改原模型/肤色/kit 分配。"""

import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from grf_ue_bridge.number_uv_plan import PLAN_SCHEMA, RENDER_POLICY, build_plan

_ACTIVE = None



def _object_result(value, label):
    if not isinstance(value, tuple) or len(value) != 2 or value[0] is None or value[1]:
        raise RuntimeError("{}失败: {!r}".format(label, value))
    return value[0]


class NumberSession:
    """只持有当前十人的组件；恢复号码后交还原外观事务。"""

    def __init__(self, plan, mapping, report_path):
        self.plan, self.mapping = plan, mapping
        self.report_path = Path(report_path)
        self.items = []
        self.atlas = None
        self.expires_at = 0
        self.report = {"schema": "futsalmot_uv_number_application_v1", "state": "preparing",
                       "plan_fingerprint": plan["fingerprint"], "actors": [], "errors": []}

    def _write(self):
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply(self):
        import unreal
        import episode_appearance as appearance
        from jersey_number_uv_build_catalog import DESTINATION
        from jersey_number_uv_build_preview import TEXTURE_PATH
        from jersey_number_uv_build_mask_preview import MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH
        library = unreal.JerseyNumberUVLibrary
        texture_path = TEXTURE_PATH
        if self.plan.get('atlas') is not None:
            from grf_ue_bridge.number_typography import atlas_profile
            expected=atlas_profile(self.plan['atlas']['id'])
            if expected != self.plan['atlas']:
                raise RuntimeError('号码字体清单与目录不符')
            texture_path=expected['texture']
        assets = {p: unreal.load_asset(p) for p in (texture_path, MASKED_PATH, EMPTY_PATH, POST_PROCESS_PATH)}
        if not all(assets.values()):
            raise RuntimeError("号码图集或mask材质不存在")
        self.atlas = assets[texture_path]
        # 限时驻留覆盖此任务；退出时显式释放，不改全局streaming或资产设置。
        self.atlas.set_force_mip_levels_to_be_resident(3600.0, 0)
        self.expires_at = time.time() + 3600
        actors = {a.get_actor_label(): a for a in unreal.EditorLevelLibrary.get_all_level_actors()}
        try:
            for entity in self.plan["entities"]:
                actor = actors[self.mapping[entity["entity_id"]]]
                visual = appearance._component_for_actor(unreal, actor)
                if appearance._package_path(visual.get_skeletal_mesh_asset()) != entity["mesh"]:
                    raise RuntimeError("当前可见mesh不匹配随机清单: " + entity["entity_id"])
                slot = library.find_unique_jersey_slot(visual)
                if slot < 0:
                    raise RuntimeError("球衣语义slot不唯一")
                if appearance._package_path(visual.get_material(slot)) != entity["jersey_material"]:
                    raise RuntimeError("号码应用前随机球衣不匹配: " + entity["entity_id"])
                item = {"visual": visual, "original_materials": list(visual.get_editor_property("override_materials")),
                        "custom_depth": visual.get_editor_property("render_custom_depth"), "follower": None}
                self.items.append(item)
                params = unreal.JerseyNumberUVParameters()
                for name, value in {"number": entity["jersey_number"], "entity_mask_id": entity["number_mask_id"],
                                    "uv_rect": unreal.LinearColor(*self.plan["uv_rect"]),
                                    "ink_color": unreal.LinearColor(*(entity["ink_color"] + [1.0])),
                                    "flip_u": self.plan["flip_u"], "flip_v": self.plan["flip_v"]}.items():
                    params.set_editor_property(name, value)
                parent_path = DESTINATION + "/M_Jersey_Set_" + entity["kit_set_id"] + "_NumberUV_v1"
                parent = unreal.load_asset(parent_path)
                if parent is None:
                    raise RuntimeError("缺少对应套装号码材质: " + parent_path)
                beauty = _object_result(library.create_number_material(parent, self.atlas, actor, params), "号码球衣")
                masked = _object_result(library.create_number_material(assets[MASKED_PATH], self.atlas, actor, params), "号码mask")
                visual.set_material(slot, beauty)
                visual.set_editor_property("render_custom_depth", False)
                follower = _object_result(library.create_number_mask_follower(visual, masked, assets[EMPTY_PATH], entity["number_mask_id"]), "蒙皮号码代理")
                item.update(follower=follower, beauty=beauty, masked=masked)
                self.report["actors"].append({"entity_id": entity["entity_id"], "mesh": entity["mesh"],
                    "skin_id": entity["skin_id"], "kit_set_id": entity["kit_set_id"],
                    "jersey_number": entity["jersey_number"], "number_mask_id": entity["number_mask_id"],
                    "visual": visual.get_path_name(), "follower": follower.get_path_name(),
                    "number_material": beauty.get_path_name(), "base_material": entity["jersey_material"]})
            self.report.update(state="applied", post_process_material=POST_PROCESS_PATH,
                               residency_expires_at=self.expires_at)
            if self.plan.get('atlas') is not None:
                self.report['atlas']=self.plan['atlas']
            self._write()
            return self
        except Exception:
            self.restore()
            raise

    def restore(self):
        import unreal
        errors = []
        for item in reversed(self.items):
            try:
                follower = item.get("follower")
                if follower is not None:
                    value = unreal.JerseyNumberUVLibrary.destroy_number_mask_follower(follower, item["visual"])
                    if value != "":
                        raise RuntimeError("号码代理删除失败: {!r}".format(value))
                item["visual"].set_editor_property("override_materials", item["original_materials"])
                item["visual"].set_editor_property("render_custom_depth", item["custom_depth"])
            except Exception as exc:
                errors.append(str(exc))
        if not errors:
            self.items.clear()
            if self.atlas is not None:
                self.atlas.set_force_mip_levels_to_be_resident(0.0, 0)
                self.atlas = None
        self.report.update(state="restore_failed" if errors else "restored", errors=errors)
        self._write()
        if errors:
            raise RuntimeError("; ".join(errors))

    def render_evidence(self):
        if self.report["state"] != "applied" or time.time() + 15 >= self.expires_at:
            raise RuntimeError("号码未应用或驻留已接近到期")
        return dict(self.report)


def validate_render_evidence(evidence, material):
    """只允许当前真实应用的十人事务提交号码通道；首轮MRQ本身产出同步证据。"""
    errors = []
    current = _ACTIVE
    if current is None or current.report.get("state") != "applied":
        errors.append("当前无活动UV号码事务")
    elif not isinstance(evidence, dict) or evidence.get("plan_fingerprint") != current.plan["fingerprint"]:
        errors.append("号码渲染输入不匹配当前事务")
    else:
        try:
            current.render_evidence()
            if len(current.items) != 10:
                raise RuntimeError("号码组件不足十人")
            for item, entity in zip(current.items, current.plan["entities"]):
                visual, follower = item["visual"], item["follower"]
                if (follower.get_skeletal_mesh_asset() != visual.get_skeletal_mesh_asset()
                        or int(follower.get_editor_property("custom_depth_stencil_value")) != entity["number_mask_id"]
                        or item["beauty"].get_scalar_parameter_value("NumberIndex") != entity["jersey_number"] - 1):
                    raise RuntimeError("号码/mesh/stencil实际读回不一致")
            if material != current.report["post_process_material"]:
                raise RuntimeError("号码后处理材质不匹配")
        except Exception as exc:
            errors.append(str(exc))
    return {"ok": not errors, "errors": errors, "number_mask_post_process_material": material}


def apply_numbers(plan, mapping, report_path):
    global _ACTIVE
    if _ACTIVE is not None:
        raise RuntimeError("已有号码事务尚未恢复")
    session = NumberSession(plan, mapping, report_path)
    _ACTIVE = session.apply()
    return _ACTIVE


def restore_numbers():
    global _ACTIVE
    if _ACTIVE is not None:
        _ACTIVE.restore()
        _ACTIVE = None
