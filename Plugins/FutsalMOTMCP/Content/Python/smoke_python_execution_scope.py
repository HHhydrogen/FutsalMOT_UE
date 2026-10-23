"""连续调用两次：验证 PRIVATE 文件隔离与显式纯 Python 会话保留。"""
import json
import sys
import types


def main():
    key = "futsalmot_mcp_scope_smoke_runtime"
    if "_futsal_scope_file_sentinel" in globals():
        raise RuntimeError("上次文件调用的全局变量仍存在，PRIVATE 隔离未生效")
    globals()["_futsal_scope_file_sentinel"] = "仅本次文件命名空间"
    holder = sys.modules.get(key)
    if holder is None:
        holder = types.ModuleType(key)
        holder.calls = 0
        sys.modules[key] = holder
    holder.calls += 1
    if holder.calls not in (1, 2):
        raise RuntimeError("超出两次 smoke；不得混入旧会话")
    result = {"call": holder.calls, "file_globals_isolated": True,
              "explicit_session_preserved": holder.calls == 2,
              "uobjects_created": False, "shutdown_fix_proven": False}
    if holder.calls == 2:
        del sys.modules[key]
        result["owned_session_released"] = True
    print("FUTSAL_MCP_SCOPE_SMOKE " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
