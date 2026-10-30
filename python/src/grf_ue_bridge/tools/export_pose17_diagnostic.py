"""历史Pose17诊断的只读输入适配；旧导出执行功能已移除。"""

import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import shutil
import stat
import sys

import numpy as np
from PIL import Image

from grf_ue_bridge.pose17_export import COCO17_NAMES, project_landmarks
from grf_ue_bridge.tools.inspect_pose17_smoke import media_index

REPO = Path(__file__).resolve().parents[3]
from grf_ue_bridge.project_paths import saved_root
WORKSPACE_SAVED = saved_root(__file__)
if str(REPO / "ue") not in sys.path:
    sys.path.insert(0,str(REPO / "ue"))
from pose17_native_receipt import normalize_native_receipt
from pose17_override_receipt import validate_joint_bundle
from pose17_location_pilot_contract import validate_location_pilot_contract


def require(ok,message):
    if not ok: raise ValueError(message)


def guard(path):
    """只读写当前workspace Saved内普通路径，不跟随junction或symlink。"""
    path = Path(os.path.abspath(os.fspath(path)))
    root = Path(os.path.abspath(os.fspath(WORKSPACE_SAVED)))
    require(path!=root and root in path.parents,"路径必须位于当前workspace Saved内")
    for part in reversed((path,)+tuple(path.parents)):
        if not part.exists() and not part.is_symlink(): continue
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not(getattr(info,"st_file_attributes",0)&0x400),"拒绝联接/符号链接")
    return path


def read_json(path):
    return json.loads(guard(path).read_text(encoding="utf-8-sig"))














def load_inputs(attempt,alignment,native_report):
    attempt,alignment,native_report = guard(attempt),guard(alignment),guard(native_report)
    plan,state = read_json(attempt/"plan.json"),read_json(attempt/"state.json")
    pilot = validate_location_pilot_contract(plan)
    require(type(plan.get("frame_count")) is int and plan["frame_count"]==(120 if pilot else 10)
        and len(plan["cameras"])==4,"只接收四相机十帧联合诊断或显式冻结120帧位置试产")
    aligned,accepted = read_json(alignment),read_json(native_report)
    require(aligned.get("structural_pairing_passed") is True and not aligned.get("errors"),"结构配对报告未通过")
    require(accepted.get("acceptance_passed") is True and accepted.get("component_transaction_passed") is True
        and not accepted.get("errors"),"原生事务/恢复报告未通过")
    require(Path(aligned.get("attempt","")).resolve()==attempt and Path(accepted.get("attempt","")).resolve()==attempt,"报告不属于当前attempt")
    require(aligned.get("MRQ_sync_verified") is False and accepted.get("MRQ_sync_verified") is False,"诊断报告不得升级正式同步")
    require(hashlib.sha256((attempt/"plan.json").read_bytes()).hexdigest()==state["plan_sha256"],"冻结plan SHA不一致")
    receipts,manifests,hashes = {},{},{}
    for target in plan["targets"]:
        entity = target["entity_id"]
        raw = guard(attempt/(entity+"_landmark_snapshot.json")).read_bytes()
        manifests[entity],hashes[entity] = json.loads(raw),hashlib.sha256(raw).hexdigest()
    for camera in plan["cameras"]:
        camera_id = camera["camera_id"]
        receipts[camera_id] = normalize_native_receipt(read_json(attempt/(camera_id+"_native_pose_restore_receipt.json")))
    checked = validate_joint_bundle(plan,state,read_json(attempt/"preflight.json"),read_json(attempt/"editor_after.json"),manifests,hashes,receipts)
    require(checked["acceptance_passed"] and not checked["errors"],"原始native/manifest/恢复当前校验失败: "+repr(checked["errors"]))
    require(set(aligned["cameras"])=={c["camera_id"] for c in plan["cameras"]},"配对机位集合不同")
    for camera_id,receipt in receipts.items():
        paired_rows = aligned["cameras"][camera_id]["frames"]
        lookup = {(r["output_frame"],r["entity_id"]):r for r in paired_rows}
        require(len(lookup)==len(paired_rows)==plan["frame_count"]*len(plan["targets"]),"已验报告的实体帧重复或缺失")
        for row in receipt["records"]:
            paired = lookup[(row["output_frame"],row["entity_id"])]
            require(paired["source_frame"]==row["sequence_source_frame"]
                and [point["world_m"] for point in paired["keypoints"]]==row["world_m"],"原始native世界点/源帧与已验报告不同")
    return attempt,plan,receipts,aligned,hashes
