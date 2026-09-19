# PHASE4B2_PRODUCTION_MIGRATION_REPORT — L_FutsalCourt Player 迁移

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `ad11a5e8f771bbceebe2bbdc9afcd3acdb2e1c2e`
- checkpoint tag：`phase4b2-before-production-migration`（@ `ad11a5e`）
- 架构基线：
  ```
  MASTER_CHARACTER          = BP_FutsalCharacterBase
  MASTER_ANIMBP             = ABP_FutsalSource
  MASTER_ANIMATION_SKELETON = SK_Mannequin
  ```
- 性质：**正式资产修改**（仅限本迁移范围）。未修改 Skeleton / AnimSequence / Retargeter / IK Rig / Control Rig；未触碰 `UNREAL_RIG.uasset`。

---

## 0. 结论

| 项 | 结果 |
|---|---|
| 10 个 Player actor | `BP_ThirdPersonCharacter_C` → **`BP_FutsalCharacterBase_C`** ✅ |
| ActorGuid | **保留**（`convert_actors` 以原 ActorGuid 重建；R4 实测 `64D3565047C4252CC108D78BD8BAD1BF` 前后一致） |
| Label / Tags / Transform | 保留（`Player_L0..R4`、`PoseL0..PoseR4`、位置/朝向） |
| Mesh（实例） | `SKM_Quinn_Simple` ✅ |
| AnimClass（实例） | `ABP_FutsalSource_C` ✅（不依赖 CDO 默认，显式设置） |
| 6 条 `LS_Cam_*` | Player possessable 已重绑并保存；**10/10 解析成功** ✅ |
| PIE | `L_FutsalCourt` 可加载，10 个角色 AnimInstance = `ABP_FutsalSource_C`，Idle 正常评估 ✅ |
| `UNREAL_RIG.uasset` | 未触碰（保持 `EXTERNAL_UNRESOLVED_CHANGE`） |

---

## 1. STEP 0 — Git Checkpoint

- 迁移前 `git status`：`UNREAL_RIG.uasset`(M) + `L_FutsalCourt.umap`(M) + 5×external actor(M) + 2 份未跟踪 Phase4A/4B1 报告。
- 已创建 annotated tag：`phase4b2-before-production-migration` @ `ad11a5e8f771bbceebe2bbdc9afcd3acdb2e1c2e`（未 push）。
- 另将迁移前 `L_FutsalCourt.umap` + `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/**`（102 文件）复制到本地临时目录作为额外回滚备份。

## 2. STEP 1 — 迁移前快照

- 10 个 Player：`BP_ThirdPersonCharacter_C`、Mesh `SKM_Quinn_Simple`、AnimClass `ABP_FutsalPlayer_C`、Tags `PoseL0..R4`、AutoPossess=DISABLED、8 组件、位置/朝向（L0~L4 于原点 / R0~R4 显式摆放）。
- 6 条序列：各 possesses 全部 10 个 Player（possessable binding，绑定类 `BP_ThirdPersonCharacter_C`）+ `Ball_01` + `CineCam_*`；Player binding 各绑定 **GUID**（如 `LS_Cam_01/Player_L0 = DFE4232E4D17BCC7AF63788DBAAE2BBF`）。

## 3. STEP 2 — Actor Class 替换（方案 A 就地替换）

- 方法：`unreal.get_editor_subsystem(unreal.EditorActorSubsystem).convert_actors([actors], BP_FutsalCharacterBase_C, "")`。
- 先对 `Player_R4` 单体验证，再批量处理其余 9 个。
- 实测（R4）：Class `BP_ThirdPersonCharacter_C` → `BP_FutsalCharacterBase_C`；**ActorGuid 不变**（`64D35650...`）；Label `Player_R4`、Tags `[PoseR4]`、Transform 保留；新 CDO 默认导致 Mesh/AnimClass 变为 `None`（由 STEP 3 修正）。
- 说明：`convert_actors` 会销毁旧 actor、以**同一 ActorGuid**重建，因此 actor 对象名与 external actor 包路径发生变化（旧包删除、新包生成），但 GUID 保留使外部引用可重新解析。

## 4. STEP 3 — 实例属性修正

- 对全部 10 个实例的 `CharacterMesh0` 通过 MCP `ObjectTools.set_properties` 设置：
  - `skeletalMeshAsset` = `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple`
  - `animClass` = `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource.ABP_FutsalSource_C`
- 不依赖 `BP_FutsalCharacterBase` 的 CDO 默认（该 CDO 仍为 None/None）。

## 5. STEP 4 — Sequence Binding 修复

- **问题**：`convert_actors` 后，6 条序列的 Player possessable 解析失败（`get_bound_objects` 返回 0），而 `Ball_01`/`CineCam_*` 正常解析（1）。原因是 possessable 缓存的 `PossessedObjectClass` 仍为 `BP_ThirdPersonCharacter_C`，与实际新类不匹配。
- **修复**：对每条序列的每个 Player possessable 执行
  1. `nb = sequence.add_possessable(新 actor)`
  2. `old.move_binding_contents(nb)`（迁移轨道，含 `MovieScene3DTransformTrack`）
  3. `old.remove()`
  4. `nb.set_display_name("Player_x")`
- 6 条序列全部处理后 `save_asset`。
- 修复后：每条序列 10/10 Player binding 解析成功，显示名保持 `Player_L0..R4`，轨道随绑定迁移。（binding GUID 因重绑而更新；序列内轨道与相机/球绑定不受影响。）

## 6. STEP 5 — 验证

| 验证项 | 结果 |
|---|---|
| 10 个 Player Class | 全部 `BP_FutsalCharacterBase_C` ✅ |
| Mesh | 全部 `SKM_Quinn_Simple` ✅ |
| AnimClass | 全部 `ABP_FutsalSource_C` ✅ |
| 序列 Player binding | 6 条 × 10 = 60 条，`resolved = 10/10` each ✅ |
| PIE 加载 | `UEDPIE_0_L_FutsalCourt` 成功加载 ✅ |
| PIE 动画 | 10/10 AnimInstance = `ABP_FutsalSource_C`；采样 `Use Auto Motion Speed=True`、`ShouldMove=False`、`Effective Motion Speed Mps=0`（Idle 正常评估）✅ |
| Transform/Tags 保留 | ✅ |

- 重新加载关卡后再次校验，结果一致（持久化成功）。
- 说明：T-pose/Idle/Locomotion/Pose/Camera Sequence 的**视觉**终验建议由人工 PIE 复核（本阶段程序化确认 AnimInstance 存在且非 None，排除“无 AnimClass 导致 T-pose”的主因）。

## 7. STEP 6 — Git

- 本迁移涉及文件：
  - `M Content/FutsalMOT/Maps/L_FutsalCourt.umap`
  - `M Content/FutsalMOT/Sequences/LS_Cam_01.uasset` … `LS_Cam_P01.uasset`（6 条；**经用户批准纳入提交**）
  - `D` 10 个旧 `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/**`（旧 actor 包）
  - `??` 10 个新 `Content/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/**`（新 actor 包，同 GUID）
  - `A PHASE4B2_PRODUCTION_MIGRATION_REPORT.md`
- **不提交**：`Content/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG.uasset`（保持 `EXTERNAL_UNRESOLVED_CHANGE`）。
- `Commit`：`Migrate L_FutsalCourt players to FutsalCharacterBase`
- `Tag`：`phase4b2-production-migration`（annotated，不 push）

---

## 附：偏差与说明

- **序列资产纳入提交**：用户 STEP 6 原允许列表未含 6 条 `LS_Cam_*`，但迁移导致其 Player 绑定失效，必须修改；已获用户确认一并提交。
- Actor 对象名与 external actor 包路径变化属 `convert_actors` 的正常行为；ActorGuid 保留是绑定可修复的前提。
- 未修改 `UNREAL_RIG.uasset` / Skeleton / AnimSequence / Retargeter / IK Rig / Control Rig。
- 未执行 `git push`。
