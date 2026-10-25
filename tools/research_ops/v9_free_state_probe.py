"""三个固定motion_RS参考的自由状态观察；轨迹须逐字节等于v8，不用GT。"""
import argparse,hashlib,json,math,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];R=Path('D:/projects/FutsalMOT_Research')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def execute(config):
    cfg=read(config);require(cfg['approved_by']=='root' and cfg['new_updates']==0,'只读诊断');oldp=Path(cfg['v8_protocol']['path']);require(sha(oldp)==cfg['v8_protocol']['sha256'],'v8绑定变化');old=read(oldp);bundle=Path(old['bundle'])
    for f in cfg['code_files']:require(sha(ROOT/f['path'])==f['sha256'],'新诊断绑定变化')
    sys.path[:0]=[str(bundle/'python/src'),str(bundle/'tools/research_ops')]
    from v8_track import load_complete
    from grf_ue_bridge.learned_association_tracker_v8 import tracker_class
    import grf_ue_bridge;grf_ue_bridge.__path__.append(str(ROOT/'python/src/grf_ue_bridge'))
    from grf_ue_bridge.pose_quality_features_v9 import quality
    import numpy as np,torch
    torch.set_num_threads(1);output=Path(cfg['output']);require(not output.exists() and R/'pose/pose_quality_v9' in output.parents,'全新输出');output.mkdir(parents=True);reports=[]
    for fold in ('game4','game6','game9'):
        source=next(s for s in read(old['source_config']['path'])['sources'] if s['domain']=='real' and s['game']==fold);run=Path(cfg['v8_control'])/'runs'/fold/'20261024';motion,normalizer,_=load_complete(run/'motion_RS/training',old,sha(oldp),fold);pose,_,_=load_complete(run/'pose_RS/training',old,sha(oldp),fold);pending=[];stats=[]
        class ObserveNormalizer:
            def transform(self,raw,*,use_pose):pending.append((normalizer.transform(raw,use_pose=True),quality(raw)));return normalizer.transform(raw,use_pose=False)
        class ObserveModel(torch.nn.Module):
            def __init__(self):super().__init__();self.motion=motion;self.pose=pose
            def forward(self,x):
                actual=self.motion(x);require(len(pending)==len(x),'观察行数不符');z=torch.tensor([v[0] for v in pending],dtype=torch.float32);other=self.pose(z)
                for a,b,(_,quality_value) in zip(actual.reshape(-1).tolist(),other.reshape(-1).tolist(),pending):stats.append(dict(quality_value,motion_logit=a,pose_logit=b,acceptance_threshold_changed=(a>=0)!=(b>=0)))
                pending.clear();return actual
        tracker=tracker_class()(mode='learned',model=ObserveModel(),normalizer=ObserveNormalizer(),use_pose=True,pose_source_sha256=old['tracking']['pose_checkpoint_sha256'],fixed_detection_sha256=source['cache']['sha256']);text=[]
        for line in Path(source['cache']['path']).read_text(encoding='utf-8').splitlines():
            frame=json.loads(line)
            for row in tracker.update_frame(frame):
                x1,y1,x2,y2,identity,score=row[:6];text.append(','.join(map(str,[frame['frame_number'],int(identity),float(x1),float(y1),float(x2-x1),float(y2-y1),float(score),-1,-1,-1])))
        # 原v8使用Path.write_text，Windows会写CRLF；必须比较实际同方式落盘字节，不把LF字符串hash误当轨迹变化。
        observed=output/f'motion_reference_{fold}.txt';observed.write_text('\n'.join(text)+'\n',encoding='utf-8')
        actual=sha(observed);reference=read(run/'motion_RS/tracking/receipt.json');require(actual==reference['mot_sha256'],'自由状态观察改变了基线轨迹，不报告为通过')
        count=len(stats);common=np.array([s['common_limbs'] for s in stats]);native_fraction=float(np.mean([abs(s['history_dt_sec']-.04)<1e-8 for s in stats]));changes=[s['shape_change_proxy'] for s in stats if s['shape_change_proxy'] is not None]
        reports.append(dict(fold=fold,seed=20261024,actual_candidates=count,reference_MOT_exact=True,reference_MOT_sha256=actual,common_limbs_lt6_fraction=float((common<6).mean()),non_native_last_history_fraction=1-native_fraction,shape_change_proxy_median=float(np.median(changes)) if changes else None,pose_vs_motion_acceptance_changed=sum(s['acceptance_threshold_changed'] for s in stats),mean_absolute_logit_difference=float(np.mean([abs(s['motion_logit']-s['pose_logit']) for s in stats])),GT_read=False))
        print(json.dumps(reports[-1]),flush=True)
    result=dict(status='complete_three_fixed_free_motion_reference_states',reports=reports,new_updates=0,GPU_used=False,test_read=False,limits='prediction sensitivity/quality on actual motion states, not GT accuracy or alternate tracker result')
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']='-1';execute(a.config)
