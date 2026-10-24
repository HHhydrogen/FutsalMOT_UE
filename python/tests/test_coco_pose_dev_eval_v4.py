"""v4评价身份定向CPU检查；随机/文本夹具，不读正式测试或训练权重。"""
from copy import deepcopy

import pytest

from grf_ue_bridge import coco_pose_dev_eval_v4 as adapter
from grf_ue_bridge import coco_pose_dev_eval as numeric


def fixture():
    tool=adapter.trainer;seed=tool.SEEDS[0];arm='R3S1';bindings=dict(cpu_fixture_only=True)
    context=dict(v4_contexts={(seed,arm):dict(bindings=bindings)})
    checkpoint=dict(schema=tool.SCHEMA,completed_updates=1000,planned_updates=1000,ema_updates=1000,
        seed=seed,arm=arm,bindings=bindings,policy=tool.POLICY,normalization=tool.NORMALIZATION,
        checkpoint_choice='last_actual_FP32_EMA_no_best',actual_ema_fp32=True,keypoint_shape=[17,2],
        physical_output_channels=51,visibility_supervised=False,initial_state_sha256='a'*64,exposure_chain_sha256='b'*64)
    run=deepcopy(checkpoint);run.update(schema=tool.RUN_SCHEMA,complete=True,real_test_read=False,
        checkpoint_choice='last1000_actual_FP32_EMA_no_best',actual_exposures=dict(real=3000,synthetic=1000))
    return checkpoint,run,context


def test_v4_full_identity_and_same_real_exposure_metadata():
    checkpoint,run,context=fixture()
    result=adapter.validate_checkpoint(checkpoint,run,context)
    assert result['role']=='last_ema_v4' and result['arm']=='R3S1'


@pytest.mark.parametrize('damage',['old_v3_schema','R4000','normalization','only999','best','binding'])
def test_reject_old_schema_changed_budget_or_missing_complete_state(damage):
    checkpoint,run,context=fixture()
    if damage=='old_v3_schema': checkpoint['schema']='futsalmot_pose_location_poseonly_checkpoint_v3'
    elif damage=='R4000': run['actual_exposures']['real']=4000
    elif damage=='normalization': run['normalization']=dict(shared_foreground_denominator=True)
    elif damage=='only999': checkpoint['completed_updates']=999
    elif damage=='best': checkpoint['checkpoint_choice']='best'
    else: checkpoint['bindings']={'wrong_source':True}
    with pytest.raises(ValueError):adapter.validate_checkpoint(checkpoint,run,context)


def test_reuses_exact_official_COCO_numeric_chain_on_same_CPU_fixture(tmp_path):
    from test_coco_pose_dev_eval import context_fixture,prediction
    path,_,_,_=context_fixture(tmp_path)
    context=numeric.load_dev_context(path,numeric.sha256(path))
    predictions=[prediction()]
    ids=context['image_ids']
    expected,_=numeric.evaluate(context,predictions,ids)
    actual,_=adapter.evaluate(context,predictions,ids)
    assert actual['schema']==adapter.VERSION
    assert actual['official_COCOeval']==expected['official_COCOeval']
    assert actual['auxiliary_location']==expected['auxiliary_location']
    assert actual['binding']==expected['binding']


def test_candidate_cannot_be_promoted_by_evaluation(tmp_path):
    path=tmp_path/'protocol.json';path.write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError):adapter.load_context(path,numeric.sha256(path),path,numeric.sha256(path))
