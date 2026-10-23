# Python 执行作用域与退出风险

本补丁减少 MCP 调用把临时 UObject 包装对象留在共享控制台 globals 的机会。它没有证明、也不宣称已修复退出时 Python finalize 的访问违规；已有 CPU skin/Lumen RHI 崩溃及 PIE 延迟回调生命周期问题应分别处理。

2026-10-23主agent已在真实Editor26244热替换执行函数：两次文件smoke通过，显式session第二次保留并释放；两次字面代码检查结果False（临时全局未泄漏）。1042已prepare队列在前后对象ID同为2754078042512，此后真实MRQ成功完成，未重新prepare或重启Editor。退出期AV仍待正常批次结束后观察，不能将这些运行证据写成退出根治。

## 本机 UE5.8 源码依据

- `Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Public/PythonScriptTypes.h:48` 定义 PRIVATE 为独立文件 globals/locals。
- 同模块 `Private/PythonScriptPlugin.cpp:1932` 的 `RunFile` 在 PRIVATE 时复制 `PyDefaultGlobalDict`，PUBLIC 使用 `PyConsoleGlobalDict`。
- `:1831` 的 `RunString` 不读取作用域枚举；`:1807` 的默认 `EvalString` 始终使用控制台字典。因此，字面诊断代码通过单表达式 `exec(compile(...), 独立dict)` 隔离，外层使用 EXECUTE_STATEMENT，避免 ExecuteFile 将代码里的 `.py ` 误判为文件。
- `:1245` 起控制台字典是实际 `__main__` 字典的副本。PUBLIC 的 globals 不应直接称为 `sys.modules['__main__'].__dict__`。
- `:1495` 起先执行 Python shutdown delegate，后释放控制台字典，再调用 `Py_Finalize`。这是引用生命周期的调查线索，不能据此定位损坏对象。
- `Engine/Binaries/ThirdParty/Python3/Win64/Lib/runpy.py:91,262` 显示 `run_path(..., run_name='__main__')` 使用临时模块，结束时恢复原 `sys.modules` 项。忽略其返回值的 helper 并不会自动把所有子脚本 globals 写入控制台；回调、闭包或显式模块会延长其生命周期。
- `Engine/Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/tool_call_impl.py:190` 的包装函数调用原 Python 方法。该方法动态查找模块 `_execute_python`，可只替换此普通函数，无需重新声明 UClass。

PRIVATE 不是新解释器或安全沙箱。`sys.modules`、导入模块及环境变量仍共享；现有 `futsalmot_pose17_smoke_runtime` 显式会话继续跨调用保留 queue/settings/executor/callback，仍须原有 release 清理。改变作用域不会自动清除之前 PUBLIC 调用遗留的引用，不能清空用户控制台或全部 `sys.modules`。

## 无重启验证顺序

由主 Agent 确认当前 Level、无 PIE/MRQ、无未知 dirty。已 prepare 尚未 submit 的自有 runner 会话可以保留，用其补丁前后相同引用作为跨调用证据；补丁不清理或重新准备该会话。不要为了测试强杀 Editor。

1. 首次安装通过原工具执行一个小表达式，显式调用 `unreal.PythonScriptLibrary.execute_python_command_ex(补丁文件绝对路径, EXECUTE_FILE, PRIVATE)`。补丁文件为 `Content/Python/patch_python_execution_scope.py`；不要 `importlib.reload(futsalmot_tools)`，也不要重新执行完整 Toolset 文件。读取该调用的原生结果及当前 LogPython。
2. 使用原有已注册 `run_python_file` 连续两次执行 `Content/Python/smoke_python_execution_scope.py`。第一次报告 call=1；第二次必须报告隔离成功、显式纯 Python session 保留并释放。两次均不创建 UObject，也不渲染。
3. 原有 `run_python_code` 执行 `ephemeral_actor = object(); print('scope-a')`，下一次执行 `print('ephemeral_actor' in globals())`，结果应为 False。若需 session 另测，只使用自有纯 Python `sys.modules` 项并删除它。
4. 一个已有 runner 的只读 preflight 可检查兼容性；不必为作用域合同重复 MRQ。此后只在正常工作所需的安全退出时记录是否仍出现 finalize AV，不将一次正常退出视为根因已证。

热替换 helper 只提取 `_execute_python` AST，保存原函数供回退，不执行 UClass 定义。若需回退，在 PRIVATE 文件调用中加载 helper 的函数并执行 `patch('rollback')`；或设置自有 `FUTSAL_MCP_SCOPE_PATCH_ACTION=rollback` 后执行 helper，并恢复该环境变量。补丁不改已有队列或 runner 会话。

## 失败日志

`execute_python_command_ex` 成功时返回本次捕获日志；失败返回 None 时仅提示读取当前 Editor LogPython/启动 abslog。旧实现按 `Saved/Logs` 最近 mtime 回退，在自定义 abslog 位于其他路径时可能错误呈现历史日志；本补丁移除此回退，没有猜测日志路径。

## CPU 合同测试

从项目根执行：

```powershell
E:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe -B -m unittest discover -s Plugins/FutsalMOTMCP/Tests -p test_python_execution_scope.py -v
```

本次 7 项通过，包括文件/字面隔离、跨调用显式会话、失败不扫描旧日志、替换后原注册闭包调用及回退、两次文件 smoke。测试使用模拟 UE 执行器，真实 Editor smoke 和退出观察由主 Agent 另行执行，未在 CPU 测试中冒充通过。
