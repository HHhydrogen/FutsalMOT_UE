"""新生成的绿色目录隔离旧候选，保持独立seed且不消费全局随机流。"""
import random

import pytest

from grf_ue_bridge.floor_diversity import select_floor_id
from grf_ue_bridge.grass_detail import CATALOG, grass_recipe


def test_green_detail_selection_is_stable_isolated_and_rejects_retired_colors():
    state = random.getstate()
    recipes = {seed: grass_recipe(seed) for seed in (1048, 1102, 2026102901)}
    assert {v['id'] for v in CATALOG} == {'grass_dark_v2','grass_standard_v2','grass_light_v2'}
    for seed in reversed(tuple(recipes)):
        assert grass_recipe(seed) == recipes[seed]
        assert recipes[seed]['variant']['id'] == select_floor_id(seed, catalog=CATALOG)
        assert recipes[seed]['sequence_constant'] is True
    for retired in ('sport_blue_v1','sport_terracotta_v1'):
        with pytest.raises(ValueError):
            grass_recipe(1048, floor_id=retired)
    assert random.getstate() == state
