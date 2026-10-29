"""完整单seed工具；prepare只采源，freeze只绑定输入，export只后处理既有采集。"""
import argparse
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'python/src'))


def main():
    from grf_ue_bridge.single_seed import prepare_source,freeze_inputs
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','freeze','export','verify'))
    parser.add_argument('--attempt',default='single_seed_s1048_a01')
    parser.add_argument('--request',type=Path,default=PROJECT/'python/configs/single_seed_generation_v1.json')
    parser.add_argument('--short',action='store_true')
    args=parser.parse_args();local=PROJECT/'Saved/SingleSeed'/args.attempt
    if args.action=='prepare':
        result={'local':str(prepare_source(PROJECT,args.attempt,args.request))}
    elif args.action=='freeze':
        result=freeze_inputs(PROJECT,local)
        result={k:result[k] for k in ('attempt_id','frame_count','seed_id','code_bundle_sha256')}
    else:
        from grf_ue_bridge.single_seed_export import export_seed,verify_seed
        result=(export_seed if args.action=='export' else verify_seed)(PROJECT,local,short=args.short)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
