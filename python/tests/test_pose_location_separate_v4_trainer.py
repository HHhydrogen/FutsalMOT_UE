"""v4新入口定向CPU夹具：分域更新、G盘预检和不重放断点。"""
from copy import copy, deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

CODE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('separate_v4_cpu_fixture', CODE / 'experiments/sim2real/train_pose_location_separate_v4.py')
TOOL = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(TOOL)


def test_project_original_shared_three_without_extra_real_or_new_rng():
    selected = list(range(1000))
    source = [dict(schema='futsalmot_pose_location_paired_schedule_row_v1', update_index=i,
        shared_real_indices=[i, (i+1)%1000, (i+2)%1000], extra_real_index=(i+3)%1000, synthetic_index=i) for i in range(1000)]
    derived = TOOL.derive_schedule(source, selected)
    assert all(row['real_indices'] == source[i]['shared_real_indices'] and 'extra_real_index' not in row for i,row in enumerate(derived))
    TOOL.validate_derived_schedule(derived, source, selected)
    damaged = deepcopy(derived); damaged[0]['real_indices'].reverse()
    with pytest.raises(ValueError, match='同序'):
        TOOL.validate_derived_schedule(damaged, source, selected)


def test_G_preflight_rejects_D_media_before_dataset_hash_or_decode(tmp_path, monkeypatch):
    source = tmp_path / 'real.jsonl'
    source.write_text(json.dumps(dict(image_file='D:/unsafe_fake_data/image.png'))+'\n', encoding='utf-8')
    # 此例只隔离媒体地址门禁；临时JSONL不冒充正式Research输入。
    with monkeypatch.context() as patch:
        patch.setattr(TOOL, 'g_research_path', lambda value: Path(value))
        with pytest.raises(ValueError, match='图像实际路径必须G'):
            TOOL.preflight_data_paths(dict(real_jsonl=source, synthetic_jsonl=source, protocol={}))
    with pytest.raises(ValueError, match='禁止D fallback'):
        TOOL.g_research_path('D:/unmigrated_fake_results')


def checkpoint(context):
    return dict(schema=TOOL.SCHEMA, bindings=context['bindings'], arm=context['arm'], seed=context['seed'],
        planned_updates=1000, policy=TOOL.POLICY, normalization=TOOL.NORMALIZATION, actual_ema_fp32=True,
        keypoint_shape=[17,2], physical_output_channels=51, visibility_supervised=False,
        completed_updates=0, ema_updates=0, exposure_chain_sha256='0'*64, last_exposure=None)


def test_uncommitted_or_post_checkpoint_exposure_refused_without_mutation(tmp_path):
    context = dict(arm='R3S1', seed=1, bindings=dict(cpu_toy_only=True))
    last = checkpoint(context)
    TOOL.atomic_json(tmp_path/'update_transaction.json', dict(status='started_not_committed'))
    with pytest.raises(ValueError, match='事务'):
        TOOL.reconcile_resume(tmp_path, last, context)
    TOOL.append_exposure(tmp_path/'exposures.jsonl', dict(actual_optimizer_update=1))
    before = (tmp_path/'exposures.jsonl').read_bytes()
    with pytest.raises(ValueError, match='禁止重放'):
        TOOL.reconcile_resume(tmp_path, last, context)
    assert (tmp_path/'exposures.jsonl').read_bytes() == before


@pytest.mark.parametrize('arm', ['R3','R3S1'])
def test_two_cpu_updates_pause_resume_exact_model_ema_optimizer_and_real_exposure(tmp_path, arm):
    import torch
    import ultralytics
    from ultralytics.nn.tasks import PoseModel
    from ultralytics.utils import DEFAULT_CFG, YAML
    from ultralytics.utils.torch_utils import ModelEMA
    from grf_ue_bridge.pose_xy_head_transfer import map_pose_xy
    from grf_ue_bridge.pose_location_supervision_v4 import SeparateDomainLocationObjective
    from grf_ue_bridge.pose_location_dataset_v2 import LocationPoseDataset
    spec = importlib.util.spec_from_file_location('separate_v4_toy_images', CODE/'tools/smoke_pose_location_jsonl_cpu.py')
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    fixture.make_toy_jsonl(tmp_path/'toy')
    data = LocationPoseDataset(tmp_path/'toy/train.jsonl', 64)
    torch.set_num_threads(1); torch.manual_seed(413)
    cfg = YAML.load(Path(ultralytics.__file__).parent/'cfg/models/11/yolo11-pose.yaml'); cfg['scale']='n'
    original = map_pose_xy(PoseModel(cfg, ch=3, nc=1, verbose=False)).cpu(); original.args=copy(DEFAULT_CFG)
    original.eval(); probe=torch.rand((1,3,64,64))
    with torch.no_grad(): initial_detection=original(probe)[0][:,:5].clone()
    context=dict(arm=arm,seed=413,bindings=dict(cpu_toy_only=True,training_authorized=False))
    schedule=[dict(schema=TOOL.ROW_SCHEMA,update_index=i,real_indices=[0,0,0],synthetic_index=1) for i in range(1000)]
    context['schedule']=schedule
    def components(model):
        objective=SeparateDomainLocationObjective(model)
        optimizer=torch.optim.SGD((p for p in model.parameters() if p.requires_grad),lr=.0001,momentum=.9,weight_decay=0.)
        return objective,optimizer,ModelEMA(model)
    model=deepcopy(original); obj,opt,ema=components(model)
    full=tmp_path/'full';full.mkdir()
    result=TOOL.train_loop(model,obj,opt,ema,obj.guard,data,data,schedule,context,full,stop_after=2)
    assert result['completed_updates']==2 and result['checkpoints_saved_at_updates']==[0,2]
    obj.close()
    model=deepcopy(original);obj,opt,ema=components(model)
    paused=tmp_path/'paused';paused.mkdir()
    result=TOOL.train_loop(model,obj,opt,ema,obj.guard,data,data,schedule,context,paused,stop_after=1)
    assert result['completed_updates']==1 and result['status']=='safely_paused'
    obj.close()
    saved=torch.load(paused/'last.pt',map_location='cpu',weights_only=False)
    assert TOOL.reconcile_resume(paused,saved,context)==1
    model=saved['model'].float();obj,opt,ema=components(model)
    opt.load_state_dict(saved['optimizer']);ema.ema.load_state_dict(saved['ema'].state_dict());ema.updates=saved['ema_updates']
    TOOL.train_loop(model,obj,opt,ema,obj.guard,data,data,schedule,context,paused,completed=1,
        chain=saved['exposure_chain_sha256'],initial_hash=saved['initial_state_sha256'],last_exposure=saved['last_exposure'],stop_after=2)
    a=torch.load(full/'last.pt',map_location='cpu',weights_only=False)
    b=torch.load(paused/'last.pt',map_location='cpu',weights_only=False)
    for field in ('model','ema'):
        for name,value in a[field].state_dict().items(): assert torch.equal(value,b[field].state_dict()[name]),name
        assert torch.equal(initial_detection,b[field](probe)[0][:,:5])
    for key,value in a['optimizer']['state'].items():
        assert torch.equal(value['momentum_buffer'],b['optimizer']['state'][key]['momentum_buffer'])
    exposures=TOOL.rows(paused/'exposures.jsonl')
    assert len(exposures)==2 and sum(row['real_images'] for row in exposures)==6
    assert sum(row['synthetic_images'] for row in exposures)==(2 if arm=='R3S1' else 0)
    assert all(row['real_indices']==[0,0,0] and row['visibility_loss']==0 for row in exposures)
    assert all(row['real_domain']['images']==3 for row in exposures)
    assert TOOL.reconcile_resume(paused,b,context)==2
    obj.close()
