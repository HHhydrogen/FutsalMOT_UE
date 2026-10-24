"""0帧路径边界失败后的独立a02；仅路径引用适配，原缓存/模型/数值不改。"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
SPEC=importlib.util.spec_from_file_location('v4_explicit_recovery_inputs_for_path_a02',PROJECT/'tools/pose17_ops/run_v4_tracking_after_cim_a01.py')
R=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(R)
SPEC2=importlib.util.spec_from_file_location('v4_registered_same_entity_path_adapter',PROJECT/'tools/pose17_ops/association_path_adapter_a02.py')
P=importlib.util.module_from_spec(SPEC2);SPEC2.loader.exec_module(P)

def configure():
    R.configure();A=R.A
    failed_root=A.OUTPUT;failed_state=failed_root/'driver_state.json';failed=A.read(failed_state)
    A.require(failed.get('status')=='stopped_preserved_no_replay' and failed.get('completed')==[]
        and len(failed.get('subprocesses',[]))==1 and failed['subprocesses'][0]['tag']=='R3_20261024.attachment'
        and failed['subprocesses'][0].get('exit_code')==1,'旧attempt并非明确首attachment前置失败，不自动重做')
    stderr=failed_root/'R3_seed20261024/logs/R3_20261024.attachment.stderr.log'
    A.require('固定JSONL身份/边界改变' in stderr.read_text(encoding='utf-8')
        and not (failed_root/'R3_seed20261024/attachment').exists(),'旧失败并非0帧文本边界失败，保留等待诊断')
    evidence=P.preflight()
    A.OUTPUT=P.OUTPUT;A.STATE=A.OUTPUT/'driver_state.json';A.LOCK=A.ROOT/'v4_association_path_a02.lock'
    original_sources=A.source_bindings
    def sources():
        return dict(original_sources(),**{str(Path(__file__)):A.sha(__file__),str(Path(P.__file__)):A.sha(P.__file__),
            str(failed_state):A.sha(failed_state),str(stderr):A.sha(stderr)})
    A.source_bindings=sources
    original_context=A.association_context
    def context():
        result=original_context();result['explicit_path_adapter']=evidence
        result['failed_zero_frame_attempt']=dict(path=str(failed_state),sha256=A.sha(failed_state),
            original_attempt_preserved=True,GPU_inference_started=False)
        return result
    A.association_context=context
    def adapt(original,operation):
        def command(*args):
            old=original(*args)
            return [old[0],'-B',str(P.__file__),operation]+old[2:]
        return command
    A.attachment_command=adapt(A.attachment_command,'attachment')
    A.tracking_command=adapt(A.tracking_command,'tracking')
    A.metric_command=adapt(A.metric_command,'metrics')
    return A

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--driver-sha256')
    args=parser.parse_args()
    if args.execute:R.A.require(args.driver_sha256==R.A.sha(__file__),'root执行需绑定a02入口SHA')
    A=configure()
    sys.argv=[str(A.__file__)]+(['--execute','--driver-sha256',A.sha(A.__file__)] if args.execute else [])
    A.main()

if __name__=='__main__':main()
