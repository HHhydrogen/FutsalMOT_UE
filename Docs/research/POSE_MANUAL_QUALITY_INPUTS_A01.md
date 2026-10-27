# 固定120样本盲人工质量输入

更新：2026-10-27。原质量计划五个已观察比赛各24样本，120人物/2040点完整保留。新的盲标包与空模板已实际生成并通过契约验收；这只是输入阶段完成，**实际人工标签和独立复核均为0**，不报PCK、OKS或Pose准确率。

入口：

- [本地盲标页面](D:/projects/FutsalMOT_Research/pose/pose_information_a01/manual_quality_inputs_a01/annotate.html)。由真实标注人用本机浏览器直接打开；页面无模型预测点预填，原图只引用不复制。
- [逐点规范](D:/projects/FutsalMOT_Research/pose/pose_information_a01/manual_quality_inputs_a01/INSTRUCTIONS.md)。COCO17解剖左右、完整原图坐标、visible/v2、可定位遮挡/v1、图外或不可判定/v0分别记录，不能猜点或删除难例。
- [空模板](D:/projects/FutsalMOT_Research/pose/pose_information_a01/manual_quality_inputs_a01/annotations_pending.json)与[实际pending验收](D:/projects/FutsalMOT_Research/pose/pose_information_a01/manual_quality_inputs_a01/pending_contract_receipt.json)。全部120 annotation pending、2040 point pending，0坐标提交、0复核、0准确率指标。

首标人和另一位真实复核人分别操作；逐点点击/不可判定选择、人员声明、UTC和内容摘要保留。修改标注后旧复核失效。JSON与操作日志只能检查可审计契约，不能证明真人身份、独立性或排除蓄意抄写。人员安排已向用户询问，等待回复期间，性能和零更新诊断继续。

6项CPU合同、Python解析与生成页面JavaScript语法检查通过。实际prepare只一次stream核五个原预测缓存的UID/帧/尺寸/SHA及原图stat，保留明确索引路径，不解码、媒体hash、复制原图、运行模型或重选样本。正式标注前不得查看原计划中的模型坐标；公开模板已剥离它们。

自动UI预览有明确限制：Codex Browser Use拒绝`file://`协议，只允许HTTP/HTTPS，因此未完成本地页面的浏览器视觉验收。保留这一限制，不能声称页面已经真实浏览器验收；未通过换浏览器、HTTP转发或其他间接方式绕过该拒绝。用户可手动打开本机文件，若浏览器限制原图访问，停止并记录，不换图或丢样。

来源：

- 原120计划SHA：`00b3dc102e33877b5d768d7221cd81f77b96423ee8665ac3d6ac0d611bc980c8`。
- 必要四文件bundle：`D:/projects/FutsalMOT_Research/code/4014d4163c2771fb3fe8040ca850c1735b2db1905d8fbebab24544ed3d54d36a`。
- manifest SHA：`c346e11cb64061043aa07b2c0c470d0d5b2687fb48e20dc8634111d1eefa37ee`。
- 空模板SHA：`43b29e7583d2a166272a5ac992cad6730442e5f4768d4825389291c47f61dde5`。
- [输入完成收据](D:/projects/FutsalMOT_Research/pose/pose_information_a01/manual_quality_inputs_a01/complete.json)。研究训练/追踪输入未变，测试继续封存。
