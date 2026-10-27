"""有界变化模型的独立追踪输入适配；只改变帧域守卫与一个输入调用。"""
import ast
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import sys
import types


TRACKER_SHA = '7f7196d9ac812b17ea94a909aaa057910ebecdfd10ee769a9ebe8b7f92759688'
FIELDS = ('uid', 'bbox_xywh_px', 'score', 'xy_px', 'geometry_valid', 'timestamp_sec', 'image_wh')
OLD_INPUT = 'self.normalizer.transform(features(list(track.history), detection.record), use_pose=self.use_pose)'
NEW_INPUT = '_bounded_velocity_input(self.normalizer, list(track.history), detection.record, self.use_pose)'
NEW_SCOPE = 'if not _v10_validate_frame(frame, _v10_sources):\n    raise ValueError("v10未登记实际帧")'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _dump(tree):
    return ast.dump(tree, include_attributes=False)


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _public(record):
    """显式白名单，GT/身份标签/评价字段从不交给输入adapter。"""
    return {key: deepcopy(record[key]) for key in FIELDS}


def velocity_input(adapter, history, candidate, use_pose=True):
    """关闭Pose仅把原末gate设0，回到本模型自己的motion分支。"""
    require(type(use_pose) is bool, 'Pose开关必须明确bool')
    values = list(adapter.transform_pair([_public(r) for r in history], _public(candidate)))
    require(len(values) == 195 and all(not isinstance(x, bool) and isinstance(x, (float, int))
                and math.isfinite(x) for x in values), '有界变化追踪输入必须195维有限数值')
    if not use_pose:
        values[-1] = 0.
    return values


class _ReplaceInput(ast.NodeTransformer):
    def __init__(self, old, new):
        self.old, self.new, self.count = _dump(old), new, 0

    def visit_Call(self, node):
        if _dump(node) == self.old:
            self.count += 1
            return ast.copy_location(deepcopy(self.new), node)
        return self.generic_visit(node)


def _scope_guard(tree):
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'update_frame']
    require(len(functions) == 1, '必须唯一原update_frame函数')
    function = functions[0]
    guards = [n for n in function.body if isinstance(n, ast.If) and any(
        isinstance(k, ast.Name) and k.id == 'SCOPE' for k in ast.walk(n.test))]
    require(len(guards) == 1, '必须唯一原帧域SCOPE守卫')
    return function, function.body.index(guards[0])


def adapt_tracker_tree(source_text):
    """不执行tracker：替换两个明确节点后反向恢复，验证整棵原AST。"""
    original = ast.parse(source_text)
    tree = deepcopy(original)
    function, index = _scope_guard(tree)
    old_guard = deepcopy(function.body[index])
    replacement_guard = ast.parse(NEW_SCOPE).body[0]
    function.body[index] = deepcopy(replacement_guard)
    old_call = ast.parse(OLD_INPUT, mode='eval').body
    new_call = ast.parse(NEW_INPUT, mode='eval').body
    # 不接受另一个self.normalizer.transform绕过这个唯一原输入表达式。
    normalizer_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == 'transform'
        and _dump(n.func.value) == _dump(ast.parse('self.normalizer', mode='eval').body)]
    require(len(normalizer_calls) == 1 and _dump(normalizer_calls[0]) == _dump(old_call),
            '原normalizer输入调用不是唯一已验结构')
    changed = _ReplaceInput(old_call, new_call)
    tree = changed.visit(tree)
    require(changed.count == 1, '只允许替换一个实际输入调用')
    restored = deepcopy(tree)
    restored_function = next(n for n in ast.walk(restored)
        if isinstance(n, ast.FunctionDef) and n.name == 'update_frame')
    require(_dump(restored_function.body[index]) == _dump(replacement_guard), '新scope位置变化')
    restored_function.body[index] = old_guard
    reverse = _ReplaceInput(new_call, old_call)
    restored = reverse.visit(restored)
    require(reverse.count == 1 and _dump(restored) == _dump(original),
            '除帧域守卫与唯一输入调用外，追踪AST改变')
    ast.fix_missing_locations(tree)
    audit = dict(schema='bounded_velocity_tracker_two_node_AST_audit_v1',
        modified_AST_nodes='one_frame_scope_guard_and_one_adapter_input_call_only',
        original_guard_AST_sha256=_digest(_dump(old_guard)),
        original_input_AST_sha256=_digest(_dump(old_call)),
        replacement_input_AST_sha256=_digest(_dump(new_call)),
        original_AST_sha256=_digest(_dump(original)), runtime_AST_sha256=_digest(_dump(tree)),
        reverse_restored_AST_sha256=_digest(_dump(restored)),
        tracker_numeric_AST_unchanged_outside_scope_and_input=True,
        sequence_or_game_alias_used=False, candidate_threshold_cost_assignment_history_unchanged=True,
        GT_used_by_input=False, inference_shape_shuffle=False,
        pose_off='same195_input_only_final_quality_gate_zero_own_motion_base')
    return tree, audit


def scoped_velocity_tracker(old_bundle, sources, source_runtime):
    """从实际旧bundle读原tracker，不复制旧runtime，不改ROOT或加载模型。"""
    path = Path(old_bundle) / 'python/src/grf_ue_bridge/learned_association_tracker_v8.py'
    require(source_runtime.TRACKER_SHA == TRACKER_SHA, '来源runtime的原tracker合同不同')
    payload = path.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == TRACKER_SHA, '原冻结tracker字节改变')
    tree, audit = adapt_tracker_tree(payload.decode('utf-8'))
    name = 'grf_ue_bridge.pose_velocity_explicit_scope'
    module = types.ModuleType(name)
    module.__package__ = 'grf_ue_bridge'
    module.__file__ = str(path)
    module._v10_validate_frame = source_runtime.validate_frame
    module._v10_sources = deepcopy(sources)
    module._bounded_velocity_input = velocity_input
    sys.modules[name] = module
    exec(compile(tree, str(path), 'exec'), module.__dict__)
    audit['original_tracker_sha256'] = TRACKER_SHA
    return module.tracker_class(), audit
