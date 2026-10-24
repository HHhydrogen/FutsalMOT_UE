"""v4独立身份适配；同真实曝光schema不能伪装成v3，数值链保持不变。"""
import importlib.util
from pathlib import Path

from . import coco_pose_dev_eval as numeric
from . import coco_pose_dev_eval_v3 as prior

VERSION='futsalmot_coco_pose_dev_evaluation_v4'
NUMERICAL_SOURCE_SHA256=prior.NUMERICAL_SOURCE_SHA256
CODE=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('v4_evaluator_readonly_trainer_contract',CODE/'experiments/sim2real/train_pose_location_separate_v4.py')
trainer=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(trainer)
require=numeric.require


def source_bindings():
    return [trainer.bind(path) for path in (Path(__file__),CODE/'experiments/sim2real/evaluate_coco_pose_location_v4.py',Path(prior.__file__),Path(numeric.__file__))]


def load_context(protocol_path,protocol_sha256,admission_path,admission_sha256):
    """只读冻结来源/六文本上下文与dev200；不解码媒体或改变旧协议。"""
    require(numeric.sha256(numeric.__file__)==NUMERICAL_SOURCE_SHA256,'原COCO数值链发生变化')
    protocol_path=trainer.g_research_path(protocol_path);admission_path=trainer.g_research_path(admission_path)
    protocol=numeric.checked_json(protocol_path,protocol_sha256);admission=numeric.checked_json(admission_path,admission_sha256)
    require(protocol.get('evaluation',{}).get('source_files')==admission.get('evaluation_source_files')==source_bindings(),
            '缺v4独立评价源码绑定')
    manifest=trainer.bound_file(protocol['schedule_manifest'])
    contexts={}
    for seed in trainer.SEEDS:
        for arm in trainer.ARMS:
            contexts[(seed,arm)]=trainer.validate_inputs(protocol_path,manifest,admission_path,seed,arm)
    old=prior.load_context(trainer.bound_file(protocol['source_v3_protocol']),protocol['source_v3_protocol']['sha256'],
        trainer.bound_file(protocol['source_v3_admission']),protocol['source_v3_admission']['sha256'])
    context=dict(old)
    context.update(protocol=protocol,protocol_sha256=protocol_sha256,v4_admission_sha256=admission_sha256,
        v4_contexts=contexts,v4_evaluation_source_files=source_bindings())
    context['binding']=dict(old['binding'],protocol_sha256=protocol_sha256,admission_sha256=admission_sha256,
        source_v3_protocol_sha256=protocol['source_v3_protocol']['sha256'],
        source_v3_admission_sha256=protocol['source_v3_admission']['sha256'],schedule_manifest_sha256=numeric.sha256(manifest))
    return context


def validate_checkpoint(checkpoint,run,context):
    require(checkpoint.get('schema')==trainer.SCHEMA and run.get('schema')==trainer.RUN_SCHEMA,'v4拒绝旧v2/v3 checkpoint/run身份')
    require(all(type(checkpoint.get(k)) is int and checkpoint[k]==1000 for k in ('completed_updates','planned_updates','ema_updates')),
        'v4必须是完整last1000/EMA1000')
    require(run.get('complete') is True and type(run.get('completed_updates')) is int
        and run['completed_updates']==run.get('planned_updates')==1000,'v4运行未完成')
    seed=checkpoint.get('seed');arm=checkpoint.get('arm')
    require(type(seed) is int and (seed,arm) in context['v4_contexts'] and run.get('seed')==seed and run.get('arm')==arm,'v4 arm/seed不符')
    expected=context['v4_contexts'][(seed,arm)]
    require(checkpoint.get('bindings')==run.get('bindings')==expected['bindings'],'v4完整新身份/原shared3来源链不符')
    require(checkpoint.get('policy')==run.get('policy')==trainer.POLICY
        and checkpoint.get('normalization')==run.get('normalization')==trainer.NORMALIZATION,'v4分域/冻结策略错误')
    require(run.get('actual_exposures')==dict(real=3000,synthetic=1000 if arm=='R3S1' else 0),'v4同真实曝光预算错误')
    require(checkpoint.get('checkpoint_choice')=='last_actual_FP32_EMA_no_best'
        and run.get('checkpoint_choice')=='last1000_actual_FP32_EMA_no_best','v4拒绝best或非最终EMA')
    for record in (checkpoint,run):
        require(record.get('actual_ema_fp32') is True and record.get('keypoint_shape')==[17,2]
            and record.get('physical_output_channels')==51 and record.get('visibility_supervised') is False,'v4模型输出声明不符')
    require(run.get('real_test_read') is False and all(numeric.digest(checkpoint.get(k)) and checkpoint[k]==run.get(k)
        for k in ('initial_state_sha256','exposure_chain_sha256')),'v4曝光链/初始化/最终测试声明错误')
    return dict(role='last_ema_v4',seed=seed,arm=arm,completed_updates=1000,bindings=expected['bindings'],
        initial_state_sha256=checkpoint['initial_state_sha256'],exposure_chain_sha256=checkpoint['exposure_chain_sha256'])


def load_model(path,expected_sha256,role,context,run_path=None,run_sha256=None):
    import torch
    path=trainer.g_research_path(path)
    require(numeric.digest(expected_sha256) and numeric.sha256(path)==expected_sha256,'v4实际检查点SHA不符')
    require(role in ('last_ema','pretrained_reference'),'v4模型角色无效')
    if role=='pretrained_reference':
        model,metadata=numeric.load_evaluation_model(path,expected_sha256,role,context)
        return prior.validate_model(model),metadata
    require(path.name=='last.pt' and run_path is not None,'v4只用last.pt和完整运行收据')
    checkpoint=torch.load(path,map_location='cpu',weights_only=False)
    run=numeric.checked_json(trainer.g_research_path(run_path),run_sha256)
    metadata=validate_checkpoint(checkpoint,run,context)
    model=prior.validate_model(checkpoint.get('ema'))
    metadata.update(path=str(path),sha256=expected_sha256,run_receipt_path=str(trainer.g_research_path(run_path)),run_receipt_sha256=run_sha256)
    return model,metadata


def evaluate(context,predictions,processed_ids):
    report,log=numeric.evaluate(context,predictions,processed_ids)
    report.update(schema=VERSION,numerical_evaluator_source_sha256=NUMERICAL_SOURCE_SHA256,
        v4_evaluation_source_files=source_bindings(),v4_normalization=trainer.NORMALIZATION)
    return report,log


def validate_prediction_receipt(receipt,context,prediction_path):
    require(receipt.get('schema')=='futsalmot_coco_pose_dev_predictions_v4' and receipt.get('binding')==context['binding']
        and receipt.get('prediction_sha256')==numeric.sha256(prediction_path)
        and receipt.get('numerical_evaluator_source_sha256')==NUMERICAL_SOURCE_SHA256
        and receipt.get('postprocess')==numeric.POSTPROCESS and receipt.get('score_policy')==numeric.SCORE_POLICY
        and receipt.get('physical_visibility')=='unknown_not_predicted' and receipt.get('test_read') is False
        and numeric.digest(receipt.get('checkpoint',{}).get('sha256')),'v4预测收据身份/后处理/来源错误')
    return receipt['processed_image_ids']
