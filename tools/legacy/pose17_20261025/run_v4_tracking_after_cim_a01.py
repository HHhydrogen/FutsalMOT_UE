"""显式恢复身份入口：关联原数值不变，只选择独立恢复权威state。"""
import argparse
import importlib.util
from pathlib import Path
import sys

PROJECT=Path('D:/projects/FutsalMOT_UEDataset')
SPEC=importlib.util.spec_from_file_location('original_v4_association_readonly_after_recovery',PROJECT/'tools/pose17_ops/run_poseonly_v4_association_a01.py')
A=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(A)
RECOVERY=A.H.ROOT/'recovery_cim_a01'

def configure():
    A.require(A.sha(A.__file__)=='adf825a023a3161ad58bc6e65fc15257367ad8610cd3021ee79b22b2d2cbcc1d','原关联source发生变化')
    A.TRAIN_STATE=RECOVERY/'driver_state.json'
    original_sources=A.source_bindings
    def sources():
        return dict(original_sources(),**{str(Path(__file__)):A.sha(__file__),
            str(PROJECT/'tools/pose17_ops/recover_v4_after_cim_a01.py'):A.sha(PROJECT/'tools/pose17_ops/recover_v4_after_cim_a01.py'),
            str(RECOVERY/'recovery_receipt.json'):A.sha(RECOVERY/'recovery_receipt.json')})
    A.source_bindings=sources

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--driver-sha256')
    args=parser.parse_args()
    if args.execute:A.require(args.driver_sha256==A.sha(__file__),'root需绑定恢复关联入口SHA')
    configure()
    if not A.TRAIN_STATE.exists() or not (RECOVERY/'recovery_receipt.json').exists():
        A.require(not args.execute,'独立恢复未完成，禁止关联')
        print('{"status":"blocked_recovery_training_not_complete","launch_authorized_by_this_preflight":false}');return
    receipt=A.read(RECOVERY/'recovery_receipt.json')
    A.require(receipt.get('status')=='completed_without_optimizer_replay' and receipt.get('fifth_train_optimizer_replayed_updates')==0,
        '恢复收据不符，禁止将旧失败driver冒充成功')
    # 显式改输入权威，而非篡改旧driver文件或将旧失败state写为成功。
    sys.argv=[str(A.__file__)]+(['--execute','--driver-sha256',A.sha(A.__file__)] if args.execute else [])
    A.main()

if __name__=='__main__':main()
