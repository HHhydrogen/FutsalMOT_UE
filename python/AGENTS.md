# Python组件约定

Git、存储、研究封存和UE生命周期遵循项目根[AGENTS](../AGENTS.md)，本文件只补充组件规则。

## 阅读入口

- [Python README](README.md)
- [数据契约](../Docs/engineering/DATA_CONTRACT.md)
- [验证与限制](../Docs/engineering/VALIDATION_AND_LIMITATIONS.md)
- [目录与运行边界](../Docs/engineering/REPOSITORY_LAYOUT.md)

## 环境隔离

- P1固定Python3.9，虚拟环境位于本目录`.venv`。不要升级到3.10或安装研究Torch依赖。
- P2入口为`ue/run_task.py`，仅在真实UE5.8 Editor Python中执行；P1不能替代`import unreal`。
- UE可导入stdlib的`grf_ue_bridge.project_paths`，不能导入依赖NumPy、OpenEXR、OpenCV的P1后处理模块。
- P1与P2通过JSON/JSONL及渲染文件交换数据，不共享虚拟环境。
- 独立研究脚本已移到项目根`experiments/sim2real`，保持Python3.10环境。

## 配置与流程

从项目根使用`tools/run.ps1 p1 task ...`。本机默认配置为`Saved/P1/.futsalmot/local.json`，模板为`configs/local.example.json`；配置仍须逐次运行`task validate`，历史smoke配置不能自动视为当前有效。

推荐顺序：validate → resolve/export → ue-command →真实Editor异步MRQ →postprocess →audit →manifest。`ue-command`只生成命令；提交MRQ不等于完成。启用Runtime Pose的任务在MRQ终态后执行独立pose-finalize。

resolver显式接收独立repo时保留该repo的`.futsalmot`，不从祖先项目继承本机配置；真正项目代码根统一写`Saved/P1`。按manifest引用定位相机和clip，不推断固定祖先层数。

## 验证边界

默认pytest跳过真实GRF集成；显式`-m grf_integration`才执行原生引擎。只对本轮改动做必要针对检查，CPU通过不代表资产、MRQ、可见性或动态Pose已验收。

历史12点与新COCO17数据保持独立。unknown不改成visible，位置监督不冒称物理遮挡监督。新源码路径改变SHA，历史冻结实验需原版本追溯，不能用旧准入直接复跑新布局。
