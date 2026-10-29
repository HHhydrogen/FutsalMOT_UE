"""统一每场随机配置；协调既有算法，保持独立命名空间及旧sidecar契约。"""
import hashlib
import json
import os
from pathlib import Path
from copy import deepcopy

from .appearance import build_appearance_manifest, write_appearance_manifest
from .environment import build_environment_manifest, write_environment_manifest
from .floor_diversity import _hash
from .grass_detail import grass_recipe
from .number_uv_plan import build_plan

SCHEMA = 'futsalmot_seeded_episode_v1'
FILES = {'appearance':'appearance.json','weather':'environment.json',
         'numbers':'number_uv.json','floor':'floor.json','cameras':'cameras.json'}


def enabled(profile):
    config = profile.get('seeded_episode')
    if config is None:
        return False
    if not isinstance(config, dict) or set(config) - {'enabled','floor_enabled','floor_id','camera_rig'}:
        raise ValueError('seeded_episode包含未知配置')
    if type(config.get('enabled')) is not bool:
        raise ValueError('seeded_episode.enabled必须是bool')
    if 'floor_enabled' in config and type(config['floor_enabled']) is not bool:
        raise ValueError('seeded_episode.floor_enabled必须是bool')
    return config['enabled']


def build_episode_recipe(meta, frames_path, profile):
    """集中解析既有外观/天气/号码和绿色地板，绝不重设全局RNG。"""
    if not enabled(profile):
        raise ValueError('统一入口未启用')
    frames_path = Path(frames_path)
    randomness = deepcopy(meta['randomness'])
    seed = randomness['root_seed']
    if type(seed) is not int or not 0 <= seed <= 0x7fffffff:
        raise ValueError('root_seed必须是0..2147483647整数')
    parts = {}
    if profile.get('appearance') is not None:
        parts['appearance'] = build_appearance_manifest(meta,frames_path,profile['appearance'])
    if profile.get('environment_profile') is not None:
        parts['weather'] = build_environment_manifest(meta,frames_path,profile['environment_profile'])
    if (profile.get('uv_numbering') or {}).get('enabled'):
        if 'appearance' not in parts:
            raise ValueError('UV号码要求启用原appearance')
        parts['numbers'] = build_plan(parts['appearance'],profile['uv_numbering'])
    config = profile['seeded_episode']
    if config.get('floor_enabled',True):
        parts['floor'] = grass_recipe(seed,floor_id=config.get('floor_id'))
    if config.get('camera_rig') is not None:
        from .camera_rig import build_camera_plan
        parts['cameras'] = build_camera_plan(seed,config['camera_rig'])
    record = {'schema':SCHEMA,'version':1,'episode_id':meta['episode_id'],
              'randomness':randomness,'trajectory_sha256':hashlib.sha256(frames_path.read_bytes()).hexdigest(),
              'components':parts}
    record['fingerprint'] = _hash(record)
    return record


def _write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    try:
        with temp.open('w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
        os.replace(temp,path)
    finally:
        if temp.exists():
            temp.unlink()


def prepare_episode_recipe(episode_dir, profile):
    """一次生成并写旧消费者所需sidecar，最后写完整清单作为完成标识。"""
    episode_dir = Path(episode_dir)
    meta = json.loads((episode_dir/'meta.json').read_text(encoding='utf-8'))
    recipe = build_episode_recipe(meta,episode_dir/'frames.jsonl',profile)
    prov = episode_dir/'provenance'
    if (prov/'seeded_episode.json').exists():
        return load_episode_recipe(episode_dir,profile)
    for name, value in recipe['components'].items():
        path = prov/FILES[name]
        if path.exists() and json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError('已有随机清单不同，拒绝覆盖: '+path.name)
    for name, value in recipe['components'].items():
        if name == 'appearance':
            write_appearance_manifest(episode_dir,value)
        elif name == 'weather':
            write_environment_manifest(episode_dir,value)
        else:
            _write(prov/FILES[name],value)
    _write(prov/'seeded_episode.json',recipe)
    return recipe


def load_episode_recipe(episode_dir, profile):
    """验证清单和实际输入/sidecar相符；运行时消费已登记结果。"""
    episode_dir = Path(episode_dir)
    prov = episode_dir/'provenance'
    actual = json.loads((prov/'seeded_episode.json').read_text(encoding='utf-8'))
    meta = json.loads((episode_dir/'meta.json').read_text(encoding='utf-8'))
    expected = build_episode_recipe(meta,episode_dir/'frames.jsonl',profile)
    if actual != expected:
        raise ValueError('统一随机清单与当前输入或配置不符')
    for name,value in actual['components'].items():
        if json.loads((prov/FILES[name]).read_text(encoding='utf-8')) != value:
            raise ValueError('统一随机清单与sidecar不符: '+FILES[name])
    return actual
