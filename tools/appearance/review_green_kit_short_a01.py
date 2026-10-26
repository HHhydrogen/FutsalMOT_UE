"""一次绿色短样元数据配对和总览；真实图像由root审阅后另签验收。"""
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'))
from grf_ue_bridge.storage_policy import physical_child,DATASET_ROOT
from PIL import Image,ImageDraw
import numpy as np

RUN=ROOT/'Saved/AppearancePlanning/green_seeded_kit_a01'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(encoding='utf-8') as f:return [json.loads(s) for s in f if s.strip()]


def compare(a,b,proof,key):
    ga,gb=read(a/'group.json'),read(b/'group.json')
    for camera in ga['cameras']:
        ca,cb=a/'cameras'/camera,b/'cameras'/camera
        proof['camera_exact'][key+'/'+camera]=read(ca/'view.json')==read(cb/'view.json')
        wa,wb=rows(ca/'pose3d_world.jsonl'),rows(cb/'pose3d_world.jsonl')
        if len(wa)!=30 or len(wb)!=30:raise ValueError('短样真实30人帧记录不完整')
        exact=True;maximum=0.0
        for p,q in zip(wa,wb):
            keys=('frame_index','source_frame_index','entity_id','mesh_identity','manifest_sha256')
            if any(p[k]!=q[k] for k in keys):raise ValueError('配对帧/身份/校准不同')
            exact &= p['world_m']==q['world_m']
            maximum=max(maximum,max(math.dist(x,y) for x,y in zip(p['world_m'],q['world_m'])))
        proof['world_pairs'][key+'/'+camera]=dict(exact=exact,max_delta_m=maximum)
        with Image.open(ca/'mask/000001.png') as x,Image.open(cb/'mask/000001.png') as y:
            proof['middle_mask_different_pixels'][key+'/'+camera]=int(np.count_nonzero(np.asarray(x)!=np.asarray(y)))


def main():
    state=read(RUN/'control_short_a01/state.json')
    if state['status']!='complete_short_exports_EXR_retired_wait_root_visual_review' or len(state['completed'])!=8:
        raise RuntimeError('全部短样及EXR退休未完成，不作验收')
    if (state['rgb'],state['mask'],state['person_pose'])!=(96,96,960):raise ValueError('实际导出总量不同')
    out=physical_child(DATASET_ROOT/'_staging/greenkit_short_a01_review',DATASET_ROOT);out.mkdir(exist_ok=False)
    items=state['completed'];proof=dict(status='await_root_visual_review',root_visual_reviewed=False,
        total_RGB=96,total_mask=96,person_pose=960,main_RGB=48,palette_RGB=48,
        test_read=False,world_values_modified=False,physical_visibility_verified=False,
        camera_exact={},world_pairs={},middle_mask_different_pixels={},selected_role_crops=[])
    overview=Image.new('RGB',(1280,8*360),(230,230,230));draw=ImageDraw.Draw(overview)
    roles=Image.new('RGB',(1200,8*230),(238,238,238));rd=ImageDraw.Draw(roles);oi=ri=0
    main=[r for r in items if r['purpose']=='seeded_kit_pair']
    for seed in (1048,1102):
        pair={v:Path(next(r['stage'] for r in main if r['seed']==seed and r['variant']==v)) for v in 'AB'}
        groups={v:read(pair[v]/'group.json') for v in 'AB'}
        if groups['A']['paired_context_sha256']!=groups['B']['paired_context_sha256']:raise ValueError('A/B上下文不同')
        compare(pair['A'],pair['B'],proof,str(seed)+'/AB')
        people={v:{} for v in 'AB'}
        for camera in groups['A']['cameras']:
            for col,v in enumerate('AB'):
                with Image.open(pair[v]/'cameras'/camera/'rgb/000001.png') as image:
                    overview.paste(image.convert('RGB').resize((640,360)),(640*col,360*oi))
                draw.rectangle((640*col,360*oi,640*col+620,360*oi+22),fill='white')
                draw.text((640*col+4,360*oi+4),f'{seed} {camera} {v} {groups[v]["green_floor"]["id"]}',fill='black')
                people[v][camera]=[p for p in rows(pair[v]/'cameras'/camera/'pose2d.jsonl') if p['frame_index']==1]
            oi+=1
        for entity,role in (('L0','Left GK'),('L1','Left outfield'),('R0','Right GK'),('R1','Right outfield')):
            choices=[]
            for camera in people['A']:
                a=next(p for p in people['A'][camera] if p['entity_id']==entity)
                b=next(p for p in people['B'][camera] if p['entity_id']==entity)
                choices.append((min(a['visible_mask_area'],b['visible_mask_area']),camera,a,b))
            area,camera,a,b=max(choices,key=lambda c:(c[0],c[1]))
            if area<=0:raise ValueError('四机位都无可辨角色像素，不能伪造配色验收')
            rd.text((10,ri*230+5),f'{seed} {entity} {role} {camera}',fill='black')
            for col,(v,person) in enumerate((('A',a),('B',b))):
                x,y,w,h=person['bbox_visible_xywh'];pad=max(5,int(.05*max(w,h)))
                box=(max(0,x-pad),max(0,y-pad),min(3840,x+w+pad),min(2160,y+h+pad))
                with Image.open(pair[v]/'cameras'/camera/'rgb/000001.png') as image:
                    crop=image.convert('RGB').crop(box);crop.thumbnail((540,185))
                roles.paste(crop,(600*col+(600-crop.width)//2,ri*230+36))
                rd.text((600*col+10,ri*230+22),v+' default' if v=='A' else v+' original seeded kit',fill='black')
            proof['selected_role_crops'].append(dict(seed=seed,entity=entity,camera=camera,visible_mask_pixels=area))
            ri+=1
    variants={r['floor_id']:r for r in items if r['seed']==1048 and r['variant']=='B'}
    palette=Image.new('RGB',(1280,3*360),(235,235,235));pd=ImageDraw.Draw(palette)
    baseline=Path(next(r['stage'] for r in main if r['seed']==1048 and r['variant']=='B'))
    for index,(floor_id,row) in enumerate(sorted(variants.items())):
        stage=Path(row['stage']);compare(baseline,stage,proof,'1048/palette/'+floor_id)
        with Image.open(stage/'cameras/CineCam_01/rgb/000001.png') as image:
            palette.paste(image.convert('RGB').resize((640,360)),((index%2)*640,(index//2)*360))
        pd.rectangle(((index%2)*640,(index//2)*360,(index%2)*640+600,(index//2)*360+23),fill='white')
        pd.text(((index%2)*640+4,(index//2)*360+4),floor_id,fill='black')
    roles.save(out/'roles_AB.png');overview.save(out/'four_camera_AB.png');palette.save(out/'green_palette.png')
    proof.update(role_sheet=str(out/'roles_AB.png'),four_camera_sheet=str(out/'four_camera_AB.png'),palette_sheet=str(out/'green_palette.png'))
    with (RUN/'short_pair_review_candidates.json').open('x',encoding='utf-8') as f:json.dump(proof,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=proof['status'],camera_all_exact=all(proof['camera_exact'].values()),
        world_all_exact=all(r['exact'] for r in proof['world_pairs'].values()),
        world_max_delta_m=max(r['max_delta_m'] for r in proof['world_pairs'].values()),
        role_sheet=proof['role_sheet'],palette_sheet=proof['palette_sheet'])))


if __name__=='__main__':main()
