# Git 单仓库融合（2026-10-25）

用户已明确授权开始融合。本次将Python已提交内容直接纳入UE主仓库；代码仍位于 `Content/FutsalMOT/code/`，环境隔离及正在运行的实验源码保持不变。

## 历史与备份

- UE父提交：`383a27ebe04396e422cb31f1c0e79b151741b023`，原69个提交。
- Python父提交：`861d83082b65a2e7a3f26b60c41ce715b8793037`，原148个提交。
- 使用标准 `git merge -s ours --no-commit --no-ff --allow-unrelated-histories` 建立双父关系，再仅在索引中将gitlink替换为Python原提交树，最后标准commit；不squash、重写旧提交或跳过hooks。
- 文档修改前，导入子树OID与Python原树均为 `4d58bc1172ea229f89b560d47e5659258cc90cfb`，完整452文件及mode一致。融合提交另外更新根/代码README和AGENTS，说明新的工作方式。
- 融合前在 `D:/projects/FutsalMOT_GitBackup_20261025_0430` 创建并验证了两仓bundle、索引、配置、patch及311份WIP，原内层 `.git` 也先移至该处。用户随后说明已主动删除该外部备份，并明确授权删除额外补建副本；两份现均不保留，不自动重建。融合历史已正常推送，当前WIP仍原位存在。

未提交的研究开发、UE资产和号码代码继续留在原工作区。融合只导入Python旧HEAD及明确的说明文件，不把WIP当作已验功能提交；虚拟环境、数据联接和忽略文件原位保留。原 `FutsalMOT_Dataset` GitHub仓库保留历史用途，本次不删除或归档它。

## 后续工作

唯一仓库根是UE项目根，远端仍为 `HHhydrogen/FutsalMOT_UE`、分支 `master`。在Python目录执行Git也会定位同一仓库，无需两次提交、子模块更新或 `--recurse-submodules`。使用命令行Git精确选择文件；新机器正常clone主仓库即可。

旧Python提交本身仍使用原根路径；查看原版本时可以按原提交及原路径查询。不能承诺普通 `git log --follow` 会自动跨过这次前缀迁移。

旧仓库已有副本更新到融合提交时，先保存原内层未提交内容和 `.git`，再处理旧子模块检出目录；不要在仍有未备份工作时强制覆盖。新clone不受此历史检出目录影响。

本记录说明融合边界，不表示Saved/Research迁回D盘已经完成，也不表示v4全部结果已出。实验和存储收尾按当前任务状态继续。
