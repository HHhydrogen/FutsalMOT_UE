# 数据存储与EXR生命周期

## 唯一落点

| 内容 | 物理目录 | 规则 |
| --- | --- | --- |
| 原始MRQ RGB/EXR | `G:/FutsalMOT_Dataset/_work/<attempt>/raw` | 新attempt，不覆盖失败或成品 |
| mask/Pose及待发布RGB | `G:/FutsalMOT_Dataset/_staging/<attempt>` | 成功后同卷移到版本目录，避免大文件复制 |
| 正式数据 | `G:/FutsalMOT_Dataset/<version>/groups/...` | 发布索引为入口，保留旧版本不覆盖 |
| UE配置、日志、轨迹、native、校准和运行收据 | UE项目`Saved/` | 物理D盘；不存大批渲染媒体，不提交Git |
| 研究输入、模型、运行日志和结果 | `D:/projects/FutsalMOT_Research/pose/<experiment>/...` | 按协议与attempt分目录，不覆盖旧实验 |
| 研究执行源码 | `D:/projects/FutsalMOT_Research/code/<manifest_SHA>/` | 从统一Git源码按清单安装，一份复用，不建第二个Git |

MRQ实际写入使用`grf_ue_bridge.storage_policy.require_render_destination`检查物理G边界、联接和80GiB最低余量；统一渲染及11个历史直接MRQ入口均接入。默认P1媒体根已改为G的`_work`，旧task内部机位`render/`布局兼容保留。开始批次前另用`tools/storage/dataset_storage_policy.py preflight`估算EXR峰值、RGB/mask和stage空间，G在预算外保留80GiB，D研究预算外保留40GiB；每新相机再检查余量。不能通过链接把数据写回D，也不能把旧产物挪入临时区绕过清理边界。

`tools/run.ps1 research`的源码入口只开放`--help`；正式执行使用已安装的DResearch代码bundle，具体训练器再验证清单SHA和独立准入。旧冻结实验仅保存历史，不自动获得新路径的运行授权。

## EXR及时清理

后处理成功必须生成真实成功收据，列出实际完整RGB/mask数量、Pose/world索引SHA、成功解码帧数和raw路径。消费登记区分EXR消费与RGB/位置训练：后者不需要等训练结束才删EXR。未来仍需深度研究时，显式登记消费者、范围和保留理由；不能从模板把状态改成成功。

清理由`tools/storage/dataset_storage_policy.py cleanup-exr`执行：先dryrun生成精确文件清单，再用清单SHA明确apply。只删除列出的EXR，不递归删目录、不跟随联接，不删除PNG、Pose、world、native、轨迹和校准。固定事务日志保存逐项结果；partial保留现场，不自动重放。需要实际成功后处理和EXR消费者结束证据，活动MRQ不清理。

清理完成后记录真实删除数量和字节数，发布版本中的来源记录指向清理收据；旧来源协议保持原bytes，另记文件已退休。EXR删除不可逆失去原深度/Cryptomatte通道；不能将mask和unknown位置标注冒充物理遮挡证据。

测试小夹具和未完成号码开发不按生产媒体批量清理。空间盘点只遍历物理目录/stat，不跟联接、不重复读媒体像素或计算全量媒体hash。Git管理源码、资产和规范，不管理Saved、渲染媒体、模型或环境。
