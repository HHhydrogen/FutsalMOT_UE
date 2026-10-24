# UE资产目录整理

2026-10-25通过真实Unreal MCP整理环境资产，默认地图仍为`/Game/FutsalMOT/Maps/L_FutsalCourt`，项目文件名保持不变。

| 原目录 | 当前资源目录 | 资产数 |
| --- | --- | --- |
| `/Game/FutsalMOT/Football` | `/Game/FutsalMOT/Environment/Football` | 3 |
| `/Game/FutsalMOT/Soccergoal` | `/Game/FutsalMOT/Environment/Goals` | 7 |
| `/Game/FutsalMOT/Staduim` | `/Game/FutsalMOT/Environment/Stadium` | 50 |

使用原生`AssetTools.move`，让Editor处理资产引用；没有从文件系统剪切或删除uasset。60项目标资产的稳定类型已核对，规范地图中23处环境网格组件已指向新目录，保存后dirty为空。原四个Sequence与TestFloor的既有WIP字节保持不变，未纳入整理提交。

## 保留的兼容边界

17个旧路径重定向器仍被外部Actor包引用，暂时保留。当前Python/MCP AssetTools没有反射出的完整FixupReferencers接口，不能为了删空目录而强删重定向器；旧路径只是兼容转向，资源实际在Environment目录。后续需要去掉这些别名时，使用UE内容浏览器或受控C++修引用流程，不在文件系统删除。

`Characters`、共享骨架/动画、`Tests/MPFB_Runtime`、地图、相机Sequence和号码开发资产保持原组织。共享生产资源不能因目录名含Tests而删除。本次不改变场景摆放、天气/地板参数或训练输入，没有重渲染数据集；资产结构验证不能替代未来功能或渲染验收。

源码入口位于`tools/ue_ops/`，实际检查和迁移收据保存在`Saved/ProjectStatus/stage3/`。这些是本机执行状态，不提交Git；未知partial必须读收据，不能直接重放迁移。
