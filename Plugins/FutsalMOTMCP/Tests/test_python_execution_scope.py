"""纯 Python 合同测试；模拟 UE 执行分支，不冒充真实 Editor 验收。"""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


PYTHON_ROOT = Path(__file__).resolve().parents[1] / "Content/Python"


class FakeEngine:
    def __init__(self):
        self.console = {"__name__": "__main__"}
        self.calls = []
        self.logs_scanned = False

    def execute(self, command, mode, scope):
        self.calls.append((command, mode, scope))
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                if mode == "file":
                    namespace = {"__name__": "__main__"} if scope == "private" else self.console
                    namespace["__file__"] = command
                    exec(compile(Path(command).read_text(encoding="utf-8"), command, "exec"), namespace)
                else:
                    # 与本机 UE RunString 相同：枚举不改变控制台 globals。
                    exec(compile(command, "<string>", "single"), self.console)
            return "None", [types.SimpleNamespace(output=output.getvalue())]
        except Exception:
            return None


def make_module(engine):
    unreal = types.ModuleType("unreal")
    unreal.PythonCommandExecutionMode = types.SimpleNamespace(EXECUTE_FILE="file", EXECUTE_STATEMENT="statement")
    unreal.PythonFileExecutionScope = types.SimpleNamespace(PUBLIC="public", PRIVATE="private")
    unreal.PythonScriptLibrary = types.SimpleNamespace(execute_python_command_ex=engine.execute)
    unreal.ToolsetDefinition = object
    unreal.uclass = lambda: lambda cls: cls
    registry = types.ModuleType("toolset_registry")

    def tool_call(func):
        original = func.__func__
        def wrapped(*args, **kwargs):
            return original(*args, **kwargs)
        return staticmethod(wrapped)

    registry.tool_call = tool_call
    module = types.ModuleType("futsalmot_tools")
    module.__file__ = str(PYTHON_ROOT / "futsalmot_tools.py")
    with patch.dict(sys.modules, {"unreal": unreal, "toolset_registry": registry}):
        exec(compile(Path(module.__file__).read_text(encoding="utf-8"), module.__file__, "exec"), module.__dict__)
    return module


class ScopeContractTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine()
        self.module = make_module(self.engine)

    def test_literal_isolation_and_multiline(self):
        result = self.module.FutsalMOTTools.run_python_code("actor = object()\nprint('ok')")
        self.assertEqual(result["success"], "true")
        self.assertNotIn("actor", self.engine.console)
        self.assertIn("ok", result["log"])
        self.assertEqual(self.engine.calls[-1][1:], ("statement", "private"))

    def test_literal_py_space_cannot_be_misparsed_as_file(self):
        result = self.module.FutsalMOTTools.run_python_code("print('asset.py argument')")
        self.assertEqual(result["success"], "true")
        self.assertEqual(self.engine.calls[-1][1], "statement")

    def test_file_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope.py"
            path.write_text("temporary_actor = object()\nprint(__name__)", encoding="utf-8")
            result = self.module._execute_python(str(path), "file", str(path))
        self.assertEqual(result["success"], "true")
        self.assertNotIn("temporary_actor", self.engine.console)
        self.assertEqual(self.engine.calls[-1][2], "private")

    def test_explicit_session_cross_literal_calls(self):
        key = "futsalmot_mcp_test_session"
        try:
            self.module.FutsalMOTTools.run_python_code(
                "import sys, types\nsys.modules['" + key + "']=types.SimpleNamespace(value=7)")
            result = self.module.FutsalMOTTools.run_python_code(
                "import sys\nprint(sys.modules['" + key + "'].value)")
            self.assertEqual(result["success"], "true")
            self.assertIn("7", result["log"])
            self.assertNotIn("sys", self.engine.console)
        finally:
            sys.modules.pop(key, None)

    def test_failure_does_not_read_old_logs(self):
        with patch("os.listdir", side_effect=AssertionError("禁止扫描历史日志")):
            result = self.module.FutsalMOTTools.run_python_code("raise RuntimeError('current error')")
        self.assertEqual(result["success"], "false")
        self.assertIn("当前 Editor", result["log"])

    def test_hotpatch_keeps_class_and_changes_registered_dispatch(self):
        namespace = {"__name__": "scope_patch_test"}
        source = PYTHON_ROOT / "patch_python_execution_scope.py"
        exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), namespace)
        original_class = self.module.FutsalMOTTools
        original_execute = self.module._execute_python
        with patch.dict(sys.modules, {"futsalmot_tools": self.module}):
            namespace["patch"]()
            self.assertIs(self.module.FutsalMOTTools, original_class)
            self.assertIsNot(self.module._execute_python, original_execute)
            result = original_class.run_python_code("print('dispatch')")
            self.assertEqual(result["success"], "true")
            namespace["patch"]("rollback")
            self.assertIs(self.module._execute_python, original_execute)

    def test_two_file_smoke_preserves_and_releases_plain_session(self):
        path = str(PYTHON_ROOT / "smoke_python_execution_scope.py")
        key = "futsalmot_mcp_scope_smoke_runtime"
        try:
            first = self.module._execute_python(path, "file", path)
            second = self.module._execute_python(path, "file", path)
            self.assertEqual(first["success"], "true")
            self.assertEqual(second["success"], "true")
            self.assertIn('"explicit_session_preserved": true', second["log"])
            self.assertNotIn(key, sys.modules)
        finally:
            sys.modules.pop(key, None)


if __name__ == "__main__":
    unittest.main()
