# PROJECT_CLEANUP_REPORT — Phase 5A 项目整理报告

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `de611502964937e16f92fa06d28f86be0c28a33c`（checkpoint tag `phase5-before-project-cleanup`）
- 性质：正式整理阶段（文档重组 + 有限资产归档）。未修改 `UNREAL_RIG.uasset`、Skeleton、AnimSequence、Retargeter、IK Rig、Control Rig、Epic 模板内容。

## 1. Before — 资产/文档树（摘要）

- 仓库根目录：**14 份 `PHASE*.md`**（Phase 1–4 报告/审计）+ `README.md` + `AGENTS.md` + 配置文件。
- 资产：`/Game/FutsalMOT/Blueprints/BP_PoseRecorder_Proto`（0 referencers、0 deps）散落在 Blueprints 根。
- 无 `Docs/`、无 `_Archive/`。

## 2. After — 资产/文档树（摘要）

- 仓库根目录：仅 `README.md`（入口索引）+ `AGENTS.md` + 配置（`.mcp.json`、`opencode.json`、`.uproject`、`.gitignore`、`.gitmodules`）。
- 新增 `Docs/`：
  ```
  Docs/Architecture/{PROJECT_ARCHITECTURE.md, ASSET_STRUCTURE.md, PROJECT_CLEANUP_REPORT.md}
  Docs/History/PhaseReports/（14 份历史报告）
  Docs/History/Diagnostics/（预留，含 README.md）
  ```
- 新增 `/Game/FutsalMOT/_Archive/AbandonedExperiments/`（1 资产）。

## 3. Archived Assets

| Asset | From | To | Reason |
|---|---|---|---|
| `BP_PoseRecorder_Proto` | `/Game/FutsalMOT/Blueprints/BP_PoseRecorder_Proto` | `/Game/FutsalMOT/_Archive/AbandonedExperiments/BP_PoseRecorder_Proto` | 0 referencers、0 deps；被 `BP_PoseRecorderC4_G0..G4` 新体系取代；无生产/未来依赖 |

**ARCHIVED_ASSETS = 1**

### 归档延后（技术债）

| Asset | 计划 | 未执行原因 |
|---|---|---|
| `ABP_FutsalPlayer` | ARCHIVE（`_Archive/LegacyAnimation/`） | 其唯一 referencer 为 **Epic 模板资产 `BP_ThirdPersonCharacter`**；移动会更新模板引用（内容修改），违反本阶段“不得修改 ThirdPerson 模板资产内容”的约束。留原位，标注 ARCHIVE。 |

## 4. Deleted Assets

**DELETED_ASSETS = 0**

| 候选 | 判定 | 原因 |
|---|---|---|
| `BP_SoccerPlayer` | 保留（EXPERIMENTAL） | 引用独特球衣材质 `MI_Player_TShirt_Test`（appearance 价值），不满足“无独特材质成果” |
| `ABP_SoccerPlayer` | 保留（EXPERIMENTAL） | 被保留的 `BP_SoccerPlayer` 引用，属 UNREAL_RIG appearance 实验 |
| `BP_ThirdPersonCharacter_Soccer` | 保留（TEMPLATE_BASELINE） | 位于 `/Game/ThirdPerson/**`，STEP 3 明确禁止删除模板目录 |
| `BP_PoseRecorder_Proto` | 改为 ARCHIVE | 保留历史实现 |

> 无资产同时满足 6 条 DELETE_CONFIRMED 判据；按规则改为 ARCHIVE / EXPERIMENTAL，未强行删除。

## 5. Preserved Experimental Assets（UNREAL_RIG / Soccer 实验）

- `UNREAL_RIG`、`UNREAL_RIG_Skeleton`
- `ABP_FutsalPlayer_Soccer`、`BS_Futsal_Locomotion_Soccer`、`*_Soccer` AnimSequences ×20
- `IKR_SoccerPlayer`、`RTG_Quinn_To_SoccerPlayer`（仍为已烘焙 `*_Soccer` 的唯一可追溯生成来源）
- `ABP_SoccerPlayer`、`BP_SoccerPlayer`
- 0 引用材质变体（`MI_Player_TShirt_Red`、`MI_Futsal_Field_Grass` 等）保持原位

## 6. Template Baseline（保留、未移动、未修改）

- `/Game/ThirdPerson/**`（`BP_ThirdPersonCharacter`、`BP_ThirdPersonCharacter_Soccer`、`BP_ThirdPersonGameMode`、`BP_ThirdPersonPlayerController`、`Lvl_ThirdPerson`）
- `/Game/Input/**`（`IA_*`、`IMC_*`、Touch）
- `/Game/Characters/Mannequins/**`（含生产依赖 `SK_Mannequin`、`SKM_Quinn_Simple`、`CR_Mannequin_FootIK`）

## 7. Production Asset Map

```
L_FutsalCourt
  └─ 10× Player actor（BP_FutsalCharacterBase_C / SKM_Quinn_Simple / ABP_FutsalSource_C）
       └─ BP_FutsalCharacterBase → BPI_FutsalAnimationSource + IA_Futsal_*
       └─ ABP_FutsalSource → BPI_FutsalAnimationSource + BS_Futsal_Locomotion + SK_Mannequin + CR_Mannequin_FootIK
```

目录：`Animation/Source`、`Animation/Interfaces`、`Animation/BS_Futsal_Locomotion`、`Characters/Base`、`Input`、`Maps`、`Sequences`、`Test`、`Blueprints`（Ball/GameMode/FieldKeypoint/Pose/**）。

## 8. Appearance Prototype Map

```
UNREAL_RIG + UNREAL_RIG_Skeleton（APPEARANCE_PROTOTYPE）
   ├─ ABP_FutsalPlayer_Soccer → BS_Futsal_Locomotion_Soccer → *_Soccer ×20
   ├─ ABP_SoccerPlayer / BP_SoccerPlayer（stub + 球衣材质）
   └─ Retarget：IKR_Quinn → RTG_Quinn_To_SoccerPlayer → IKR_SoccerPlayer
SoccerSource/LS_*_InPlace ×7（SK_Mannequin，未接线，未来动画库）
```

## 9. Document Cleanup

- **MOVED_DOCUMENTS = 14**：`PHASE1_REPORT.md`、`PHASE1_5_TEST_REPORT.md`、`PHASE1_6_STABILIZATION_REPORT.md`、`PHASE2A_INPUT_AUDIT_REPORT.md`、`PHASE2B_INPUT_REWIRE_REPORT.md`、`PHASE2B_MANUAL_REWIRE_VERIFICATION.md`、`PHASE2B2_PLAYERCONTROLLER_TEST_REPORT.md`、`PHASE3A_ANIMATION_OWNERSHIP_AUDIT.md`、`PHASE3B_SOURCE_ANIMBP_EXTRACTION_REPORT.md`、`PHASE3C_RUNTIME_VALIDATION_REPORT.md`、`PHASE4A_ANIMATION_STANDARDIZATION_AUDIT.md`、`PHASE4B1_PRODUCTION_MIGRATION_AUDIT.md`、`PHASE4B2_PRODUCTION_MIGRATION_REPORT.md`、`PHASE4C_LEGACY_CHAIN_AUDIT.md` → `Docs/History/PhaseReports/`
- **DELETED_DOCUMENTS = 0**（无文件被判定为可安全删除）
- 新增长期文档：`Docs/Architecture/PROJECT_ARCHITECTURE.md`、`Docs/Architecture/ASSET_STRUCTURE.md`、`Docs/History/Diagnostics/README.md`
- 更新 `README.md` 为入口索引（含 Master 定义、生产链摘要、Docs 链接）
- `Docs/History/Diagnostics/` 当前为空（无纯失败诊断文档；历史 `PHASE*.md` 均具阶段价值，归入 PhaseReports）

## 10. Redirectors Fixed

- **0**。归档的唯一资产 `BP_PoseRecorder_Proto` 无 referencers，`rename_asset` 未产生 redirector（旧路径已不存在）。
- 未执行任何全局 Fix Up Redirectors。

## 11. Production Dependency Proof

对 119 个生产相关包（`L_FutsalCourt`、6 条 `LS_Cam_*`、`BP_FutsalCharacterBase`、`BP_FutsalPlayerControllerBase`、`ABP_FutsalSource`、`BPI_FutsalAnimationSource`、`BS_Futsal_Locomotion`、`/Game/FutsalMOT/Input/**`、L_FutsalCourt 全部 external actor 包）扫描依赖：

- 对 `/Game/FutsalMOT/_Archive/**` 依赖 = **0**
- 对 `/Game/ThirdPerson/**` 依赖 = **0**
- 对 `/Game/Input/**` 依赖 = **0**
- 对 `ABP_FutsalPlayer` / `BP_ThirdPersonCharacter` 依赖 = **0**
- 核心链确认：`Player actor pkg → BP_FutsalCharacterBase + ABP_FutsalSource + SKM_Quinn_Simple`；`BP_FutsalCharacterBase → BPI_FutsalAnimationSource + IA_Futsal_*`；`ABP_FutsalSource → SK_Mannequin + BS_Futsal_Locomotion + BPI_FutsalAnimationSource`

## 12. Git Changed Files

- `M`/`D`：`BP_PoseRecorder_Proto`（旧路径删除）+ `_Archive/AbandonedExperiments/BP_PoseRecorder_Proto`（新增）+ redirector（无）
- `R`：14 份 `PHASE*.md` 根 → `Docs/History/PhaseReports/`
- `A`：`Docs/Architecture/*`、`Docs/History/Diagnostics/README.md`
- `M`：`README.md`
- **不含**：`UNREAL_RIG.uasset`（保持 `EXTERNAL_UNRESOLVED_CHANGE`，未 stage）、模板资产内容、生产地图/AnimBP/Skeleton 内容修改。

## 13. Remaining Technical Debt

1. **`ABP_FutsalPlayer` 未归档**：被模板资产 `BP_ThirdPersonCharacter` 引用；需在未来单独阶段处理（解耦模板引用后再归档）。
2. **`ABP_FutsalPlayer_Soccer` 对 `BP_ThirdPersonCharacter` 的依赖未解**（EXPERIMENTAL）。
3. **`BP_ThirdPersonCharacter` 仍依赖 `/Game/Input/**` 与 `ABP_FutsalPlayer`**（模板基线，暂不动）。
4. **`Config/DefaultEngine.ini` 地图漂移**（`L_Futsal_Demo` 不存在）未修复。
5. **UNREAL_RIG appearance 链暂未定稿**（`*_Soccer` / RTG / IKR_SoccerPlayer 保留）。
6. **0 引用材质变体**未清理（暂列 EXPERIMENTAL）。
