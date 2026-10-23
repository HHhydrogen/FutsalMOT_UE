"""仅替换普通执行函数，不重新声明或注册 Unreal Toolset 类。"""
import ast
import json
import os
import sys
from pathlib import Path


def patch(action="apply"):
    """由主 Agent 在无 PIE/MRQ 的安全状态通过 PRIVATE 文件调用。"""
    module = sys.modules.get("futsalmot_tools")
    if module is None:
        raise RuntimeError("Toolset 尚未导入；禁止在补丁中创建或重载 UClass")
    backup_name = "_execute_python_before_scope_patch"
    if action == "rollback":
        original = getattr(module, backup_name, None)
        if original is None:
            raise RuntimeError("本会话不存在执行函数备份")
        module._execute_python = original
        return {"action": action, "uclass_reloaded": False}
    if action != "apply":
        raise ValueError("action 仅允许 apply 或 rollback")
    source = Path(module.__file__).resolve()
    tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "_execute_python"]
    if len(functions) != 1:
        raise RuntimeError("执行函数定义必须唯一")
    isolated = ast.Module(body=functions, type_ignores=[])
    replacements = {}
    exec(compile(isolated, str(source), "exec"), module.__dict__, replacements)
    replacement = replacements["_execute_python"]
    if not hasattr(module, backup_name):
        setattr(module, backup_name, module._execute_python)
    module._execute_python = replacement
    return {"action": action, "source": str(source), "uclass_reloaded": False,
            "scope": "private_file_and_isolated_literal_globals",
            "shutdown_crash_fix_proven": False}


if __name__ == "__main__":
    print("FUTSAL_MCP_SCOPE_PATCH " + json.dumps(
        patch(os.environ.get("FUTSAL_MCP_SCOPE_PATCH_ACTION", "apply")),
        ensure_ascii=False))
