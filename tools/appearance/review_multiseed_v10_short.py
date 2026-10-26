"""v10短样一次元数据核验与三张QA总览；视觉通过由root另签。"""
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'python/src'));sys.path.insert(0,str(ROOT/'python/ue'))
from grf_ue_bridge.storage_policy import physical_child,DATASET_ROOT
from pose17_multiseed_v10_contract import WINDOWS
from pose17_seeded_kit_contract import assert_seeded_kit_receipt,require
from pose17_native_receipt import normalize_native_receipt
from PIL import Image,ImageDraw

RUN=ROOT/'Saved/AppearancePlanning/multiseed_v10_a01'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
rows=lambda p:[json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s.strip()]


def main():
    state=read(RUN/'control_short_a01/state.json')
    require(state['status']=='complete_short_exports_EXR_retired_wait_root_visual_review'
        and len(state['completed'])==3 and (state['rgb'],state['mask'],state['person_pose'])==(36,36,360), '短样/导出/退休未完整')
    output=physical_child(DATASET_ROOT/'_staging/v10_short_a01_review',DATASET_ROOT)
    require(not output.exists() and not (RUN/'short_review_candidates.json').exists(),'已有QA不重复覆盖')
    output.mkdir();proof=dict(status='await_root_visual_review',root_visual_reviewed=False,
        rgb=36,mask=36,person_pose=360,test_read=False,physical_visibility_verified=False,seeds=[])
    for item in state['completed']:
        seed=item['seed'];start,_,_=WINDOWS[seed];stage=physical_child(Path(item['stage']),DATASET_ROOT)
        require(item['normal_UE_exit'] is True and item['EXR_deleted']==12,'UE退出/EXR未闭合')
        group=read(stage/'group.json');plan=read(group['plan']['path'])
        require(group['capture_experiment']=='multiseed_v10_a01' and group['source_frame_range']==[start,start+3]
            and group['diagnostic_only'] is True and group['not_training'] is True,'新scope/范围或限制不符')
        sheet=Image.new('RGB',(1280,960),(235,235,235));draw=ImageDraw.Draw(sheet)
        people={};worlds={};cameras=list(group['cameras']);native_refs=[]
        require(cameras==['CineCam_01','CineCam_02','CineCam_03','CineCam_04'],'实际四cam不完整')
        for index,cam in enumerate(cameras):
            directory=stage/'cameras'/cam;poses=rows(directory/'pose2d.jsonl');world=rows(directory/'pose3d_world.jsonl')
            require(len(poses)==len(world)==30,'每cam三帧十人不完整')
            expected={(i,e) for i in range(3) for e in ('L0','L1','L2','L3','L4','R0','R1','R2','R3','R4')}
            require({(r['frame_index'],r['entity_id']) for r in poses}==expected
                and {(r['frame_index'],r['entity_id']) for r in world}==expected
                and all(r['source_frame_index']==start+r['frame_index'] and r['visibility_state']==['unknown']*17
                    and len(r['uv_px'])==17 for r in poses),'人物/时间/Pose/unknown契约改变')
            require(all(len(r['world_m'])==17 and all(len(p)==3 and all(math.isfinite(v) for v in p) for p in r['world_m'])
                for r in world),'world非有限17点')
            receipt=group['cameras'][cam]['native_receipt'];native=normalize_native_receipt(read(receipt['path']))
            assert_seeded_kit_receipt(plan,native);native_refs.append(receipt)
            people[cam]=[r for r in poses if r['frame_index']==1]
            worlds[cam]={(r['frame_index'],r['entity_id']):r['world_m'] for r in world}
            with Image.open(directory/'rgb/000001.png') as image:
                require(image.size==(3840,2160),'非原生4K')
                sheet.paste(image.convert('RGB').resize((640,360)),((index%2)*640,(index//2)*360))
            x,y=(index%2)*640,(index//2)*360
            draw.rectangle((x,y,x+630,y+22),fill='white')
            draw.text((x+4,y+4),f'{seed} {cam} source={start+1} {item["floor_id"]}',fill='black')
        role_selections=[]
        for index,(entity,role) in enumerate((('L0','Left GK'),('L1','Left outfield'),('R0','Right GK'),('R1','Right outfield'))):
            person,cam=max(((next(p for p in values if p['entity_id']==entity),cam) for cam,values in people.items()),
                           key=lambda q:(q[0]['visible_mask_area'],q[1]))
            require(person['visible_mask_area']>0,'角色四cam均不可辨认，不能视觉验收')
            x,y,w,h=person['bbox_visible_xywh'];pad=max(5,int(max(w,h)*.08))
            box=(max(0,x-pad),max(0,y-pad),min(3840,x+w+pad),min(2160,y+h+pad))
            with Image.open(stage/'cameras'/cam/'rgb/000001.png') as image:crop=image.convert('RGB').crop(box)
            crop.thumbnail((150,195));left=index*320
            sheet.paste(crop,(left+(150-crop.width)//2,750));overlay=crop.copy();od=ImageDraw.Draw(overlay)
            sx,sy=crop.width/(box[2]-box[0]),crop.height/(box[3]-box[1])
            for point in person['uv_px']:
                if point is not None:
                    px,py=(point[0]-box[0])*sx,(point[1]-box[1])*sy
                    od.ellipse((px-2,py-2,px+2,py+2),fill=(255,40,40))
            sheet.paste(overlay,(left+160+(150-overlay.width)//2,750))
            binding=next(r for r in group['original_seeded_kit_binding']['entities'] if r['entity_id']==entity)
            draw.text((left+4,724),f'{entity} {role} Set{binding["kit_set_id"]}',fill='black')
            draw.text((left+4,738),'RGB / projected joints (visibility unknown)',fill='black')
            role_selections.append(dict(entity=entity,camera=cam,kit_set_id=binding['kit_set_id'],visible_mask_pixels=person['visible_mask_area']))
        reference=worlds[cameras[0]];comparisons={}
        for cam in cameras[1:]:
            maximum=max(math.dist(a,b) for key in reference for a,b in zip(reference[key],worlds[cam][key]))
            comparisons[cam]=dict(exact=reference==worlds[cam],max_delta_m=maximum)
        motion={e:max(math.dist(a,b) for a,b in zip(reference[(0,e)],reference[(2,e)])) for e in ('L1','L2','L3','L4','R1','R2','R3','R4')}
        require(max(motion.values())>0,'全部外场world静止，需诊断')
        path=output/f'seed_{seed:08d}_QA.png';sheet.save(path)
        proof['seeds'].append(dict(seed=seed,sheet=str(path),roles=role_selections,native_receipts=native_refs,
            world_cross_camera=comparisons,world_values_modified=False,observed_0_to_2_max_joint_displacement_m=motion))
    with (RUN/'short_review_candidates.json').open('x',encoding='utf-8') as stream:json.dump(proof,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=proof['status'],sheets=[r['sheet'] for r in proof['seeds']]),ensure_ascii=False))


if __name__=='__main__':main()
