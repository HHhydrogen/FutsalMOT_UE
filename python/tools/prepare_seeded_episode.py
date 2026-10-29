"""为已有轨迹生成统一每场随机清单，不重跑GRF或渲染。"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from grf_ue_bridge.seeded_episode import prepare_episode_recipe


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolved-task',type=Path,required=True)
    args=parser.parse_args()
    task=json.loads(args.resolved_task.read_text(encoding='utf-8'))
    recipe=prepare_episode_recipe(task['trajectory_output'],task['ue_profile'])
    print(json.dumps({'fingerprint':recipe['fingerprint'],'components':list(recipe['components']),
                      'path':str(Path(task['trajectory_output'])/'provenance/seeded_episode.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
