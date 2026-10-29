"""统一每场清单的绿色地板事务；与既有天气/外观共享结束回调。"""
import json
from pathlib import Path


class FloorSession:
    def __init__(self, recipe, report_path):
        self.recipe = recipe
        self.path = Path(report_path)
        self.restore_result = None
        self.render_deferred = False
        self.callback_ownership_transferred = False
        self.report = {'schema':'futsalmot_floor_application_v1','state':'not_started',
                       'recipe':recipe,'errors':[]}

    def _floor(self):
        import unreal
        assert unreal.EditorLevelLibrary.get_editor_world().get_path_name().split('.')[0] == '/Game/FutsalMOT/Maps/L_FutsalCourt'
        actors = [a for a in unreal.EditorLevelLibrary.get_all_level_actors()
                  if a.get_actor_label() == 'SM_FutsalCourt_Floor']
        if len(actors) != 1:
            raise RuntimeError('绿色地板Actor必须唯一')
        component = actors[0].get_component_by_class(unreal.StaticMeshComponent)
        if component is None or component.get_num_materials() != 1:
            raise RuntimeError('绿色地板组件/材质槽不符')
        return component

    def preflight(self):
        import unreal
        from grf_ue_bridge.grass_detail import grass_recipe
        if unreal.EditorLevelLibrary.get_pie_worlds(False) or unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem).is_rendering():
            raise RuntimeError('活动PIE/MRQ时不准备地板事务')
        dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        if dirty:
            raise RuntimeError('地板准备前有未保存改动')
        expected = grass_recipe(self.recipe['seed'],floor_id=self.recipe['variant']['id'])
        expected['selection_mode'] = self.recipe['selection_mode']
        if expected != self.recipe:
            raise ValueError('地板recipe与已确认目录不符')
        target = unreal.load_asset(self.recipe['material'])
        if target is None or target.get_class().get_name() != 'MaterialInstanceConstant':
            raise RuntimeError('绿色材质不存在或class不符')
        lib = unreal.MaterialEditingLibrary
        for key,value in self.recipe['scalar_parameters'].items():
            if abs(float(lib.get_material_instance_scalar_parameter_value(target,key))-value)>1e-6:
                raise RuntimeError('绿色材质实际参数不同: '+key)
        gain = lib.get_material_instance_vector_parameter_value(target,'GreenAlbedoGain')
        if any(abs(a-b)>1e-6 for a,b in zip(self.recipe['variant']['albedo_gain_linear'],[gain.r,gain.g,gain.b])):
            raise RuntimeError('绿色材质实际深浅不同')
        original = self._floor().get_material(0).get_path_name()
        if self.path.exists():
            raise RuntimeError('已有地板事务收据，使用新attempt')
        self.report.update(original_material=original,expected_current=original)

    def _write(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(self.path)

    def apply(self):
        import unreal
        component = self._floor()
        if component.get_material(0).get_path_name() != self.report['expected_current']:
            raise RuntimeError('地板槽在preflight后发生改变')
        target = unreal.load_asset(self.recipe['material'])
        self.report['state'] = 'apply_intent'
        self._write()
        try:
            component.set_material(0,target)
            self.report['expected_current'] = target.get_path_name()
            if component.get_material(0) != target:
                raise RuntimeError('地板应用读回不符')
            self.report['state'] = 'applied'
            self._write()
        except BaseException:
            self.restore('apply_failed')
            raise
        return self

    def mark_rendering(self):
        self.report['state'] = 'rendering'
        self._write()

    def record_downstream_failure(self, exc):
        self.report['errors'].append(type(exc).__name__+': '+str(exc))
        self._write()

    def restore(self, reason, render_result=None):
        if self.restore_result is not None:
            return self.restore_result
        import unreal
        errors = []
        try:
            component = self._floor()
            if component.get_material(0).get_path_name() != self.report['expected_current']:
                raise RuntimeError('地板槽被其他操作改变，保留现场')
            original = unreal.load_asset(self.report['original_material'])
            if original is None:
                raise RuntimeError('原地板材质缺失')
            component.set_material(0,original)
            if component.get_material(0) != original:
                raise RuntimeError('地板恢复读回不符')
            self.report['expected_current'] = original.get_path_name()
        except Exception as exc:
            errors.append(str(exc))
        self.restore_result = {'ok':not errors,'state':'restore_failed' if errors else 'restored','errors':errors}
        self.report.update(state=self.restore_result['state'],restore_reason=reason,restore_errors=errors)
        self._write()
        return self.restore_result

    def _record_incomplete_render_result(self, result):
        return self.restore('failed',result)
