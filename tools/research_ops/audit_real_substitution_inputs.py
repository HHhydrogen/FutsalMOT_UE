"""只读核验额外真实窗口与公开比赛元数据；不下载、不推理、不训练。"""
import argparse
from collections import Counter,defaultdict
import configparser
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import pose_mechanism_core as core


def frame_set(windows):
    return {(w['sequence'],i) for w in windows for i in [*w['history_frame_indices'],w['candidate_frame_index']]}


def audit(protocol,output):
    rt,old,runtime,train,numeric,base,numbers=core.reference(protocol)
    path=Path('D:/projects/FutsalMOT_Research/code/1ddcf191b3f33c3d350cdab64011721ae99854680b1b1d2f3eef4c2592a69806/tools/research_ops/v8_pairs.py')
    core.require(core.sha(path)=='522d00e3767fe4413d44a90510088407bbfa66b444e6e2e6b473764a020208ef','原窗口规则改变')
    pairs=core.load('substitution_frozen_v8_pairs',path)
    from grf_ue_bridge.learned_association_features_v8 import candidate_gate
    available={}
    for seq,source in old['sources'].items():
        if seq not in rt.OLD:continue
        frames,_=pairs.load_source(source)
        available[seq]=list(pairs.enumerate_windows(source,frames,candidate_gate))
    output=runtime.storage().physical_child(output,core.V);core.require(not output.exists(),'新资源审计输出，不覆盖');output.mkdir(parents=True)
    folds={}
    for fold,refs in train['folds'].items():
        base_pool=core.rows(core.checked(refs['real_pool']));base_ids={w['window_uid'] for w in base_pool};base_frames=frame_set(base_pool)
        allowed=sorted({w['sequence'] for w in base_pool});heldout=next(s for s,f in rt.OLD.items() if f==fold)
        core.require(len(allowed)==2 and heldout not in allowed,'额外R不能来自heldout比赛')
        candidates={s:sorted([w for w in available[s] if w['window_uid'] not in base_ids],key=lambda w:w['window_uid']) for s in allowed}
        enough=all(len(w)>=500 for w in candidates.values());selected=[w for s in allowed for w in candidates[s][:500]] if enough else []
        selected_frames=frame_set(selected);shared=selected_frames&base_frames
        if enough:
            core.require(len({w['window_uid'] for w in selected})==1000 and not ({w['window_uid'] for w in selected}&base_ids),'额外窗口UID重复或与base重叠')
            p=output/(fold+'_extra_R_window_candidates.jsonl')
            with p.open('x',encoding='utf-8') as stream:
                for w in selected:
                    stream.write(core.canonical(dict(window_uid=w['window_uid'],sequence=w['sequence'],game=w['game'],
                        history_frame_indices=w['history_frame_indices'],candidate_frame_index=w['candidate_frame_index'],
                        all_pairs=len(w['candidates']),known_pairs=sum(c['label'] is not None for c in w['candidates']),
                        source='existing_observed_train_cache_not_newly_acquired_images'))+'\n')
            manifest=core.ref(p)
        else:manifest=None
        folds[fold]=dict(allowed_sequences=allowed,heldout_excluded=heldout,base_unique_windows=len(base_ids),
            available_unused_window_UIDs={s:len(v) for s,v in candidates.items()},enough_500_each=enough,
            candidate_manifest=manifest,selected_unique_windows=len(selected),base_unique_source_frames=len(base_frames),
            selected_unique_source_frames=len(selected_frames),source_frames_shared_with_base=len(shared),
            source_frame_overlap_fraction=len(shared)/len(selected_frames) if selected_frames else None,
            genuinely_new_source_frames=len(selected_frames-base_frames),
            annotation_time_saved_measured=False,interpretation='unused window supervision is not necessarily new images or annotations')
    # 只读取官方train索引和已存在gameinfo；不读取test索引/标签。
    public=Path('D:/projects/FutsalMOT_Research/public/soccernet_tracking');zip_index=core.read(public/'train_zip_index.json')
    extra_sequences=[]
    for seq in zip_index['sequences']:
        if seq in rt.OLD:continue
        meta=public/'train'/seq/'gameinfo.ini'
        if meta.is_file():
            info=configparser.ConfigParser();info.read(meta,encoding='utf-8-sig')
            extra_sequences.append(dict(sequence=seq,game='game'+info['Sequence']['gameID'],gameinfo=core.ref(meta),images_or_predictions_not_verified=True))
    inventory_path=Path('D:/projects/FutsalMOT_UEDataset/Saved/ResearchBuild/v10_validation_inventory_a01.json')
    inventory=core.read(inventory_path);selections=core.read(Path('D:/projects/FutsalMOT_UEDataset/Saved/ResearchBuild/v10_new_match_selection_a01.json'))
    observed_video_ids={x[2:].rsplit('_c',1)[0] for x in rt.EXTERNAL};videos=defaultdict(list)
    for seq in inventory['val_sequences']:videos[seq[2:].rsplit('_c',1)[0]].append(seq)
    all_videos=[dict(video_id=k,title=inventory['video_titles'].get(k,{}).get('title'),title_error=inventory['video_titles'].get(k,{}).get('error'),
        official_val_clips=sorted(v),already_observed_in_v10=k in observed_video_ids,actual_match_identity_verified=False) for k,v in sorted(videos.items())]
    result=dict(schema='real_substitution_input_feasibility_v1',status='complete_local_metadata_and_unused_window_audit_no_training',
        v10_protocol=core.ref(protocol),original_window_rule=core.ref(path),folds=folds,
        train_archive_index=core.ref(public/'train_zip_index.json'),additional_local_gameinfo=extra_sequences,
        val_source_inventory=core.ref(inventory_path),val_videos=all_videos,
        no_new_real_images_downloaded=True,models_trained=False,optimizer_updates=0,test_read=False,
        independent_matches_not_certified_from_title_alone=True,
        limitations=['same-source unused windows support exposure comparison, not an annotation-cost saving claim',
            'video IDs and clips are not automatically distinct matches; identity must be verified',
            'new independent match sample size and noninferiority margin must be frozen before C outcomes'])
    with (output/'report.json').open('x',encoding='utf-8') as stream:stream.write(core.canonical(result)+'\n')
    return dict(status=result['status'],folds=folds,val_videos=all_videos,additional_local_gameinfo=extra_sequences)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--v10-protocol',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execute',action='store_true');a=p.parse_args()
    print(core.canonical(audit(a.v10_protocol,a.output) if a.execute else dict(status='readonly_real_substitution_feasibility_plan')))
