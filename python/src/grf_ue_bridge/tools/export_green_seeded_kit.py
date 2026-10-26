"""绿色独立导出准入，复用原生/采样/mask数值和实际EXR消费链。"""
import argparse
import json
from pathlib import Path
from grf_ue_bridge.tools import export_seeded_kit_pair as base
from grf_ue_bridge.tools import export_seeded_kit_camera as camera


def metadata(attempt):
    plan=base.read(attempt/'plan.json')
    base.require(plan.get('green_seeded_kit_contract') is True,'非独立绿色准入')
    result=(camera.metadata if (attempt/'capture_scope.json').exists() else base.metadata)(attempt)
    _,state,*_=result
    restored=state.get('green_floor_restored',{})
    base.require(restored.get('status')=='original_floor_slot_restored_not_saved'
        and restored.get('non_floor_context_unchanged') is True,'绿色或其他场景上下文未恢复')
    applied=state.get('green_floor_transaction',{})
    base.require(applied.get('target_material')==plan['seeded_kit_pair']['green_floor']['material']
        and applied.get('status')=='preview_active','缺实际新绿色应用证据')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attempt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();print(json.dumps(base.export(a.attempt,a.output,a.workers,metadata_loader=metadata),ensure_ascii=False))


if __name__=='__main__':main()
