# UE无参数启动误报模块缺失

2026-10-25的手动启动进程命令行没有项目参数。当前引擎先记录`Running engine without a game`，随后从本机`AutoLoadProject.txt`恢复本项目，最终提示`Incompatible or missing module: FutsalMOT`。

项目DLL和引擎模块清单的BuildId均为`55116800`。不改DLL、不编译，显式传入`.uproject`后，同一DLL正常加载，真实MCP进入规范地图，`FutsalPlayerBase`和`FutsalPose17Library`均可用。

本机UE5.8源码中，`LaunchEngineLoop.cpp`在最近项目恢复之前初始化`ProjectBinariesRootDirectory`；无项目参数时该变量未获得项目根，后续模块搜索因而使用了错误位置。这与本次日志及显式路径对照一致。

## 本机处理与验证

- 关闭本机UE5.8自动恢复最近项目，仅移除指向本项目的`AutoLoadProject.txt`设置；不清空最近项目列表。
- 通过显式项目路径启动，真实模块/地图/MCP/clean/PIE/MRQ门禁通过。
- 正常退出后，再进行无项目参数启动复验：没有恢复最近项目或缺失模块提示，通过引擎`QUIT_EDITOR`正常退出，exit0。
- 未重新编译、修改引擎、改资产或禁用项目模块；DLL SHA保持`e5d8cea6fd77a388442a052d7c1b27e2e73716928064c0d315b77efb4bb5b6ab`。

证据在`Saved/EditorStartup/module_path_repair_20261025_a01/`。历史Python配置探针因HomeScreenSettings属性未暴露而失败，已收纳同目录；不把失败探针当成功修复。

## 后续打开项目

直接打开根目录`.uproject`，或使用明确项目路径的入口：

```powershell
./tools/open_editor.ps1 -Visible
./tools/open_editor.ps1 -ValidateOnly
```

启动器检查引擎/项目BuildId、模块文件、已有Editor、研究进程与提交内存余量，日志写本项目`Saved/EditorStartup/`。不自动重编译或忽略错误。若重新启用当前引擎的最近项目自动恢复，仍可能进入原故障路径；本次是本机启动规避修复，没有声称引擎代码缺陷已修复。
