"""绿色候选沿用旧seed流；不能以CPU清单冒充材质或采集验收。"""

import hashlib
import json
import random

import pytest

from grf_ue_bridge.floor_diversity import CATALOG, NAMESPACE, select_floor_id
from grf_ue_bridge.green_floor import GREEN_CATALOG, build_green_floor_candidate

INPUTS = dict(trajectory_sha256="1" * 64, frozen_context_sha256="2" * 64,
              original_material_sha256="3" * 64, inspection_sha256="4" * 64)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")).hexdigest()


def test_default_catalog_still_uses_original_selection_bytes():
    for seed in (0, 1048, 1102, 2147483647):
        rank = digest(dict(namespace=NAMESPACE, seed=seed, catalog_sha256=digest(CATALOG)))
        assert select_floor_id(seed) == CATALOG[int(rank, 16) % len(CATALOG)]["id"]


def test_green_is_order_independent_and_does_not_consume_random_state():
    before = random.getstate()
    records = {s: build_green_floor_candidate(s, **INPUTS) for s in (1048, 1102)}
    assert random.getstate() == before
    for seed in (1102, 1048):
        assert build_green_floor_candidate(seed, **INPUTS) == records[seed]
        assert records[seed]["variant"]["id"] == select_floor_id(seed, catalog=GREEN_CATALOG)
        assert records[seed]["sequence_constant"] is True
        assert records[seed]["runtime_authorized"] is False
        assert records[seed]["visual_acceptance"] is False


def test_all_green_pairs_keep_motion_context_and_split_independent_key():
    records = [build_green_floor_candidate(1048, floor_id=v["id"], **INPUTS)
               for v in GREEN_CATALOG]
    assert len({r["pairing_key"] for r in records}) == 1
    assert len({r["fingerprint"] for r in records}) == len(GREEN_CATALOG)
    assert all(0.9 <= x <= 1.1 for v in GREEN_CATALOG for x in v["albedo_gain_linear"])
    with pytest.raises(ValueError):
        build_green_floor_candidate(1048, floor_id="sport_blue_v1", **INPUTS)


def test_bad_inputs_cannot_be_admitted_as_green_candidate():
    with pytest.raises(ValueError):
        build_green_floor_candidate(True, **INPUTS)
    with pytest.raises(ValueError):
        build_green_floor_candidate(1048, **dict(INPUTS, inspection_sha256="bad"))
    with pytest.raises(ValueError):
        select_floor_id(1048, catalog=())
