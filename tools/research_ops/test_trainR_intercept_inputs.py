"""截距输入的必要CPU合同；夹具不加载实际权重、不前向、不访问研究输出。"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import trainR_intercept_inputs as inputs


def reference(path):
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def put(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    return reference(path)


def prediction(index, ordinal=1):
    return dict(uid='SNMOT-097:%06d:%06d' % (index+1, ordinal), bbox_xywh_px=[100.+index, 80., 50., 100.],
        score=.8, timestamp_sec=index/25., image_wh=[1920,1080], xy_px=[[110.+index,100.]]*17, geometry_valid=[True]*17)


def window(index=0, labels=(1,None)):
    return dict(window_uid=hashlib.sha256(('window'+str(index)).encode()).hexdigest(), domain='real',
        sequence='SNMOT-097', game='game6', fps=25, history=[prediction(i) for i in (1,2,3)],
        history_frame_indices=[1,2,3], candidate_frame_index=5, candidate_frame_number=6,
        candidates=[dict(prediction=prediction(5,i+1), label=label, label_reason='fixture') for i,label in enumerate(labels)])


@contextmanager
def fixture():
    with TemporaryDirectory() as directory, patch.object(inputs, 'R', Path(directory)):
        root=Path(directory); bundle=root/'code'/('a'*64)
        package=bundle/'python/src/grf_ue_bridge'; package.mkdir(parents=True)
        (package/'__init__.py').write_text('"""CPU夹具原特征包。"""\n',encoding='utf-8')
        actual=Path(__file__).resolve().parents[2]/'python/src/grf_ue_bridge'
        for filename in ('learned_association_features_v8.py','learned_association_model_v8.py'):
            (package/filename).write_bytes((actual/filename).read_bytes())
        loader=bundle/'tools/research_ops/v8_track.py';loader.parent.mkdir(parents=True)
        loader.write_text('# 仅绑定CPU夹具；测试不得执行此入口。\n',encoding='utf-8')
        relatives=['python/src/grf_ue_bridge/'+filename for filename in ('learned_association_features_v8.py','learned_association_model_v8.py')]
        manifest=put(root/'metadata/manifest.json',dict(files=[dict(path=name,sha256=reference(bundle/name)['sha256'])
            for name in relatives+['tools/research_ops/v8_track.py']]))
        norm=dict(schema='v8_train_R_only_normalizer',mean=[0.]*194,std=[1.]*194,count=12,feature_dim=194,
            pose_columns=list(range(24,194)),fit_scope='known_label_train_R_only',std_floor=.05,clip_abs=5.,
            guard_stage='before_any_training_or_evaluation')
        normref=put(root/'metadata/normalizer.json',norm)
        pool=root/'train/real_pool.jsonl';pool.parent.mkdir(parents=True)
        original=[window(i,(None,None) if i==1 else (1,None)) for i in range(1000)]
        pool.write_text(''.join(json.dumps(w,separators=(',',':'))+'\n' for w in original),encoding='utf-8')
        poolref=reference(pool)
        protocol=dict(bundle=str(bundle),bundle_manifest=manifest,folds=dict(game4=dict(normalizer=normref)))
        protoref=put(root/'metadata/protocol.json',protocol)
        binding=dict(protocol_sha256=protoref['sha256'],fold='game4',seed=20261024,arm='motion_R')
        run=root/'train/run';run.mkdir();(run/'last.pt').write_bytes(b'not-loaded')
        trainref=put(run/'run_receipt.json',dict(status='complete',completed_updates=1000,binding=binding,
            checkpoint_sha256=reference(run/'last.pt')['sha256']))
        spec=dict(model_id='fixture_R',regime='R',fold='game4',seed=20261024,architecture='original_strong_motion_v8',use_pose=False,
            checkpoint=reference(run/'last.pt'),training_receipt=trainref,run=str(run),binding=binding,normalizer=normref,clean_R_pool=poolref,
            loader=dict(module=reference(loader),function='load_complete',protocol=protoref,return_contract='model,normalizer,binding'),
            calibration=dict(augmentation=False,training_S_read=False,optimizer_SGD_updates=0,extra_clean_R_window_evaluations=1000))
        info=dict(clean_R_pool=poolref,normalizer=normref,allowed_games=['game6','game9'],
            allowed_sequences=['SNMOT-097','SNMOT-151'])
        inv=dict(schema='trainR_intercept_source_inventory_v1',input_Pose_used=False,feature_function='features',
            models=[spec],folds=dict(game4=info),feature_source=reference(bundle/relatives[0]),normalizer_source=reference(bundle/relatives[1]))
        inputs.clear_feature_cache()
        try: yield root,inv,spec,original,norm
        finally: inputs.clear_feature_cache()


class CleanInputs(unittest.TestCase):
    def test_original194_motion_mask_unknown_and1000_denominator(self):
        with fixture() as (_,inv,spec,original,norm):
            modules=set(sys.modules)
            result=inputs.prepare_clean_R_windows(inv,spec); windows=result['windows']; receipt=result['receipt']
            self.assertEqual(len(windows),1000);self.assertFalse(result['cache_hit'])
            self.assertEqual(receipt['counts'],dict(windows=1000,all_pair_count=2000,known_pair_count=999,
                unknown_pair_count=1001,positive_pair_count=999,negative_pair_count=0,empty_known_window_count=1))
            self.assertEqual(windows[1]['labels'],(None,None));self.assertEqual(windows[1]['known_mask'],(False,False))
            self.assertEqual(windows[0]['candidate_UIDs'],tuple(c['prediction']['uid'] for c in original[0]['candidates']))
            self.assertEqual(len(windows[0]['features'][0]),194)
            self.assertEqual(windows[0]['features'][0][24:],(0.,)*170)
            # 原features先减两个实际timestamp；不以等价实数式改变FP64运算顺序。
            self.assertEqual(windows[0]['features'][0][:4],((5/25.-3/25.)/1.2,.8,.8,1.))
            self.assertEqual(receipt['objective_denominator'],1000);self.assertFalse(receipt['normalizer_fitted'])
            self.assertEqual(receipt['actual_model_window_evaluations'],0)
            self.assertEqual(set(sys.modules)-modules,set())
            with self.assertRaises(TypeError):windows[0]['labels']=(0,0)

    def test_same_fold_seed_regime_reuses_inputs_no_pool_reopen(self):
        with fixture() as (_,inv,spec,_,_):
            first=inputs.prepare_clean_R_windows(inv,spec)
            second=deepcopy(spec);second['model_id']='fixture_other_seed';second['seed']=20261025;second['binding']['seed']=20261025
            inv['models'].append(second)
            actual_open=Path.open;pool=Path(spec['clean_R_pool']['path'])
            def guarded(path,*args,**kwargs):
                if path==pool:raise AssertionError('同一fold原池不能重复读取')
                return actual_open(path,*args,**kwargs)
            with patch.object(Path,'open',guarded):result=inputs.prepare_clean_R_windows(inv,second)
            self.assertTrue(result['cache_hit']);self.assertIs(first['windows'],result['windows'])
            self.assertEqual(result['receipt']['planned_extra_R_model_window_evaluations'],1000)

    def test_duplicate_UID_and_changed_pool_SHA_refused(self):
        with fixture() as (_,inv,spec,original,_):
            pool=Path(spec['clean_R_pool']['path']);original[1]['window_uid']=original[0]['window_uid']
            pool.write_text(''.join(json.dumps(w)+'\n' for w in original),encoding='utf-8')
            spec['clean_R_pool'].update(reference(pool));inv['folds']['game4']['clean_R_pool']=spec['clean_R_pool']
            with self.assertRaisesRegex(ValueError,'复制UID'):inputs.prepare_clean_R_windows(inv,spec)
            original[1]['window_uid']='e'*64;pool.write_text(''.join(json.dumps(w)+'\n' for w in original),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SHA/1000'):inputs.prepare_clean_R_windows(inv,spec)

    def test_heldout_future_label_and_UID_guards(self):
        info=dict(allowed_games=['game6','game9'],allowed_sequences=['SNMOT-097','SNMOT-151'])
        normalizer=SimpleNamespace(transform=lambda values,**kwargs:[*values[:24],*([0.]*170)])
        feature=lambda *_:[0.]*194
        for mutate in (lambda w:w.update(game='game4'),lambda w:w.update(candidate_frame_index=2),
                lambda w:w['candidates'][0].update(label=True),
                lambda w:w['candidates'][0]['prediction'].update(uid='SNMOT-097:000007:000001')):
            w=window();mutate(w)
            with self.assertRaises(ValueError):inputs._materialize(w,info,feature,normalizer)

    def test_import_scope_restores_old_modules_paths_on_failure(self):
        sentinel=ModuleType('grf_ue_bridge');old=sys.modules.get('grf_ue_bridge');paths=sys.path[:];bytecode=sys.dont_write_bytecode
        sys.modules['grf_ue_bridge']=sentinel
        try:
            with self.assertRaisesRegex(RuntimeError,'fixture'):
                with inputs.frozen_import_scope(Path('not_executed')):
                    self.assertNotIn('grf_ue_bridge',sys.modules)
                    sys.modules['grf_ue_bridge']=ModuleType('temporary')
                    sys.modules[inputs._MODULE_PREFIX+'fixture']=ModuleType('temporary')
                    raise RuntimeError('fixture')
            self.assertIs(sys.modules['grf_ue_bridge'],sentinel);self.assertEqual(sys.path,paths)
            self.assertEqual(sys.dont_write_bytecode,bytecode)
            self.assertNotIn(inputs._MODULE_PREFIX+'fixture',sys.modules)
        finally:
            if old is None:sys.modules.pop('grf_ue_bridge',None)
            else:sys.modules['grf_ue_bridge']=old

    def test_model_loader_original_contract_CPU_frozen_no_forward(self):
        with fixture() as (_,inv,spec,_,norm):
            events=[]
            class Model:
                def state_dict(self):return {'weight':SimpleNamespace(dtype='FP32')}
                def to(self,**kwargs):events.append(('to',kwargs));return self
                def eval(self):events.append('eval');return self
                def requires_grad_(self,flag):events.append(('requires_grad',flag));return self
                def __call__(self,*_):raise AssertionError('inputs不允许前向')
            model=Model();normalizer=SimpleNamespace(state=lambda:deepcopy(norm))
            def complete(run,protocol,protocol_sha,fold):
                events.append(('loader',str(run),protocol_sha,fold));return model,normalizer,deepcopy(spec['binding'])
            module=SimpleNamespace(load_complete=complete)
            with patch.object(inputs,'_module',return_value=module),patch.dict(sys.modules,{'torch':SimpleNamespace(float32='FP32')}):
                result=inputs.load_model(spec)
            self.assertIs(result['model'],model);self.assertEqual(result['receipt']['model_forward_calls'],0)
            self.assertIn(('to',{'device':'cpu'}),events);self.assertIn(('requires_grad',False),events)
            normalizer.state=lambda:dict(norm,count=999)
            with patch.object(inputs,'_module',return_value=module),patch.dict(sys.modules,{'torch':SimpleNamespace(float32='FP32')}):
                with self.assertRaisesRegex(ValueError,'normalizer'):inputs.load_model(spec)

    def test_RS_uses_original_complete_model_not_R_loader(self):
        with fixture() as (root,inv,spec,_,norm):
            old=deepcopy(spec)
            bundle=root/'code'/('b'*64);loader=bundle/'tools/research_ops/v10_runtime.py'
            loader.parent.mkdir(parents=True);loader.write_text('# 不实际执行的RS夹具\n',encoding='utf-8')
            manifest=put(root/'metadata/RS_manifest.json',dict(files=[dict(path='tools/research_ops/v10_runtime.py',sha256=reference(loader)['sha256'])]))
            protocol=put(root/'metadata/RS_protocol.json',dict(bundle=str(bundle),bundle_manifest=manifest,v8_protocol=old['loader']['protocol']))
            run=root/'train/RS_run';checkpoint=run/'checkpoints/step_1000.pt';checkpoint.parent.mkdir(parents=True);checkpoint.write_bytes(b'not-loaded')
            binding=dict(protocol_sha256=protocol['sha256'],fold='game4',seed=20261024,regime='RS',method='motion',pool='balanced')
            spec.update(model_id='fixture_RS',regime='RS',run=str(run),binding=binding,checkpoint=reference(checkpoint))
            spec['loader']=dict(module=reference(loader),function='complete_model',protocol=protocol,
                return_contract='cfg,numeric,model,adapter,binding')
            spec['training_receipt']=put(run/'run_receipt.json',dict(status='complete',completed_updates=1000,binding=binding,checkpoint=spec['checkpoint']))
            events=[]
            model=SimpleNamespace(state_dict=lambda:{'weight':SimpleNamespace(dtype='FP32')},
                to=lambda **kwargs:events.append(('to',kwargs)),eval=lambda:events.append('eval'),
                requires_grad_=lambda flag:events.append(('requires_grad',flag)))
            normalizer=SimpleNamespace(state=lambda:deepcopy(norm))
            def complete(config,actual_run):
                self.assertEqual(config,Path(protocol['path']));self.assertEqual(actual_run,run)
                return {},None,model,normalizer,deepcopy(binding)
            with patch.object(inputs,'_module',return_value=SimpleNamespace(complete_model=complete)),\
                    patch.dict(sys.modules,{'torch':SimpleNamespace(float32='FP32')}):
                loaded=inputs.load_model(spec)
            self.assertIs(loaded['normalizer'],normalizer);self.assertEqual(loaded['binding'],binding)
            # R与RS使用同原pool/normalizer/v8数值，缓存键不能包含模型权重或regime。
            inv['models']=[old,spec]
            first=inputs.prepare_clean_R_windows(inv,old);second=inputs.prepare_clean_R_windows(inv,spec)
            self.assertTrue(second['cache_hit']);self.assertIs(first['windows'],second['windows'])

    def test_test_paths_and_wrong_Pose_model_refused_without_read(self):
        with fixture() as (root,_,spec,_,_):
            with self.assertRaises(ValueError):inputs.safe(root/'test'/'forbidden.json')
            with self.assertRaises(ValueError):inputs.safe(root/'SNMOT-116'/'forbidden.json')
            spec['binding']['arm']='pose_R'
            with self.assertRaises(ValueError):inputs.load_model(spec)


if __name__=='__main__':unittest.main(verbosity=2)
