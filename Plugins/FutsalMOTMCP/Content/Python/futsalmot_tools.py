import os

import unreal
import toolset_registry


def _project_root() -> str:
    return os.path.normpath(unreal.Paths.project_dir())


def _resolve_file_within_project(path: str, root: str) -> str:
    raw = (path or "").strip()
    if not raw:
        raise ValueError("path must not be empty")
    resolved = os.path.normpath(
        raw if os.path.isabs(raw) else os.path.join(root, raw)
    )
    try:
        common = os.path.commonpath([root, resolved])
    except ValueError:
        common = ""
    if common != root:
        raise ValueError(f"path resolves outside the project root: {resolved}")
    if not os.path.isfile(resolved):
        raise ValueError(f"file does not exist: {resolved}")
    return resolved


def _log_text(log_output) -> str:
    if not log_output:
        return ""
    return "\n".join(entry.output for entry in log_output)


def _tail_python_log(max_lines: int = 40) -> str:
    try:
        log_dir = os.path.join(unreal.Paths.project_saved_dir(), "Logs")
        candidates = [
            os.path.join(log_dir, name)
            for name in os.listdir(log_dir)
            if name.endswith(".log")
        ]
        if not candidates:
            return ""
        log_path = max(candidates, key=os.path.getmtime)
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        python_lines = [
            ln
            for ln in lines
            if "LogPython" in ln or "LogPythonScriptPlugin" in ln
        ]
        return "\n".join(python_lines[-max_lines:])
    except Exception:
        return ""


def _execute_python(command: str, mode, path: str) -> dict[str, str]:
    result = unreal.PythonScriptLibrary.execute_python_command_ex(
        command, mode, unreal.PythonFileExecutionScope.PUBLIC
    )
    if result is None:
        return {
            "success": "false",
            "path": path,
            "result": "execution failed (see UE Output Log, category LogPython)",
            "log": _tail_python_log(),
        }
    command_result, log_output = result
    return {
        "success": "true",
        "path": path,
        "result": command_result or "",
        "log": _log_text(log_output),
    }


@unreal.uclass()
class FutsalMOTTools(unreal.ToolsetDefinition):
    """Run real Unreal Python scripts and code from OpenCode via the MCP toolset registry.

    Execution happens in the full Unreal Python environment (not the sandboxed
    ProgrammaticToolset), so scripts can `import unreal` and use the editor API.
    """

    @toolset_registry.tool_call
    @staticmethod
    def run_python_file(path: str) -> dict[str, str]:
        """Execute a real Unreal Python script file (execute-file mode).

        Args:
            path: Absolute path, or a path relative to the project root. The
                resolved file must stay inside the project root directory.

        Returns:
            A dict with keys: success, path, result, log. `success` is the
            string "true" or "false".
        """
        root = _project_root()
        resolved = _resolve_file_within_project(path, root)
        return _execute_python(
            resolved, unreal.PythonCommandExecutionMode.EXECUTE_FILE, resolved
        )

    @toolset_registry.tool_call
    @staticmethod
    def run_python_code(code: str) -> dict[str, str]:
        """Execute Python code in the real Unreal Python environment.

        Intended for diagnostics. Runs the code in execute-file mode, so both
        single statements and multi-line blocks are supported.

        Args:
            code: Python code to execute.

        Returns:
            A dict with keys: success, path, result, log. `success` is the
            string "true" or "false".
        """
        if not (code or "").strip():
            raise ValueError("code must not be empty")
        return _execute_python(
            code, unreal.PythonCommandExecutionMode.EXECUTE_FILE, ""
        )