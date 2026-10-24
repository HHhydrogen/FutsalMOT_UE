# 根目录文件的用途

根目录保留工具识别入口和项目入口文档，其余过期生成文件收纳到本机Saved。

| 文件 | 用途与位置 |
| --- | --- |
| `FustalMOT_UEDataset.uproject` | UE项目描述，绑定引擎、模块和插件；与Source/Content同级，保留根目录，名称不变。 |
| `.gitignore` | Git忽略生成物、Saved、缓存等；保留根目录以覆盖整个项目。 |
| `.mcp.json` | 项目Unreal MCP连接描述，地址为本机8000端口；保留约定的项目配置位置。 |
| `.vsconfig` | Visual Studio组件安装清单，包括MSVC、Windows SDK和UE工具；保留根目录供IDE和UE工程生成器识别。 |
| `AGENTS.md` | 全项目Agent工程规则；保留根目录。 |
| `README.md` | 项目及GitHub首页入口；保留根目录。 |
| `TASK_STATUS_AND_NEXT_STEPS.md` | 当前进度与下一步，现有工作流从根目录读取；保留根目录。 |

## 已收纳

- 原`opencode.json`移至`Config/LegacyTools/opencode.json`，保留原字节作为旧OpenCode项目配置；不再从项目根自动加载。Codex本机配置及Blender运行依赖不在本次调整范围，没有删除。
- `FustalMOT_UEDataset.sln`和`.slnx`是UE生成的主工程索引，两者是不同格式，不是两套项目源码。
- `Automation_FustalMOT_UEDataset.sln`和`.slnx`是UE生成的AutomationTool/C#工具工程索引，不是本聊天的定时任务配置。
- 上述四份IDE索引移至`Saved/IDE/`，原字节保留，不再纳入Git。主索引指向的`Intermediate/ProjectFiles`在本次整理前已经不存在，不能把这些旧文件视为当前可用的C++工程。

使用Visual Studio工程文件工作时，应先为`.uproject`重新生成工程文件，再打开新生成的主解决方案；不要直接打开Saved中的旧索引。UE重新生成时仍可能在根目录产生`.sln/.slnx`，这是正常的可再生文件；两种格式均已被Git忽略。

本次不移动UE资产、不运行Editor或编译，不改变模块/插件/默认地图。收纳收据位于`Saved/ProjectStatus/root_files_20261025/receipt.json`。
