"""新生成使用的细草纹绿色目录；历史地板目录及随机算法保留。"""
from copy import deepcopy

from .floor_diversity import NAMESPACE, _hash, select_floor_id

CATALOG_ID = 'green_fine_grass_v2'
MATERIAL_ROOT = '/Game/FutsalMOT/Environment/Floors/GreenV2'
PARAMETERS = {
    'GrassUVTiling': 60.0,
    'GrassNormalFlatness': 0.90,
    'GrassStripeContrast': 0.18,
}
# 只改变明暗，全部保留绿色草地；每场固定一档。
CATALOG = (
    {'id': 'grass_dark_v2', 'albedo_gain_linear': [0.60, 0.60, 0.60]},
    {'id': 'grass_standard_v2', 'albedo_gain_linear': [1.0, 1.0, 1.0]},
    {'id': 'grass_light_v2', 'albedo_gain_linear': [1.50, 1.50, 1.50]},
)


def grass_recipe(seed, *, floor_id=None):
    """复用既有地板独立namespace，不消耗其他随机流或改历史清单。"""
    selected = select_floor_id(seed, catalog=CATALOG)
    if floor_id is not None:
        selected = floor_id
    choices = [v for v in CATALOG if v['id'] == selected]
    if len(choices) != 1:
        raise ValueError('新生成只支持GreenV2绿色草地: ' + str(selected))
    variant = deepcopy(choices[0])
    name = 'MI_' + selected
    return {
        'catalog_id': CATALOG_ID,
        'catalog_sha256': _hash(CATALOG),
        'selection_namespace': NAMESPACE,
        'seed': seed,
        'sequence_constant': True,
        'selection_mode': 'explicit' if floor_id is not None else 'seeded',
        'variant': variant,
        'material': MATERIAL_ROOT + '/' + name + '.' + name,
        'scalar_parameters': deepcopy(PARAMETERS),
    }
