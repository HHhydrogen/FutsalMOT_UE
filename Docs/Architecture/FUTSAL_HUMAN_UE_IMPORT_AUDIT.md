# FUTSAL_HUMAN_UE_IMPORT_AUDIT — FutsalHuman UE 导入兼容性审计（Phase 5C.2 / 5C.2b）

- 更新时间：2026-09-22
- 基线：branch `refactor/character-architecture` @ `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`
- **Phase 5C.2b 补充（2026-09-22）**：Phase 5C.2 的「geometry-only 阻断」已在 Blender 导出层修复。使用新的 `FutsalHuman_Compatibility_01_GameEngine_SKINNED.fbx` 完成了 SkeletalMesh + Skeleton 导入并跑通 STEP 3–11。上文 Phase 5C.2 的 BLOCKED 结论仅对旧的 geometry-only FBX 有效，已被取代。详见文末「Phase 5C.2b」章节。
- **Phase 5C.2c 补充（2026-09-22）**：通过导出瞬间临时命名 Armature 为 `Armature`，成功消除额外顶层骨 `Human_rig`，得到 Top=`Root`/53 骨/A-Pose/165.94 cm 的 RootClean 候选（隔离目录，未替换工作资产）。详见文末「Phase 5C.2c — Root Normalization Spike」章节。
- **Phase 5C.2d 补充（2026-09-22）**：在 RootClean 基础上把临时导出副本转换到 centimeter workspace，得到 Root Scale=`(1,1,1)`、53 骨、Top=`Root`、A-Pose、165.94 cm 的 CM-normalized 候选（隔离目录）。`ROOT_SCALE_NORMALIZATION_IMPROVEMENT = YES`。详见文末「Phase 5C.2d — Root Scale Normalization Spike」章节。
- **Phase 5C.3 补充（2026-09-22）**：以 `IKR_Quinn`（复用）为 Source IK Rig、新建 `IKR_FutsalHuman_Compatibility` + `RTG_Mannequin_To_FutsalHuman_Compatibility`，批量 retarget 了 6 个最小测试动画到 `RetargetSpike/Animations/`。数值验证全 PASS（root scale=1、in-place 稳定、root motion 合法、前向轴一致）；形变视觉项为 REVIEW（需人工）。`FUTSAL_HUMAN_SKELETON_STANDARD_V1 = READY_TO_FREEZE`（结构/功能）。详见文末「Phase 5C.3 — Retarget Compatibility Spike」章节。
- **Phase 5C.4 补充（2026-09-22）**：人工视觉签核通过后，创建生产规范资产 `SKM_FutsalHuman_Base` / `SK_FutsalHuman` / `IKR_FutsalHuman` / `RTG_Mannequin_To_FutsalHuman`，回归与引用审计全 PASS，**`FUTSAL_HUMAN_SKELETON_STANDARD_V1 = FROZEN`**。测试资产按约束保留。详见文末「Phase 5C.4 — FutsalHuman Skeleton Standard V1 Freeze」章节。
- **Phase 5C.5 补充（2026-09-22）**：审计 `ABP_FutsalSource` 运行时依赖；离线重定向 20 个序列（全 PASS）并创建 `BS_FutsalHuman_Locomotion`（27 samples，全 PASS）；创建 `ABP_FutsalHuman`（目标骨架 `SK_FutsalHuman`、图结构等价、可编译）。**BLOCKED**：Python 复制 ABP 后 EdGraph pin 缓存仍硬引用源动画（`SOURCE_ANIMATION_RUNTIME_REFERENCES = 5`，未清零），且源 `CR_Mannequin_FootIK` 与目标骨架不兼容（11 条告警）。详见文末「Phase 5C.5 — Build Canonical ABP_FutsalHuman」章节。
- 审计性质：**只读**（未创建 / 未重命名 / 未重导入 / 未修改 Skeleton / 未修改 Reference Pose / 未修改骨骼层级 / 未 stage / 未 commit / 未 tag / 未 push）
- 审计方法：Unreal MCP 原生 Toolset（AssetTools / SkeletalMeshTools / LogsToolset）+ `FutsalMOTTools.run_python_code` 真实 UE Python 只读诊断 + 对源 FBX 二进制做结构 token 核验

---

## 0. 结论摘要

**本次审计发现一个位于管线输入端的阻断性问题：**

> 被审计的 FBX（`FutsalHuman_Compatibility_01_GameEngine.fbx`）**不包含任何骨架 / 蒙皮数据**，因此 UE 5.8 导入后只生成 **1 个 StaticMesh**，并未生成 SkeletalMesh + Skeleton。

因此本阶段所有依赖 Skeleton 的检查项（STEP 5–11）**无法执行**，最终分类为：

```
IMPORT_COMPATIBILITY = BLOCKED
FUTSAL_HUMAN_SKELETON_STANDARD_V1 = NOT_FROZEN
```

阻断点不在 UE 导入配置，而在 **Blender → FBX 导出产物本身**（无 armature / 无 skin）。详见「§ 12 矛盾报告」。

---

## 1. Blender / MPFB 版本

| 项 | 值 |
|---|---|
| Blender | 5.1.1 |
| MPFB | 2.0.17 |
| Rig preset | Game engine |
| Blender Scene Units | Metric / Unit Scale 1.0 / Meters |
| Human 对象变换 | Location (0,0,0) / Rotation (0,0,0) / Scale (1,1,1) |
| Human.rig 对象变换 | Location (0,0,0) / Rotation (0,0,0) / Scale (1,1,1) |
| Blender 人物尺寸 | X≈1.65 m / Y≈0.297 m / Z≈1.66 m |
| Rest Pose | MPFB Game Engine 原生 A-Pose（T-Pose 仅作为 Current Pose，未应用为 Rest Pose） |

## 2. FBX 导出基线

### 2.1 预期导出设置（用户声明）

- Selected Objects = ON；Objects: Mesh = ON、Armature = ON
- Scale = 1.0；Apply Scaling = FBX Units Scale
- Forward = -Y Forward；Up = Z Up
- Apply Unit = ON；Use Space Transform = ON；Apply Transform = OFF
- Apply Modifiers = ON
- Primary Bone Axis = Y；Secondary Bone Axis = X
- Armature FBX Node Type = Null
- Only Deform Bones = OFF；Add Leaf Bones = OFF
- Bake Animation = OFF

### 2.2 源文件核验（实测）

| 项 | 值 |
|---|---|
| 文件 | `D:/projects/FutsalMOT_blender/FutsalHuman_Compatibility_01_GameEngine.fbx` |
| 大小 | 724284 字节 |
| 修改时间 | 2026-09-22 13:07:29 |
| 格式 | Kaydara FBX Binary |
| UE 记录 MD5 | `1c4deef405464141777e76206092a621` |

对 FBX 二进制做结构 token 扫描（节点名在 binary FBX 中为未压缩明文字符串，扫描有效）：

| token | 命中数 | 含义 |
|---|---|---|
| `Deformer` / `SubDeformer` / `Cluster` | 0 / 0 / 0 | 无蒙皮数据 |
| `Skin` / `BindPose` / `Pose` | 0 / 0 / 0 | 无蒙皮绑定 / 无绑定姿势 |
| `LimbNode` | 0 | 无骨骼节点 |
| `Armature` | 0 | 无骨架节点 |
| `pelvis` / `spine_01` / `thigh_l` / `upperarm_l` | 0 / 0 / 0 / 0 | 无任何骨骼名 |
| `Geometry` | 4 | 存在几何体 |
| `Model` / `Mesh` | 3 / 3 | 存在模型 / 网格节点 |
| `Vertices` / `PolygonVertexIndex` | 1 / 1 | 存在顶点与面索引 |
| `LayerElementUV` / `LayerElementNormal` | 2 / 2 | 存在 UV / 法线层 |
| `Material` / `Texture` / `Video` | 0 / 0 / 0 | 无材质 / 贴图 |
| `AnimCurve` / `AnimationStack` / `AnimationLayer` | 0 / 0 / 0 | 无动画 |

**实测结论：该 FBX 是纯静态几何导出，不含 armature、不含 skin cluster、不含任何骨骼。** 与 §2.1 声明的「Armature = ON、Only Deform Bones = OFF」不符。

## 3. UE 导入设置（预期意图）

- Skeleton = None；Try Auto Select Skeleton = OFF
- Import Skeletal Mesh = ON；Geometry + Skin Weights
- Import Animations = OFF；Import Morph Targets = OFF
- Use T0 As Ref Pose = OFF；Update Skeleton Reference Pose = OFF
- Create Physics Asset = OFF
- Import Materials = OFF；Import Textures = OFF
- Import Translation = (0,0,0)；Import Rotation = (0,0,0)；Import Uniform Scale = 1.0

> 说明：由于 FBX 中没有骨架/蒙皮，即使上述意图正确，导入器也只能产出静态网格。

## 4. 导入资产路径（实测）

目标文件夹 `/Game/FutsalMOT/Test/FutsalHumanCompatibility/` 下**仅存在 1 个资产**：

| 资产 | 路径 | 类 |
|---|---|---|
| 网格（实测为 StaticMesh） | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/FutsalHuman_Compatibility_01_GameEngine` | **StaticMesh** |

来源核验（AssetImportData）：该 StaticMesh 确由本次被审计的 FBX 导入
（`RelativeFilename = D:/projects/FutsalMOT_blender/FutsalHuman_Compatibility_01_GameEngine.fbx`）。

全项目资产扫描（只读）结果，未发现任何 FutsalHuman 相关 SkeletalMesh / Skeleton：

- SkeletalMesh：`/Game/FutsalMOT/Characters/FutsalPlayer/Meshes/UNREAL_RIG`、`/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple`、`/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple`
- Skeleton：`/Game/FutsalMOT/Characters/FutsalPlayer/Skeleton/UNREAL_RIG_Skeleton`、`/Game/Characters/Mannequins/Meshes/SK_Mannequin`
- PhysicsAsset：`/Game/Characters/Mannequins/Rigs/PA_Mannequin`

**未发现**本 FBX 生成的 Skeleton、PhysicsAsset、Animation、Material、Texture。

## 5. Mesh 尺寸（实测，StaticMesh）

| 项 | 值 |
|---|---|
| Vertices (LOD0) | 1134 |
| Triangles (LOD0) | 1762 |
| LOD 数 | 1 |
| Material Slot 数 | 1（默认 `WorldGridMaterial`，因 Import Materials = OFF） |
| UV 通道数 | 1 |
| Morph Target | 不适用（StaticMesh） |
| Bounds Origin | ≈ (0.000002, 11.949, 82.972) cm |
| Bounds Extent | ≈ (52.553, 21.499, 82.972) cm |
| Bounds Min | ≈ (-52.553, -9.550, 0.000) cm |
| Bounds Max | ≈ (52.553, 33.447, 165.943) cm |
| AssetRegistry ApproxSize | 106 x 45 x 168 cm |
| Nanite | 已启用 |

## 6. Root hierarchy

**无法评估** —— 不存在 Skeleton 资产。

```
SKELETON_TOP_LEVEL_BONE     = N/A（无 Skeleton）
EXTRA_ARMATURE_ROOT_NODE    = N/A（无 Skeleton）
ROOT_HIERARCHY              = BLOCKED
```

## 7. Bone count

```
UE_BONE_COUNT        = N/A（无 Skeleton）
EXPECTED_BONE_COUNT  = 53
BONE_COUNT_MATCH     = BLOCKED
```

## 8. Full hierarchy validation

```
CORE_BODY_HIERARCHY = BLOCKED
LEFT_ARM_CHAIN      = BLOCKED
RIGHT_ARM_CHAIN     = BLOCKED
LEFT_LEG_CHAIN      = BLOCKED
RIGHT_LEG_CHAIN     = BLOCKED
FINGER_CHAINS       = BLOCKED
```

原因：FBX 实测无骨骼（见 §2.2），UE 无 Skeleton 可校验。

## 9. Reference pose

```
REFERENCE_POSE        = N/A（无 Skeleton）
REFERENCE_POSE_IMPORT = BLOCKED
```

说明：由于 FBX 中无 rest/reference pose 数据（`BindPose` / `Pose` token 命中 0），无法判定 A-Pose / T-Pose。未执行任何 `Use T0 As Ref Pose` / `Update Reference Pose` / `Apply Retarget Pose` 操作。

## 10. Orientation（由 bounds 推断，未做任何旋转 / 变换）

| 项 | 结论 |
|---|---|
| UP 轴 | **+Z**（Bounds Z 0→165.94，X/Y 为水平范围） |
| 是否直立 | 推断直立（Z 为最大跨度且与 1.66 m 人体身高一致） |
| 头在骨盆之上 / 脚在骨盆之下 | 从 Z 范围推断成立 |
| 是否侧躺 / 倒置 | 否（由 bounds 推断） |
| 前进轴（Forward） | **UNKNOWN**（无 Skeleton / 无法在当前模型下通过只读数值可靠判定 Y 朝向；且本项对静态网格无意义） |

```
CHARACTER_UPRIGHT                    = PASS（由 bounds 推断）
UP_AXIS                              = +Z
CHARACTER_FORWARD_AXIS               = UNKNOWN
IMPORT_ROTATION_CORRECTION_REQUIRED  = NO（未发现坐标轴错乱证据）
```

## 11. Physical scale

```
UE_CHARACTER_HEIGHT_CM = 165.94（≈1.659 m）
EXPECTED_HEIGHT_CM     = ~166
HEIGHT_ERROR_PERCENT   = ~0.04%
PHYSICAL_SCALE         = PASS
```

未出现 ~1.66 cm / ~16.6 cm / ~1660 cm / ~16600 cm 级别的灾难性缩放错误。**但注意：此 PASS 仅针对静态网格几何高度，不能替代「带骨架 SkeletalMesh 的缩放校验」。**

## 12. Skin weight / deformation sanity

```
SKIN_BINDING              = N/A（StaticMesh，无蒙皮）
CATASTROPHIC_WEIGHT_ERROR = N/A
```

由于产物是 StaticMesh，不存在顶点权重 / 骨骼绑定，本项整体 **BLOCKED**。

## 13. Bone transform / orientation sanity

```
BONE_TRANSFORM_SANITY      = BLOCKED（无 Skeleton）
NEGATIVE_SCALE_DETECTED    = N/A
NONFINITE_BONE_TRANSFORM   = N/A
```

## 14. Source vs Target retarget readiness

- Source（预期）：`SK_Mannequin`（Mannequin 骨架，含 twist / IK helper）
- Target（实测）：**不存在** Skeleton（FBX 无骨骼）
- 语义映射方案（预期目标链）：`Root → pelvis → spine_01..03 → neck_01 → head`，`clavicle/upperarm/lowerarm/hand_l|r`，`thigh/calf/foot/ball_l|r`，五指各三节 L/R

```
CORE_RETARGET_CHAIN_MAPPING = NOT_READY
TWIST_BONE_DIFFERENCE       = EXPECTED（且当前 target 连骨骼都缺失）
IK_HELPER_BONE_DIFFERENCE   = EXPECTED（同上）
```

## 15. Mannequin compatibility risk audit

| 风险 | STATUS | EVIDENCE（实测事实） | NEXT TEST（Retarget 阶段需验证） |
|---|---|---|---|
| A. root hierarchy mismatch | **BLOCKER** | 无 Skeleton，无法产生任何根骨层级 | 修复导出后核对 `Root → pelvis` |
| B. scale mismatch | LOW | StaticMesh 高度 165.94 cm ≈ 1.66 m | 修复后确认 SkeletalMesh 高度一致 |
| C. axis mismatch | LOW（未证实） | Z-up、直立；Forward 未定 | 修复后核对前进轴与 SK_Mannequin |
| D. reference pose difference | **BLOCKER** | FBX 无 BindPose/Pose 数据 | 修复后确认导入为 MPFB 原生 A-Pose |
| E. twist bone absence | EXPECTED | 无骨骼（MPFB GE rig 本就无 twist） | 确认重定向是否需要 twist 代偿 |
| F. IK helper absence | EXPECTED | 无骨骼（MPFB GE rig 本就无 IK helper） | 确认 locomotion 重定向不依赖 IK helper |
| G. spine bone count difference | UNKNOWN | 无骨骼，无法计数 | 修复后核对 spine_01..03 |
| H. finger chain difference | UNKNOWN | 无骨骼 | 修复后核对五指三节 L/R |
| I. bone naming mismatch | **BLOCKER（当前）** | FBX 中无任何骨骼名 | 修复后核对命名语义映射 |
| J. skinning quality | **BLOCKER** | 无蒙皮数据 | 修复后验证肩/肘/腕/髋/膝/踝权重 |

## 16. Import artifact audit

```
UNEXPECTED_PHYSICS_ASSET = NO
UNEXPECTED_ANIMATION     = NO
UNEXPECTED_MATERIAL      = NO
UNEXPECTED_TEXTURE       = NO
```

`/Game/FutsalMOT/Test/` 全量资产仅 4 个（1 个 StaticMesh + 1 个 Blueprint + 2 个 World），无导入副作用产物。

**但存在一个「非预期产物类型」：** 预期为 SkeletalMesh，实际得到 StaticMesh（见 §12 矛盾报告）。

## 17. 矛盾报告（Contradiction）

> 按 STEP 15 要求，将矛盾单独报告，不静默改写既有管线架构。

**矛盾：** 既有设计与 Phase 5C.2 前提假定「MPFB Game Engine → Blender FBX → UE 导入」会产出 **SkeletalMesh + Skeleton**；但实测该 FBX 与 UE 导入结果均表明产物为 **StaticMesh**，且 FBX 内**无 armature / 无 skin / 无骨骼名**。

**已排除的可能：**

- 不是 UE 导入配置问题：导入产物确由本 FBX 生成，且资产类型完全符合「无蒙皮几何」的导入结果。
- 不是检索遗漏：全项目 Asset Registry 扫描无任何本 FBX 生成的 SkeletalMesh / Skeleton。
- 不是命名差异：按 `FutsalHuman` / `GameEngine` / `Compatibility_01` 全项目搜索均只命中该 StaticMesh。

**最可能根因（待 Blender 侧确认，本次未修改 Blender）：** 导出时实际未包含骨架，或导出对象选择未真正包含 `Human.rig` armature（FBX 中 `Armature`/`LimbNode`/`Deformer` 命中均为 0），导致 `Only Deform Bones = OFF` 等设置实际未生效。

**未修改任何既有架构决策**；本审计仅记录矛盾，不自动修复。

---

## 18. FINAL STRUCTURED RESULT

```
PHASE5C2_UE_IMPORT_AUDIT            = BLOCKED

IMPORTED_SKELETAL_MESH              = NONE
                                      （实际产物为 StaticMesh：
                                       /Game/FutsalMOT/Test/FutsalHumanCompatibility/FutsalHuman_Compatibility_01_GameEngine）
IMPORTED_SKELETON                   = NONE

CHARACTER_UPRIGHT                   = PASS（由 bounds 推断）
CHARACTER_FORWARD_AXIS              = UNKNOWN

UE_CHARACTER_HEIGHT_CM              = 165.94
PHYSICAL_SCALE                      = PASS（仅静态几何高度；骨架缩放未验证）

SKELETON_TOP_LEVEL_BONE             = N/A
EXTRA_ARMATURE_ROOT_NODE            = N/A
ROOT_HIERARCHY                      = BLOCKED

UE_BONE_COUNT                       = N/A
EXPECTED_BONE_COUNT                 = 53
BONE_COUNT_MATCH                    = BLOCKED

CORE_BODY_HIERARCHY                 = BLOCKED
LEFT_ARM_CHAIN                      = BLOCKED
RIGHT_ARM_CHAIN                     = BLOCKED
LEFT_LEG_CHAIN                      = BLOCKED
RIGHT_LEG_CHAIN                     = BLOCKED
FINGER_CHAINS                       = BLOCKED

REFERENCE_POSE                      = N/A
SKIN_BINDING                        = BLOCKED
BONE_TRANSFORM_SANITY               = BLOCKED

TWIST_BONES                         = NOT_PRESENT（因整体无骨骼）
IK_HELPER_BONES                     = NOT_PRESENT（因整体无骨骼）
CORE_RETARGET_CHAIN_MAPPING         = NOT_READY

UNEXPECTED_PHYSICS_ASSET            = NO
UNEXPECTED_ANIMATION                = NO
UNEXPECTED_MATERIAL                 = NO
UNEXPECTED_TEXTURE                  = NO

IMPORT_COMPATIBILITY                = BLOCKED
FUTSAL_HUMAN_SKELETON_STANDARD_V1   = NOT_FROZEN

NEXT_PHASE_RECOMMENDATION           = 先在 Blender 侧确认并修复 FBX 导出确实包含 armature + skin
                                      （仅导出几何是当前阻断根因），再以同一 FBX 重新导入并重跑本审计的
                                      STEP 3–11（不污染现有 Skeleton / Reference Pose）。
```

## 19. Next recommended phase

1. **Blender 导出侧修复（前置阻断项）**：确认 `Human.rig` armature 被真实选中并导出；导出前确认 FBX 内含 `Deformer`/`Cluster`/`LimbNode` 节点；保持 MPFB Game Engine 原生 A-Pose 作为 Rest Pose。
2. 重新导出后，重新导入到 `/Game/FutsalMOT/Test/FutsalHumanCompatibility/`（不改动生产资产）。
3. 重跑本审计 STEP 1–13，重点关注 skeleton root、bone count（期望 53）、层级、reference pose、蒙皮与根骨层级。
4. 仅在上述全部通过后，才进入 Retarget Spike（IKR / RTG）与 `SK_FutsalHuman_Skeleton` 标准化冻结流程。

---

# Phase 5C.2b — 修正后 SKINNED 导入审计结果

- 阶段：Phase 5C.2b（在 Phase 5C.2 BLOCKED 之后的续跑）
- 输入 FBX：`D:/projects/FutsalMOT_blender/FutsalHuman_Compatibility_01_GameEngine_SKINNED.fbx`（947900 字节，2026-09-22 18:51，UE MD5 `579b85e3c8a3f1fb5fc411037bf8cff7`）
- 目标目录：`/Game/FutsalMOT/Test/FutsalHumanCompatibility/`
- 目的：对修正后的 SKINNED FBX 做干净的 UE SkeletalMesh/Skeleton 兼容性验证，并补跑 Phase 5C.2 被 BLOCKED 的 STEP 3–11。

## B.1 两次 FBX 样本对比（旧 FAILED EXPORT vs 新 corrected skeletal export）

| 项 | OLD `..._GameEngine.fbx` | NEW `..._GameEngine_SKINNED.fbx` |
|---|---|---|
| 结论 | **FAILED EXPORT SAMPLE**（geometry-only） | **corrected skeletal export** |
| UE 导入产物 | 1 个 StaticMesh（无 Skeleton） | 1 个 SkeletalMesh + 1 个 Skeleton |
| FBX `Skin` token | 0 | **1** |
| FBX `Cluster` token | 0 | **53** |
| FBX `SubDeformer` token | 0 | **53** |
| FBX `BindPose` token | 0 | **2** |
| FBX `LimbNode` token | 0 | **106** |
| FBX 骨骼名（pelvis / spine_01 / thigh_l / upperarm_l …） | 0（全部缺失） | **全部存在** |
| 网格几何 | 1134 v / 1762 tri | 14517 v / 26756 tri（含 skin 权重后的 LOD0） |

## B.2 导入方法与一次重要工具差异（必须记录）

首次通过 MCP 原生工具 `editor_toolset...SkeletalMeshTools.import_file` 导入时，产物 `SkeletalMesh`/`Skeleton` **结构正确但缩放为源尺寸的 1/100**（pelvis≈0.87、整高≈1.66）。经对照验证，这是**导入工具路径未应用 FBX 场景单位换算**造成的，而非 FBX 本身问题：

- 使用显式 `unreal.FbxImportUI` + `AssetImportTask`（`import_mesh=True`、`import_as_skeletal=True`、`convert_scene=True`、`convert_scene_unit=True`、`skeletal_mesh_import_data.import_uniform_scale=1.0`、无材质/贴图/动画/物理）重新导入后，得到**正确尺寸 165.94 cm**。
- 结论：**后续自动化导入应使用显式 `FbxImportUI`（开启 Convert Scene / Convert Scene Unit），不要依赖该原生 tool 的默认缩放行为。**
- 本阶段已删除那次缩放错误的临时产物与对照产物（`TMP_AuditScaleCheck*`、缩放错误的 `SKM/SK_...`），并以正确设置重新导入。

## B.3 最终导入资产（实际路径）

| 资产 | 路径 | 类 |
|---|---|---|
| SkeletalMesh | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/SKM_FutsalHuman_Compatibility_01` | SkeletalMesh |
| Skeleton | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/SK_FutsalHuman_Compatibility_01` | Skeleton |
| 旧 geometry-only 样本（保留、未触碰） | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/FutsalHuman_Compatibility_01_GameEngine` | StaticMesh |

来源核验：AssetImportData `RelativeFilename = .../FutsalHuman_Compatibility_01_GameEngine_SKINNED.fbx`，Skeleton 引用指向 `SK_FutsalHuman_Compatibility_01`。

## B.4 Mesh 结构（实测）

| 项 | 值 |
|---|---|
| LOD 数 | 1 |
| Vertices (LOD0) | 14517 |
| Triangles (LOD0) | 26756 |
| Material Slot | 1（默认 `WorldGridMaterial`；Import Materials = OFF） |
| UV 通道 | 1 |
| Morph Target | 0 |
| PhysicsAsset | NONE |
| MaxBoneInfluences | 6 |
| Bounds Min/Max Z | ≈ 0.000 / 165.943 cm |

## B.5 Scale / Orientation（STEP 4）

- UE 角色高度 = **165.94 cm**（预期 ~165.94 cm，误差 ~0%）。
- `CHARACTER_UPRIGHT = PASS`；`UP_AXIS = +Z`；双脚在 Z≈0，头在 Z≈166。
- 根骨 `Human_rig` 的参考姿势局部缩放为 (100,100,100)——这是 meters→cm 的单位换算载体；网格几何已是 cm，两者绝对尺寸一致（pelvis 绝对高度 ≈87 cm）。
- `PHYSICAL_SCALE = PASS`。

## B.6 Root Hierarchy（STEP 5）

```
Human_rig (parent = None)   ← 顶层骨骼（Blender armature 对象节点）
└── Root        (parent = Human_rig)
    └── pelvis  (parent = Root)
        └── spine_01 ...
```

- `SKELETON_TOP_LEVEL_BONE = Human_rig`
- `EXTRA_ARMATURE_ROOT_NODE = YES`
- `PELVIS_PARENT = Root`
- `ROOT_HIERARCHY = FAIL`（严格标准要求 `Root` 为顶层；实测顶层为 `Human_rig`）

> 说明：`Human_rig` 是 Blender armature 对象节点，属常见的多出一级根节点，IK Retargeter 可通过 Root→Root 语义映射处理；不计为功能性阻断，但需在 Retarget 阶段显式处理。

## B.7 Bone Count（STEP 6）

```
UE_BONE_COUNT        = 54
EXPECTED_BONE_COUNT  = 53
BONE_COUNT_MATCH     = FAIL
EXTRA_BONES          = [ Human_rig ]   （UE 将 Blender armature 节点导入为 1 个额外骨骼）
MISSING_BONES        = []
```

## B.8 Full Hierarchy（STEP 7）

实测父级关系（节选，全部与 Blender 源一致）：

```
pelvis→Root; spine_01→pelvis; spine_02→spine_01; spine_03→spine_02;
clavicle_l/r→spine_03; upperarm_l/r→clavicle_l/r; lowerarm→upperarm; hand→lowerarm;
neck_01→spine_03; head→neck_01;
thigh_l/r→pelvis; calf→thigh; foot→calf; ball→foot;
index/middle/pinky/ring/thumb 01→hand; 02→01; 03→02（L/R 各五指三节）
```

```
CORE_BODY_HIERARCHY = PASS
LEFT_ARM_CHAIN      = PASS
RIGHT_ARM_CHAIN     = PASS
LEFT_LEG_CHAIN      = PASS
RIGHT_LEG_CHAIN     = PASS
FINGER_CHAINS       = PASS
```

## B.9 Reference Pose（STEP 8）

由参考姿势绝对骨位推断：手部明显低于肩部（肩 Z≈132 cm，手 Z≈102 cm，低约 30 cm），双手水平跨距 ≈91 cm，远小于身高 166 cm——符合手臂下垂的 **A-Pose**，而非 T-Pose（T-Pose 双手应与肩同高、跨距≈身高）。

```
REFERENCE_POSE        = A_POSE
REFERENCE_POSE_IMPORT = PASS
```

未执行 `Use T0 As Ref Pose` / `Update Reference Pose` / `Apply Retarget Pose`。

## B.10 Skin Binding（STEP 9）

只读结构性检查：

- 网格已绑定 Skeleton（`get_skeleton` → `SK_FutsalHuman_Compatibility_01`）；
- 蒙皮网格包围盒非退化（0→165.94 cm，脚在地面、头在顶端），无 exploded / 全原点 / 整体塌陷迹象；
- MaxBoneInfluences = 6，FBX 含 `Skin=1` / `Cluster=53` / `SubDeformer=53`；
- 根骨单位缩放 100 与网格 cm 几何一致（绝对骨架与网格同尺度）。
- 当前可用的只读 tooling 未暴露逐顶点权重图，故未做逐顶点权重直读；已在此限制下给出结构性判定，最终变形质量留待 Retarget 阶段。

```
SKIN_BINDING              = PASS（结构性）
CATASTROPHIC_WEIGHT_ERROR = NO
```

## B.11 Bone Transform Sanity（STEP 10）

```
BONE_TRANSFORM_SANITY    = PASS
NEGATIVE_SCALE_DETECTED  = NO
NONFINITE_BONE_TRANSFORM = NO
```

- 全部 54 根骨骼参考姿势变换有限（non-finite 列表为空）、无零长度骨（zerolen 列表为空）、无负缩放。
- 唯一非单位缩放：根骨 `Human_rig` = (100,100,100)，为 meters→cm 单位换算载体，属预期而非异常。

## B.12 Retarget Readiness（STEP 11）

目标链语义映射：

```
Root     : Root（UE 顶层为 Human_rig，映射时取 Root）
Pelvis   : pelvis
Spine    : spine_01 → spine_02 → spine_03
Neck     : neck_01
Head     : head
LeftArm  : upperarm_l → lowerarm_l → hand_l
RightArm : upperarm_r → lowerarm_r → hand_r
LeftLeg  : thigh_l → calf_l → foot_l → ball_l
RightLeg : thigh_r → calf_r → foot_r → ball_r
```

```
CORE_RETARGET_CHAIN_MAPPING = READY
TWIST_BONE_DIFFERENCE       = EXPECTED（MPFB GE rig 无 twist，不单独判 FAIL）
IK_HELPER_BONE_DIFFERENCE   = EXPECTED（MPFB GE rig 无 IK helper，不单独判 FAIL）
```

## B.13 Import Artifact Audit

```
UNEXPECTED_PHYSICS_ASSET = NO
UNEXPECTED_ANIMATION     = NO
UNEXPECTED_MATERIAL      = NO
UNEXPECTED_TEXTURE       = NO
```

目标目录最终仅含 3 个资产（旧 StaticMesh + 新 SKM + 新 SK），无多余产物。

## B.14 FINAL STRUCTURED RESULT（Phase 5C.2b）

```
PHASE5C2B_SKINNED_IMPORT_AUDIT = COMPLETE

NEW_ASSET_TYPE             = SKELETAL_MESH
SKELETON_CREATED           = YES
IMPORTED_SKELETAL_MESH     = /Game/FutsalMOT/Test/FutsalHumanCompatibility/SKM_FutsalHuman_Compatibility_01
IMPORTED_SKELETON          = /Game/FutsalMOT/Test/FutsalHumanCompatibility/SK_FutsalHuman_Compatibility_01

CHARACTER_UPRIGHT          = PASS
UE_CHARACTER_HEIGHT_CM     = 165.94
PHYSICAL_SCALE             = PASS

SKELETON_TOP_LEVEL_BONE    = Human_rig
EXTRA_ARMATURE_ROOT_NODE   = YES
ROOT_HIERARCHY             = FAIL   （顶层为 Human_rig，非 Root；功能性可接受，Retarget 阶段显式映射）

UE_BONE_COUNT              = 54
EXPECTED_BONE_COUNT        = 53
BONE_COUNT_MATCH           = FAIL   （EXTRA_BONES=[Human_rig]，MISSING_BONES=[]）

CORE_BODY_HIERARCHY        = PASS
LEFT_ARM_CHAIN             = PASS
RIGHT_ARM_CHAIN            = PASS
LEFT_LEG_CHAIN             = PASS
RIGHT_LEG_CHAIN            = PASS
FINGER_CHAINS              = PASS

REFERENCE_POSE             = A_POSE
SKIN_BINDING               = PASS
BONE_TRANSFORM_SANITY      = PASS
CORE_RETARGET_CHAIN_MAPPING = READY

IMPORT_COMPATIBILITY       = PASS_FOR_RETARGET_SPIKE
FUTSAL_HUMAN_SKELETON_STANDARD_V1 = NOT_FROZEN
```

## B.15 阻断项 / 非阻断项

- **非阻断（已知差异，Retarget 阶段处理）**：额外根骨 `Human_rig`（+1 骨）；无 twist / IK helper 骨；骨骼主轴为 Y（Blender `Primary Bone Axis = Y` 导出），需在 IK Retargeter 的 Retarget Pose 中做轴向对齐。
- **阻断项**：无。
- **工具注意事项（重要）**：MCP 原生 `SkeletalMeshTools.import_file` 会产出 1/100 缩放；自动化必须改用显式 `FbxImportUI`（Convert Scene / Convert Scene Unit）。

## B.16 Next recommended phase

1. 进入 **Retarget Spike**：基于 `SK_Mannequin`（source）与 `SK_FutsalHuman_Compatibility_01`（target）建立 IKR/RTG，先做 locomotion 语义链映射；决定 `Human_rig` 根是保留（映射 Root→Root）还是在后续标准化 rig 中消除。
2. 在 spike 中验证 A-Pose→A-Pose 对齐、Y 主轴与 Mannequin X 主轴之间的 Retarget Pose 修正、以及缺失 twist/IK 骨对 deformation 的影响。
3. Spike 通过后，才将 `SK_FutsalHuman_Skeleton` 标准化为 V1 并冻结（当前仍为 `NOT_FROZEN`）。

---

# Phase 5C.2c — Root Normalization Spike（消除 Blender Armature Object 额外顶层骨）

- 阶段：Phase 5C.2c（隔离实验，不触碰 Phase 5C.2b 的可用资产）
- 输入 FBX：`D:/projects/FutsalMOT_blender/FutsalHuman_Compatibility_01_GameEngine_ROOTCLEAN_TEST.fbx`（947884 字节，2026-09-22 19:06，UE MD5 `476e7d0739b31f47cd8d2957b2674258`）
- 唯一设计差异：**Blender 导出瞬间**把 Armature Object name / Armature Data name 临时改为 `Armature`；53 根 Bone 与 Root Bone 名 `Root` 完全未改，导出后 Blender 内恢复 `Human.rig`。
- 导入方式：显式 `unreal.FbxImportUI` + `AssetImportTask`（**禁用**会导致 1/100 scale 的 `SkeletalMeshTools.import_file`）。
- 导入设置：`import_mesh=True`、`import_as_skeletal=True`、`skeleton=None`、Animations/Materials/Textures/MorphTargets/Physics 全部关闭、`convert_scene=True`、`convert_scene_unit=True`、`import_uniform_scale=1.0`、`use_t0_as_ref_pose=False`。
- 隔离目录：`/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootCleanTest/`

## C.1 导入资产

| 资产 | 路径 |
|---|---|
| RootClean SkeletalMesh | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootCleanTest/SKM_FutsalHuman_RootClean_01` |
| RootClean Skeleton | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootCleanTest/SKM_FutsalHuman_RootClean_01_Skeleton` |

来源核验：AssetImportData `RelativeFilename = .../FutsalHuman_Compatibility_01_GameEngine_ROOTCLEAN_TEST.fbx`。

## C.2 对照：control（Phase 5C.2b）vs RootClean candidate

| 项 | CONTROL `SKM_FutsalHuman_Compatibility_01` | ROOTCLEAN `SKM_FutsalHuman_RootClean_01` |
|---|---|---|
| Top Bone | `Human_rig` | **`Root`** |
| Pelvis Parent | `Root` | `Root` |
| Bone Count | 54 | **53** |
| Extra Bone | `Human_rig` | **无** |
| 是否存在 `Human_rig`/`Human.rig`/`Armature` 骨 | 有 `Human_rig` | 全部不存在 |
| Height | 165.94 cm | 165.94 cm |
| Reference Pose | A-Pose | A-Pose |
| Core hierarchy | PASS | PASS |
| Skin binding | PASS | PASS |
| MaxBoneInfluences | 6 | 6 |
| 网格 | 14517 v / 26756 tri / 1 LOD / 0 morph | 同左 |
| 单位换算载体的位置 | `Human_rig` 骨 scale=100 | `Root` 骨 scale=100 |

## C.3 STEP 结果

```
NEW_ASSET_TYPE      = SKELETAL_MESH（非 StaticMesh）
PHYSICAL_SCALE      = PASS（165.94 cm）

SKELETON_TOP_LEVEL_BONE = Root
PELVIS_PARENT           = Root
EXTRA_ARMATURE_ROOT_NODE = NO
ROOT_HIERARCHY          = PASS

ROOT_SCALE              = (100, 100, 100)
ROOT_SCALE_SANITY       = REVIEW
  （Root reference transform：translation=(0,0,-0.0563)、rotation=(0,0,0,-1)、scale=(100,100,100)；
    该 100 倍为 meters→cm 单位换算载体，有限、均匀、正缩放；
    绝对尺寸正确：pelvis 87.39 cm、neck 141.36 cm、head 151.46 cm、foot 6.92 cm、ball 0.89 cm）

UE_BONE_COUNT       = 53
BONE_COUNT_MATCH    = PASS
EXTRA_BONES         = []
MISSING_BONES       = []

CORE_BODY_HIERARCHY = PASS
LEFT_ARM_CHAIN      = PASS
RIGHT_ARM_CHAIN     = PASS
LEFT_LEG_CHAIN      = PASS
RIGHT_LEG_CHAIN     = PASS
FINGER_CHAINS       = PASS

REFERENCE_POSE      = A_POSE（手低于肩约 30.46 cm，双手水平跨距约 90.62 cm，远小于身高 166 cm）
SKIN_BINDING        = PASS（网格绑定新 Skeleton；包围盒 0→165.94 cm 非退化；无爆炸/塌陷迹象）
```

- `nonfinite = []`、`zerolen = []`（Root 的 100 倍缩放为唯一非单位缩放）。

## C.4 STEP 9/10 — 结论与策略

```
ROOTCLEAN_IMPROVEMENT = YES
```

严格条件全部满足：Top Bone = `Root`；Bone Count = 53；Height ≈165.94 cm；A-Pose 保持；Skin binding 保持；Core hierarchy 保持。

```
ROOT_NORMALIZATION_STRATEGY = TEMPORARY_BLENDER_ARMATURE_NAME_ARMATURE_DURING_EXPORT
```

**建议**：将「导出瞬间把 Armature Object / Armature Data 临时命名为 `Armature`，导出后恢复 `Human.rig`」写入未来 Blender Exporter（作为 Root 归一化的标准前置步骤）。

**边界（本阶段未做）**：
- 未删除或替换 Phase 5C.2b 的 54-bone `SKM_FutsalHuman_Compatibility_01` / `SK_FutsalHuman_Compatibility_01`；
- 未开始 Retarget；未创建 IK Rig / IK Retargeter / AnimBP；
- 未修改任何 Reference Pose / bone hierarchy。

## C.5 FINAL STRUCTURED RESULT（Phase 5C.2c）

```
PHASE5C2C_ROOT_NORMALIZATION = COMPLETE

ROOTCLEAN_SKELETAL_MESH = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RootCleanTest/SKM_FutsalHuman_RootClean_01
ROOTCLEAN_SKELETON      = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RootCleanTest/SKM_FutsalHuman_RootClean_01_Skeleton

CHARACTER_HEIGHT_CM     = 165.94
PHYSICAL_SCALE          = PASS

SKELETON_TOP_LEVEL_BONE = Root
PELVIS_PARENT           = Root
UE_BONE_COUNT           = 53
EXPECTED_BONE_COUNT     = 53
EXTRA_ARMATURE_ROOT_NODE = NO
ROOT_HIERARCHY          = PASS

ROOT_SCALE              = (100,100,100)
ROOT_SCALE_SANITY       = REVIEW
BONE_COUNT_MATCH        = PASS
CORE_BODY_HIERARCHY     = PASS

REFERENCE_POSE          = A_POSE
SKIN_BINDING            = PASS

ROOTCLEAN_IMPROVEMENT   = YES
ROOT_NORMALIZATION_STRATEGY = TEMPORARY_BLENDER_ARMATURE_NAME_ARMATURE_DURING_EXPORT

FUTSAL_HUMAN_SKELETON_STANDARD_V1 = NOT_FROZEN
```

---

# Phase 5C.2d — Root Scale Normalization Spike

- 阶段：Phase 5C.2d（隔离实验，冻结 `FUTSAL_HUMAN_SKELETON_STANDARD_V1` 前最后一个 FBX Skeleton Contract 测试）
- 输入 FBX：`D:/projects/FutsalMOT_blender/FutsalHuman_Compatibility_01_GameEngine_ROOTCLEAN_CMSCALE_TEST.fbx`（949532 字节，2026-09-22 19:11，UE MD5 `789857e37cce0569176c1b236898bfa6`）
- 与 Phase 5C.2c 的唯一差异：临时导出副本被转换到 **centimeter workspace**；Bone hierarchy 未改；Armature Object 名仍为 `Armature`；源 Blender Human / Human.rig 未改。
- 导入方式：显式 `unreal.FbxImportUI` + `AssetImportTask`（禁用 `SkeletalMeshTools.import_file`）；`convert_scene=True`、`convert_scene_unit=True`、`import_uniform_scale=1.0`、无 Animations/Materials/Textures/MorphTargets/Physics、`use_t0_as_ref_pose=False`。
- 隔离目录：`/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/`

## D.1 导入资产

| 资产 | 路径 |
|---|---|
| CM-normalized SkeletalMesh | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01` |
| CM-normalized Skeleton | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01_Skeleton` |

来源核验：AssetImportData `RelativeFilename = .../FutsalHuman_Compatibility_01_GameEngine_ROOTCLEAN_CMSCALE_TEST.fbx`。

## D.2 对照：CONTROL(RootClean) vs CM_NORMALIZED

| 项 | CONTROL `SKM_FutsalHuman_RootClean_01` | CM_NORMALIZED `SKM_FutsalHuman_CMScaled_01` |
|---|---|---|
| Top Bone | `Root` | `Root` |
| Pelvis Parent | `Root` | `Root` |
| Bone Count | 53 | 53 |
| 额外 armature 骨 | 无 | 无 |
| Height | 165.94 cm | 165.94 cm |
| **Root Scale** | **(100,100,100)** | **(1,1,1)** |
| 参考姿势骨坐标 | pelvis 约 0.874（m，靠 root×100 换算） | pelvis 约 87.39（cm，root×1） |
| Reference Pose | A-Pose | A-Pose |
| Skin binding | PASS | PASS |
| Core hierarchy | PASS | PASS |
| MaxBoneInfluences | 6 | 6 |

## D.3 STEP 结果

```
NEW_ASSET_TYPE = SKELETAL_MESH（非 StaticMesh）
CHARACTER_HEIGHT_CM = 165.94
PHYSICAL_SCALE = PASS

SKELETON_TOP_LEVEL_BONE = Root
PELVIS_PARENT           = Root
UE_BONE_COUNT           = 53
EXTRA_ARMATURE_ROOT_NODE = NO
ROOT_HIERARCHY          = PASS
BONE_COUNT_MATCH        = PASS

ROOT_TRANSLATION = (0, 0, -0.0563)
ROOT_ROTATION    = (0, 0, 0, -1)   （等价于单位旋转）
ROOT_SCALE       = (1, 1, 1)
ROOT_SCALE_SANITY = PASS

CHILD_BONE_SCALE_SANITY = PASS
  （pelvis / spine_01..03 / upperarm_l|r / lowerarm_l|r / hand_l|r /
    thigh_l|r / calf_l|r / foot_l|r / ball_l|r 的参考姿势局部缩放均为 (1,1,1)）

CORE_BODY_HIERARCHY = PASS
LEFT_ARM_CHAIN      = PASS
RIGHT_ARM_CHAIN     = PASS
LEFT_LEG_CHAIN      = PASS
RIGHT_LEG_CHAIN     = PASS
FINGER_CHAINS       = PASS

REFERENCE_POSE = A_POSE（手低于肩约 30.46 cm，双手水平跨距约 90.62 cm；head Z≈151.46 cm）
SKIN_BINDING   = PASS（绑定新 Skeleton；包围盒 0→165.94 cm 非退化；无爆炸/塌陷）
```

- `nonfinite = []`、`badscale = []`、`zerolen = []`——**全骨架已无任何非单位缩放**。
- 绝对骨位与 control 完全一致（pelvis 87.39 cm、neck 141.36 cm、head 151.46 cm、foot 6.92 cm、ball 0.89 cm），说明只是把「单位换算」从 root×100 前移进了骨坐标，姿势与几何不变。

## D.4 STEP 10/11 — 结论与契约

```
ROOT_SCALE_NORMALIZATION_IMPROVEMENT = YES
```

严格条件全部满足：Height≈165.94 cm；Top=`Root`；Bones=53；Root Scale≈1；A-Pose 保持；Skin 保持；Hierarchy 保持。

推荐冻结以下契约（仅建议，本阶段未写入代码/配置）：

```
FUTSAL_BLENDER_AUTHORING_UNITS  = METRIC_1_METER
FUTSAL_EXPORT_NORMALIZATION     = TEMP_DUPLICATE_TO_CENTIMETER_WORKSPACE
FUTSAL_EXPORT_SCENE_SCALE_LENGTH = 0.01
FUTSAL_EXPORT_ARMATURE_OBJECT_NAME = Armature
FUTSAL_UE_IMPORT                = EXPLICIT_FBX_IMPORT_UI_WITH_SCENE_CONVERSION
```

> `FUTSAL_HUMAN_SKELETON_STANDARD_V1` 仍为 **NOT_FROZEN**，直到 Retarget Spike 通过。

## D.5 FINAL STRUCTURED RESULT（Phase 5C.2d）

```
PHASE5C2D_ROOT_SCALE_NORMALIZATION = COMPLETE

CANDIDATE_SKELETAL_MESH = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01
CANDIDATE_SKELETON      = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01_Skeleton

CHARACTER_HEIGHT_CM = 165.94
PHYSICAL_SCALE      = PASS

SKELETON_TOP_LEVEL_BONE = Root
PELVIS_PARENT           = Root
UE_BONE_COUNT           = 53
BONE_COUNT_MATCH        = PASS

ROOT_TRANSLATION = (0, 0, -0.0563)
ROOT_ROTATION    = (0, 0, 0, -1)
ROOT_SCALE       = (1, 1, 1)
ROOT_SCALE_SANITY = PASS
CHILD_BONE_SCALE_SANITY = PASS

CORE_BODY_HIERARCHY = PASS
REFERENCE_POSE      = A_POSE
SKIN_BINDING        = PASS

ROOT_SCALE_NORMALIZATION_IMPROVEMENT = YES

FUTSAL_HUMAN_SKELETON_STANDARD_V1 = NOT_FROZEN
```

---

# Phase 5C.3 — Retarget Compatibility Spike

- 阶段：Phase 5C.3（SK_Mannequin → FutsalHuman Retarget 兼容性 spike；隔离目录 `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RetargetSpike/`）
- 目的：验证 Root + Scale 归一化后的 FutsalHuman Skeleton 可作为未来所有 MPFB/Blender 球员共享的 Target Skeleton。
- 已冻结导入契约（本阶段不再修改，视为已验证基线）：`FUTSAL_BLENDER_AUTHORING_UNITS=METRIC_1_METER`、`FUTSAL_EXPORT_NORMALIZATION=TEMP_DUPLICATE_TO_CENTIMETER_WORKSPACE`、`FUTSAL_EXPORT_SCENE_SCALE_LENGTH=0.01`、`FUTSAL_EXPORT_ARMATURE_OBJECT_NAME=Armature`、`FUTSAL_UE_IMPORT=EXPLICIT_FBX_IMPORT_UI_WITH_SCENE_CONVERSION`。

## E.1 Skeleton / IK Rig / Retargeter 资产

| 角色 | 资产 | 路径 |
|---|---|---|
| Source Skeleton | `SK_Mannequin`（161 骨） | `/Game/Characters/Mannequins/Meshes/SK_Mannequin` |
| Target Skeleton | `SKM_FutsalHuman_CMScaled_01_Skeleton`（53 骨） | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01_Skeleton` |
| Source IK Rig | `IKR_Quinn`（**复用，未编辑**） | `/Game/FutsalMOT/Animation/Retarget/IKR_Quinn` |
| Target IK Rig | `IKR_FutsalHuman_Compatibility`（新建） | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RetargetSpike/IKR_FutsalHuman_Compatibility` |
| IK Retargeter | `RTG_Mannequin_To_FutsalHuman_Compatibility`（新建） | `/Game/FutsalMOT/Test/FutsalHumanCompatibility/RetargetSpike/RTG_Mannequin_To_FutsalHuman_Compatibility` |

- `REUSE_EXISTING_SOURCE_IKRIG = YES`：`IKR_Quinn` preview mesh = `SKM_Quinn_Simple`（骨架 `SK_Mannequin`），retarget root = `pelvis`，链与源骨架一致 → 直接复用，未修改。
- 说明：Phase 5C.2c/2d 已确认目标骨架 Top=`Root`/53 骨/`Root Scale=(1,1,1)`/A-Pose/蒙皮 PASS。

## E.2 实际链定义（STEP 5/6/7）

Source（IKR_Quinn 实测）：

```
Spine  spine_01 → spine_05
Neck   neck_01  → neck_02
Head   head     → head
LeftArm  upperarm_l → hand_l      RightArm upperarm_r → hand_r
LeftLeg  thigh_l → foot_l         RightLeg thigh_r → foot_r
LeftFoot ball_l → ball_l          RightFoot ball_r → ball_r
Left/RightClavicle clavicle_* → clavicle_*
（另含左右各 5 指 + 4 metacarpal 链）
```

Target（IKR_FutsalHuman_Compatibility 实测）：

```
Root   Root    → Root
Spine  spine_01 → spine_03
Neck   neck_01  → neck_01
Head   head     → head
LeftArm  upperarm_l → hand_l      RightArm upperarm_r → hand_r
LeftLeg  thigh_l → ball_l         RightLeg thigh_r → ball_r
LeftClavicle clavicle_l → clavicle_l   RightClavicle clavicle_r → clavicle_r
```

Retarget Root：Source = `pelvis`，Target = `pelvis`（默认工具栏语义；未使用 `Root`）。

链映射（RTG 实测 `get_source_chain`）：

```
Spine→Spine  Neck→Neck  Head→Head
LeftArm→LeftArm  RightArm→RightArm
LeftLeg→LeftLeg  RightLeg→RightLeg
LeftClavicle→LeftClavicle  RightClavicle→RightClavicle
Root→(None)   # 源 IKR_Quinn 无 Root 链，故 Root 未映射（in-place 动画无影响）
```

已知结构性差异（预期，不判 FAIL）：源 spine 5 节 vs 目标 3 节（按语义映射，不截断源）；源 neck 2 节 vs 目标 1 节；源 Additional twist/corrective/ik_hand_*/ik_foot_* 骨在目标不存在。

## E.3 Reference / Retarget Pose（STEP 8）

- Source `SK_Mannequin` 参考姿势：**A_POSE**（手低于肩约 39.12 cm，双手水平跨距约 95.54 cm）。
- Target `SKM_FutsalHuman_CMScaled_01` 参考姿势：**A_POSE**（手低于肩约 30.46 cm，跨距约 90.62 cm）。
- 两者同为 A-Pose，方向一致，默认对齐即足够；`RETARGET_POSE_ADJUSTMENT = NONE`（未对 IK Retargeter Retarget Pose 做任何手动修正，未写入 Skeleton）。

## E.4 测试动画集（STEP 9/11）

由 `ABP_FutsalSource` / `BS_Futsal_Locomotion` 的实际依赖读取，选取最小代表性集合，批量 retarget 到 `RetargetSpike/Animations/`（前缀 `RTG_`，未覆盖源动画）：

| 类别 | 源动画 | 生成资产 |
|---|---|---|
| Idle | `MM_Idle` | `RTG_MM_Idle` |
| Forward locomotion | `MF_Unarmed_Jog_Fwd` | `RTG_MF_Unarmed_Jog_Fwd` |
| Jump | `MM_Jump` | `RTG_MM_Jump` |
| Fall | `MM_Fall_Loop` | `RTG_MM_Fall_Loop` |
| Land | `MM_Land` | `RTG_MM_Land` |
| Lateral locomotion | `MF_Unarmed_Jog_Left` | `RTG_MF_Unarmed_Jog_Left` |

全部生成资产的 `skeleton` 均指向 `SKM_FutsalHuman_CMScaled_01_Skeleton`（STEP 12：无错误骨架引用）。30 fps；长度分别为 227 / 53 / 26 / 90 / 26 / 46 帧。

## E.5 数值验证结果（STEP 10/12/16/17）

对每个 clip 采样 4 帧（0 / 1/3 / 2/3 / 末帧），按骨骼层级合成绝对变换：

- `root_scale = 1.0`（所有 clip、所有帧），`max_scale_dev = 0.0`，无 NaN → **无 100x 缩放、无缩放跳变**。
- 无骨骼爆炸/塌陷：pelvis 高度稳定（Idle 约 87 cm；Jog 约 78–80 cm；Jump 62→105→92→88 cm；Land 68→85 cm；Fall 约 87–88 cm）。
- 根平移：Idle/Jump/Fall/Land 为 in-place（`(0,0,0)`）；Jog_Fwd 沿 +Y 累积位移（0→920 cm / 1.77 s），Jog_Left 沿 +X 累积（0→797 cm / 1.53 s）→ 属**合法 root motion**，非爆炸。
- 前向轴：前向 Jog 位移（+Y）与侧向 Jog 位移（+X）正交；源与目标的 toe（ball−foot）方向同为 +Y → 前向源动画 → 前向目标动画一致。

```
RETARGET_ROOT_SCALE_SANITY        = PASS
RETARGET_ROOT_TRANSLATION_SANITY  = PASS
FORWARD_AXIS_RETARGET             = PASS
RETARGET_PREVIEW_BASIC            = PASS（数值：无爆炸 / 无 180° 数值异常 / 无缩放跳变 / 无 NaN）
```

> **限制声明（重要）**：本阶段由自动化 Agent 执行，**不具备视觉评审能力**。以上为数值/结构性验证；STEP 13 的形变质量（美观、局部塌陷）与 STEP 10 的纯视觉预览**尚未由人工确认**，相关项按下表标记为 `REVIEW`。

## E.6 形变 / twist / IK helper（STEP 13/14/15）

| 部位 | 结果 | 说明 |
|---|---|---|
| Shoulder | REVIEW | 数值无塌陷；视觉待人工确认 |
| Elbow | REVIEW | 数值无异常；视觉待人工确认 |
| Wrist | REVIEW | 数值无异常；视觉待人工确认 |
| Spine | REVIEW | pelvis/head 高度与姿态合理；视觉待人工确认 |
| Hip | REVIEW | 数值无异常 |
| Knee | REVIEW | 腿部循环无 NaN/翻转数值迹象 |
| Ankle/Foot | REVIEW | feet 接近地面（偶有 <3 cm 轻微穿地，与源同级） |

```
TWIST_BONE_ABSENCE_IMPACT = LOW
IK_HELPER_ABSENCE_IMPACT  = NONE
```

- Twist：源 twist/corrective 骨未被 FK 链映射（IKR_Quinn 的 Arm 链止于 `hand_l`/`lowerarm_l`），目标无 twist 骨；数值上无 roll 塌陷或缩放异常 → 影响判 LOW（locomotion spike）。**未添加 twist 骨**。
- IK helper：目标无 `ik_hand_*`/`ik_foot_*`；basic locomotion retarget 不依赖它们（FK 链重定向）→ 影响 NONE。**未添加 IK helper 骨**。

## E.7 Skeleton V1 判定（STEP 18/19）

结构/功能条件全部满足：Top=`Root`、BoneCount=53、RootScale=1、Reference Pose 已理解、Skin 有效、Retarget Preview 非灾难、Idle/Forward/Jump-Fall-Land 生成成功、Root 变换正常、twist/IK 缺失非 BLOCKER。

```
FUTSAL_HUMAN_SKELETON_STANDARD_V1 = READY_TO_FREEZE（结构/功能就绪）
```

> 注意：**本阶段未实际冻结/重命名/迁移任何生产资产**。且 STEP 13 形变视觉项为 `REVIEW`——**建议在执行真正冻结前补一次人工视觉验收**。

生产架构建议（**仅提议，未执行**）：

```
SK_Mannequin
  ↓ Source animations / ABP_FutsalSource
RTG_Mannequin_To_FutsalHuman
  ↓
SK_FutsalHuman
  ↓
ABP_FutsalHuman
  ↓
Player_001 / Player_002 / ...
```

拟议命名：`SK_FutsalHuman`、`IKR_FutsalHuman`、`RTG_Mannequin_To_FutsalHuman`、`ABP_FutsalHuman`（**均未创建**）。

## E.8 FINAL STRUCTURED RESULT（Phase 5C.3）

```
PHASE5C3_RETARGET_SPIKE = PARTIAL（资产与数值验证完成；形变视觉评审待人工）

SOURCE_SKELETON = /Game/Characters/Mannequins/Meshes/SK_Mannequin
TARGET_SKELETON = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RootScaleTest/SKM_FutsalHuman_CMScaled_01_Skeleton

SOURCE_IKRIG = /Game/FutsalMOT/Animation/Retarget/IKR_Quinn（复用）
TARGET_IKRIG = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RetargetSpike/IKR_FutsalHuman_Compatibility
IK_RETARGETER = /Game/FutsalMOT/Test/FutsalHumanCompatibility/RetargetSpike/RTG_Mannequin_To_FutsalHuman_Compatibility

SOURCE_RETARGET_ROOT = pelvis
TARGET_RETARGET_ROOT = pelvis

SOURCE_REFERENCE_POSE = A_POSE
TARGET_REFERENCE_POSE = A_POSE
RETARGET_POSE_ADJUSTMENT = NONE

ROOT_CHAIN       = PASS（目标 Root 链已建；源无 Root 链，未映射，in-place 无影响）
SPINE_CHAIN      = PASS
NECK_HEAD_CHAIN  = PASS
LEFT_ARM_CHAIN   = PASS
RIGHT_ARM_CHAIN  = PASS
LEFT_LEG_CHAIN   = PASS
RIGHT_LEG_CHAIN  = PASS

RETARGET_PREVIEW_BASIC = PASS（数值）
IDLE_RETARGET          = PASS
LOCOMOTION_RETARGET    = PASS
JUMP_RETARGET          = PASS

SHOULDER_DEFORMATION = REVIEW
ELBOW_DEFORMATION    = REVIEW
WRIST_DEFORMATION    = REVIEW
SPINE_DEFORMATION    = REVIEW
HIP_DEFORMATION      = REVIEW
KNEE_DEFORMATION     = REVIEW
ANKLE_FOOT_DEFORMATION = REVIEW

TWIST_BONE_ABSENCE_IMPACT = LOW
IK_HELPER_ABSENCE_IMPACT  = NONE

RETARGET_ROOT_SCALE_SANITY       = PASS
RETARGET_ROOT_TRANSLATION_SANITY = PASS
FORWARD_AXIS_RETARGET            = PASS

FUTSAL_HUMAN_SKELETON_STANDARD_V1 = READY_TO_FREEZE（结构/功能就绪；视觉形变为 REVIEW）
```

---

# Phase 5C.3 — Human Visual Sign-Off

- 时间：2026-09-22
- 由人工完成 Phase 5C.3 的视觉形变评审（自动化 Agent 无视觉能力，此处由人工补签）。

```
VISUAL_RETARGET_SIGNOFF = PASS

Idle      = PASS   (RTG_MM_Idle)
Jog_Fwd   = PASS   (RTG_MF_Unarmed_Jog_Fwd)
Jog_Left  = PASS   (RTG_MF_Unarmed_Jog_Left)
Jump      = PASS   (RTG_MM_Jump)
Fall      = PASS   (RTG_MM_Fall_Loop)
Land      = PASS   (RTG_MM_Land)

Shoulder   = PASS
Elbow      = PASS
Wrist      = PASS
Spine      = PASS
Hip        = PASS
Knee       = PASS
Ankle_Foot = PASS

TWIST_BONE_ABSENCE_IMPACT = LOW
IK_HELPER_ABSENCE_IMPACT  = NONE

PHASE5C3_RETARGET_SPIKE = COMPLETE

FUTSAL_HUMAN_SKELETON_STANDARD_V1 = APPROVED_FOR_FREEZE
```

> 历史审计结果（Phase 5C.2 的 BLOCKED、5C.3 的 REVIEW）保留不改写；本节仅追加人工签核结论。

---

# Phase 5C.4 — FutsalHuman Skeleton Standard V1 Freeze

- 阶段：Phase 5C.4（将已验证兼容性设计提升为生产规范资产；**未**创建 ABP_FutsalHuman，**未**迁移 BP_FutsalCharacterBase，**未**批量导入人物，**未**删除测试资产）
- 前置结论（人工视觉已通过）：`PHASE5C3_RETARGET_SPIKE = COMPLETE`、`STRUCTURAL/FUNCTIONAL/VISUAL = PASS`、`FUTSAL_HUMAN_SKELETON_STANDARD_V1 = APPROVED_FOR_FREEZE`

## F.1 生产规范资产

| 资产 | 路径 |
|---|---|
| Canonical SkeletalMesh | `/Game/FutsalMOT/Characters/FutsalHuman/Meshes/SKM_FutsalHuman_Base` |
| Canonical Skeleton | `/Game/FutsalMOT/Characters/FutsalHuman/Skeleton/SK_FutsalHuman` |
| Canonical Target IK Rig | `/Game/FutsalMOT/Animation/Retarget/IKR_FutsalHuman` |
| Canonical IK Retargeter | `/Game/FutsalMOT/Animation/Retarget/RTG_Mannequin_To_FutsalHuman` |
| Source IK Rig（复用，未修改） | `/Game/FutsalMOT/Animation/Retarget/IKR_Quinn` |
| Source Skeleton | `/Game/Characters/Mannequins/Meshes/SK_Mannequin` |

- STEP 2 冲突检查：`/Game/FutsalMOT/Characters/FutsalHuman/**` 原为空；`IKR_FutsalHuman`/`RTG_Mannequin_To_FutsalHuman` 原不存在 → 无冲突（同目录既有 `IKR_Quinn`/`IKR_SoccerPlayer`/`RTG_Quinn_To_SoccerPlayer` 未触碰）。
- STEP 3：从已验证 CM-normalized FBX（`FutsalHuman_Compatibility_01_GameEngine_ROOTCLEAN_CMSCALE_TEST.fbx`）用显式 `FbxImportUI` 全新导入；UE 自动骨架名 `SKM_FutsalHuman_Base_Skeleton` 被**重命名/移动**为 `SK_FutsalHuman`（仅改资产名，未改层级/参考姿势）。

## F.2 冻结契约（FROZEN）

```
FUTSAL_HUMAN_SKELETON_STANDARD_V1 = FROZEN

TOP_BONE            = Root
PELVIS_PARENT       = Root
BONE_COUNT          = 53
RETARGET_ROOT       = pelvis
REFERENCE_POSE      = A_POSE
ROOT_SCALE          = (1,1,1)
CHILD_BONE_SCALES   = (1,1,1)
CHARACTER_HEIGHT_CM = 165.94
TWIST_BONES         = NOT_PRESENT
IK_HELPER_BONES     = NOT_PRESENT
```

- 验证结果：`top_level=[Root]`；无 `Human_rig`/`Human.rig`/`Armature`；`nonfinite=[]`、`badscale=[]`、`zerolen=[]`；`hierarchy_mismatch=[]`；A-Pose（手低于肩 30.46 cm，跨距 90.62 cm）；skin binding PASS。
- 核心层级与骨骼名在 V1 内视为**不可变**；任何未来结构改动需走 `FUTSAL_HUMAN_SKELETON_STANDARD_V2`，不得静默变异 V1。

## F.3 规范 Retarget 契约

- Target IK Rig `IKR_FutsalHuman`：preview mesh = `SKM_FutsalHuman_Base`，retarget root = `pelvis`。
- 规范链定义（实测）：

```
Root   Root→Root        Spine  spine_01→spine_03   Neck  neck_01→neck_01   Head  head→head
LeftArm  upperarm_l→hand_l      RightArm upperarm_r→hand_r
LeftLeg  thigh_l→ball_l         RightLeg thigh_r→ball_r
LeftClavicle clavicle_l→clavicle_l   RightClavicle clavicle_r→clavicle_r
```

- `RTG_Mannequin_To_FutsalHuman`：Source=`IKR_Quinn`，Target=`IKR_FutsalHuman`；Retarget Root Source/Target 均 `pelvis`。
- 映射（实测 `get_source_chain`）：`Spine→Spine`、`Neck→Neck`、`Head→Head`、`LeftArm→LeftArm`、`RightArm→RightArm`、`LeftLeg→LeftLeg`、`RightLeg→RightLeg`、`LeftClavicle→LeftClavicle`、`RightClavicle→RightClavicle`；`Root→(None)`（`IKR_Quinn` 无 Root 链，in-place 无影响）。
- Retarget Pose = 默认/NONE（源与目标均 A-Pose，未引入偏移）。

## F.4 生产 Retarget 回归（STEP 7）

用规范 Retargeter 对 6 个动画做回归，仅导出到测试目录 `/Game/FutsalMOT/Test/FutsalHumanCompatibility/FreezeRegression/`（`FRZ_*`），未污染生产目录、未批量重定向：

| Clip | 骨架引用 | Root Scale | 根平移（末帧） | 与 5C.3 对比 |
|---|---|---|---|---|
| FRZ_MM_Idle | SK_FutsalHuman | 1.0 | (0,0,0) | 一致 |
| FRZ_MF_Unarmed_Jog_Fwd | SK_FutsalHuman | 1.0 | (0,919.78,0) | 一致 |
| FRZ_MF_Unarmed_Jog_Left | SK_FutsalHuman | 1.0 | (796.91,0,0) | 一致 |
| FRZ_MM_Jump | SK_FutsalHuman | 1.0 | (0,0,0) | 一致 |
| FRZ_MM_Fall_Loop | SK_FutsalHuman | 1.0 | (0,0,0) | 一致 |
| FRZ_MM_Land | SK_FutsalHuman | 1.0 | (0,0,0) | 一致 |

- 全部帧：`finite=true`、`max_scale_dev=0.0`；无 NaN、无爆炸；前向(+Y)/侧向(+X) 与 5C.3 数值完全一致。
- `CANONICAL_RETARGET_REGRESSION = PASS`。

## F.5 生产资产引用审计（STEP 11）

```
SKM_FutsalHuman_Base     → SK_FutsalHuman（+ 引擎默认材质）
SK_FutsalHuman           → SKM_FutsalHuman_Base
IKR_FutsalHuman          → SKM_FutsalHuman_Base
RTG_Mannequin_To_FutsalHuman → SKM_Quinn_Simple, IKR_Quinn, SKM_FutsalHuman_Base, IKR_FutsalHuman
```

- 生产资产**未**引用 `RootScaleTest` / `RootCleanTest` / `FutsalHuman_Compatibility_01` / 54-bone 兼容 Skeleton → `PRODUCTION_ASSET_REFERENCE_AUDIT = PASS`。
- 测试资产（geometry-only sample、54-bone sample、RootClean、RootScale100、CM-normalized、RetargetSpike、FreezeRegression）**按 STEP 12 全部保留**，留作溯源；后续专门阶段再清理。

## F.6 规范契约（Blender 导出 / UE 导入）

```
FUTSAL_BLENDER_AUTHORING_UNITS   = METRIC_1_METER
FUTSAL_EXPORT_NORMALIZATION      = TEMP_DUPLICATE_TO_CENTIMETER_WORKSPACE
FUTSAL_EXPORT_SCENE_SCALE_LENGTH = 0.01
FUTSAL_EXPORT_ARMATURE_OBJECT_NAME = Armature
FUTSAL_UE_IMPORT                 = EXPLICIT_FBX_IMPORT_UI_WITH_SCENE_CONVERSION
  （convert_scene=True, convert_scene_unit=True, import_uniform_scale=1.0；
    禁止使用 SkeletalMeshTools.import_file —— 实测其产生 1/100 scale）
```

## F.7 未来球员兼容契约（STEP 9）

每个未来的 MPFB / Blender 球员**必须**：

1. 使用同一套 53 骨 FutsalHuman 层级；
2. 保持完全一致的骨骼名与父子层级；
3. 保持 A-Pose Rest Pose；
4. 保持 `Root Scale = 1`；
5. 保持 centimeter-normalized 导出；
6. 导出时 Armature Object 名临时为 `Armature`；
7. 使用显式 `FbxImportUI`（开启 scene conversion）导入；
8. 绑定到 / 复用 `SK_FutsalHuman`。

未来球员**禁止**：为每个球员新建 Skeleton、新建 IK Rig、新建 Retargeter。网格拓扑/体型比例可不同，只要规范骨架契约保持兼容。

## F.8 FINAL STRUCTURED RESULT（Phase 5C.4）

```
PHASE5C4_SKELETON_V1_FREEZE = COMPLETE
HUMAN_VISUAL_SIGNOFF = PASS

CANONICAL_SKELETAL_MESH = /Game/FutsalMOT/Characters/FutsalHuman/Meshes/SKM_FutsalHuman_Base
CANONICAL_SKELETON      = /Game/FutsalMOT/Characters/FutsalHuman/Skeleton/SK_FutsalHuman
CANONICAL_TARGET_IKRIG  = /Game/FutsalMOT/Animation/Retarget/IKR_FutsalHuman
CANONICAL_RETARGETER    = /Game/FutsalMOT/Animation/Retarget/RTG_Mannequin_To_FutsalHuman
SOURCE_IKRIG            = /Game/FutsalMOT/Animation/Retarget/IKR_Quinn

CHARACTER_HEIGHT_CM     = 165.94
SKELETON_TOP_LEVEL_BONE = Root
PELVIS_PARENT           = Root
BONE_COUNT              = 53
ROOT_SCALE              = (1,1,1)
REFERENCE_POSE          = A_POSE
RETARGET_ROOT           = pelvis
TWIST_BONES             = NOT_PRESENT
IK_HELPER_BONES         = NOT_PRESENT

CANONICAL_SKELETON_VALIDATION    = PASS
CANONICAL_RETARGET_REGRESSION    = PASS
PRODUCTION_ASSET_REFERENCE_AUDIT = PASS

FUTSAL_HUMAN_SKELETON_STANDARD_V1 = FROZEN

NEXT_PHASE = PHASE_5C5_ABP_FUTSALHUMAN   （本阶段未创建 ABP_FutsalHuman）
```

> 说明：`Docs/Architecture/FUTSAL_CHARACTER_APPEARANCE_MODEL_PIPELINE.md` **不存在**，按 STEP 10 的约束**未创建**该文件。

---

# Phase 5C.5 — Build Canonical ABP_FutsalHuman

- 阶段：Phase 5C.5（审计 ABP_FutsalSource 运行时依赖 → 离线重定向所需动画 → 构建共享 ABP_FutsalHuman → 验证编译与引用）
- 结论摘要：**动画重定向与 BlendSpace 全部 PASS；ABP_FutsalHuman 已创建、目标骨架正确、图结构等价、可编译**；但 **未通过 STEP 13（源引用清零）与 STEP 14（无骨架不匹配告警）两道关卡** → 本阶段 **BLOCKED**。
- 未修改：`SK_Mannequin` / `IKR_Quinn` / `RTG_Mannequin_To_FutsalHuman` / `IKR_FutsalHuman` / `SK_FutsalHuman` / `SKM_FutsalHuman_Base` / `ABP_FutsalSource` / `BP_FutsalCharacterBase` / `L_FutsalCourt` / `UNREAL_RIG.uasset`。

## G.1 STEP 1–3 — ABP_FutsalSource 审计

```
SOURCE_ABP            = /Game/FutsalMOT/Animation/Source/ABP_FutsalSource
SOURCE_ABP_SKELETON   = /Game/Characters/Mannequins/Meshes/SK_Mannequin
SOURCE_ABP_PARENT_CLASS = /Script/Engine.AnimInstance
SOURCE_STATE_MACHINES = 2 个（AnimGraphNode_StateMachine），StateResult×6，TransitionResult×8
ANIM_GRAPH_NODES      = 26（Root1 / StateMachine2 / SaveCachedPose1 / Slot1(DefaultSlot) /
                         ControlRig1 / StateResult6 / SequencePlayer4 / BlendSpacePlayer1 /
                         TransitionResult8 / UseCachedPose1）
```

运行时动画依赖闭包（A. DIRECT / B. INDIRECT）：

- DIRECT（SequencePlayer×4）：`MM_Idle`、`MM_Jump`、`MM_Fall_Loop`、`MM_Land`
- INDIRECT（BlendSpacePlayer×1 → `BS_Futsal_Locomotion`）：`BS_Futsal_Locomotion` 采样 27 个 sample，覆盖 17 个唯一序列（MM_Idle + 8 Walk + 8 Jog）
- 另含运行时 **ControlRig 节点**：`CR_Mannequin_FootIK`（源骨架专用）

```
SOURCE_RUNTIME_ANIMATION_DEPENDENCY_COUNT = 20（17 BlendSpace 唯一序列 + Idle/Jump/Fall/Land 去重后共 20 个唯一 Sequence）
                                            + 1 BlendSpace
```

`BS_Futsal_Locomotion` 采样矩阵（轴：Direction −180..180 grid8；Speed 0..600 grid4；第三轴 None 未用）：

- Speed 0：`MM_Idle` @ x∈{0,±45,±90,±135,180}（9）
- Speed 300：`MF_Unarmed_Walk_{Fwd,Fwd_Left,Fwd_Right,Bwd,Bwd_Left,Bwd_Right,Left,Right}`（9）
- Speed 600：`MF_Unarmed_Jog_{Fwd,Fwd_Left,Fwd_Right,Bwd,Bwd_Left,Bwd_Right,Left,Right}`（9）

## G.2 STEP 4–8 — 生产动画库

目录：`/Game/FutsalMOT/Animation/FutsalHuman/`

- `Locomotion/Sequences/`：17 个 `FH_MM_Idle` / `FH_MF_Unarmed_{Walk,Jog}_*`（由规范 `RTG_Mannequin_To_FutsalHuman` 批量重定向）
- `Actions/Jump/`：`FH_MM_Jump` / `FH_MM_Fall_Loop` / `FH_MM_Land`
- `Locomotion/BlendSpaces/BS_FutsalHuman_Locomotion`

验证（STEP 7，**20/20 PASS**）：每个目标序列 skeleton=`SK_FutsalHuman`、时长与源完全一致、`root_scale=1.0`、变换有限、无 NaN。

BlendSpace（STEP 8，PASS）：`skeleton=SK_FutsalHuman`、27 samples、axis 名/范围/格数与源一致、全部 sample 指向 `FH_*`。

> 工具注意：BlendSpace 无法通过复制后改 skeleton（`Skeleton` 属性不可编辑）；必须用 `BlendSpaceFactoryNew(target_skeleton=...)` 新建，再回写 `blend_parameters` / `sample_data`（整数组回写才持久）。

## G.3 STEP 10–12 — ABP_FutsalHuman

```
TARGET_ABP = /Game/FutsalMOT/Animation/FutsalHuman/ABP/ABP_FutsalHuman
TARGET_SKELETON  = /Game/FutsalMOT/Characters/FutsalHuman/Skeleton/SK_FutsalHuman   ✅
```

- 由图结构复制得到（`duplicate_asset` → 改 `target_skeleton` → 替换 4 个 SequencePlayer 的 `sequence` 为 `FH_*`、1 个 BlendSpacePlayer 的 `blend_space` 为 `BS_FutsalHuman_Locomotion`）。
- **图结构等价（STEP 12）= PASS**：源/目标 26 个动画节点类型与数量完全一致（含 2 StateMachine / 6 StateResult / 8 TransitionResult / 1 Slot `DefaultSlot` / 1 ControlRig）。
- 注意：AnimationBlueprint 的 AnimGraphNode **state 名称 / 过渡规则 / 变量**在 UE5.8 Python 中未暴露只读接口，无法逐项文本比对；等价性以「逐节点复制 + 结构计数一致」判定。

## G.4 STEP 13/14 — 未通过的关卡（BLOCKER）

**STEP 13（源引用清零）FAIL。** `ABP_FutsalHuman` 的硬依赖仍包含：

```
源动画（SK_Mannequin）：MM_Idle, MM_Jump, MM_Fall_Loop, MM_Land   → 4
源 BlendSpace：BS_Futsal_Locomotion                              → 1
源骨头：SK_Mannequin
源 ControlRig：CR_Mannequin_FootIK                               → 1
```

```
SOURCE_ANIMATION_RUNTIME_REFERENCES = 5   （要求 0）
TEST_ASSET_RUNTIME_REFERENCES       = 0   （PASS：无 RetargetSpike/FreezeRegression/RootScaleTest 引用）
```

**根因（已定位）**：通过 `duplicate_asset` 复制 ABP 后，即使用 Python 把每个 `AnimGraphNode_*` 的 `node.sequence`/`node.blend_space` 改成 `FH_*`（读回确认为新值），**EdGraph pin 的 `DefaultObject` 缓存仍指向源资产**，因此包内保留了对源动画的硬引用；Node 属性已更新但 pin 缓存未刷新。UE 5.8 Python **未暴露** EdGraph `Nodes`/`Pins` 写接口，也**未暴露**编辑器内置的「Retarget Anim Blueprints」工具，故无法通过自动化清除这些缓存。

**STEP 14（编译）**：`compile_blueprint` 返回成功，状态 `BS_UP_TO_DATE_WITH_WARNINGS`，但产生 **11 条 ControlRig 绑定告警**：`Hierarchy discrepancy for bone 'clavicle_l/r' | 'index_01_l/r' … | 'neck_01' | 'head' - different parents on Control Rig vs SkeletalMesh`。原因是源 `CR_Mannequin_FootIK` 为 Mannequin 专用，无法用于 `SK_FutsalHuman`。

```
ABP_COMPILE = PASS_WITH_WARNINGS（无编译错误；但存在骨架不匹配告警 → 按 STEP 14 严格标准不达标）
```

## G.5 STEP 15–19 — 语义 / 运行时 / 架构

- STEP 15 状态机语义：**结构等价**（2 SM / 6 State / 8 Transition 计数一致，逐节点复制）。逐状态名/过渡条件无法由 Python 只读导出 → 依据结构判定为 PASS，但建议人工在编辑器中确认状态名与过渡。
- STEP 16/17 运行时验证：**NOT_TESTED**。理由：ABP 仍含源硬引用与不兼容 FootIK，运行时验证会被污染；且需在隔离关卡搭建 Character 测试蓝图（本阶段未创建，避免半成品）。建议在清除源引用与处理 FootIK 后进行。
- STEP 18 架构：运行时不需要第二套隐藏 SK_Mannequin 网格、不需要 Retarget Pose From Mesh、不需要 per-player Retargeter（重定向为离线资产生产）：
  ```
  DUAL_MESH_RUNTIME          = NO
  RUNTIME_RETARGET_NODE      = NO
  SHARED_TARGET_ANIM_LIBRARY = YES（FH_* + BS_FutsalHuman_Locomotion）
  SHARED_TARGET_ANIMBP       = YES（单一 ABP_FutsalHuman）
  ```
- STEP 19：未迁移 `BP_FutsalCharacterBase`、未改 MASTER_ANIMBP/生产 Mesh/Spawn/Appearance/Dataset actor（属 Phase 5C.6）。

## G.6 解除阻断的建议（不在本阶段执行）

1. 用 **UE 编辑器内置的「Retarget Anim Blueprints」**（右键 `ABP_FutsalSource` → Retarget Anim Blueprints → 目标 `SK_FutsalHuman`）生成干净的 ABP，或提供一个小型编辑器工具调用 `FAnimBlueprintUtils::RetargetAnimBlueprint`（未在 Python 暴露），以刷新 graph pin 的 `DefaultObject`。
2. 处理 `CR_Mannequin_FootIK`：为 FutsalHuman 新建 FootIK Control Rig（或在 target ABP 中明确移除该节点，并记录为有意差异）。
3. 之后重跑 STEP 13/14/16/17。

## G.7 FINAL STRUCTURED RESULT（Phase 5C.5）

```
PHASE5C5_ABP_FUTSALHUMAN = BLOCKED

SOURCE_ABP      = /Game/FutsalMOT/Animation/Source/ABP_FutsalSource
TARGET_ABP      = /Game/FutsalMOT/Animation/FutsalHuman/ABP/ABP_FutsalHuman
SOURCE_SKELETON = SK_Mannequin
TARGET_SKELETON = SK_FutsalHuman

SOURCE_RUNTIME_ANIMATION_DEPENDENCY_COUNT = 20
TARGET_ANIMATION_SEQUENCE_COUNT = 20
TARGET_BLENDSPACE_COUNT         = 1
TARGET_OTHER_ANIMATION_ASSET_COUNT = 0

ANIMBP_LOGIC_EQUIVALENCE = PASS（结构等价；逐状态/过渡文本价受 Python 接口限制）
TARGET_SKELETON_ASSIGNMENT = PASS

SOURCE_ANIMATION_RUNTIME_REFERENCES = 5   （要求 0 → FAIL）
TEST_ASSET_RUNTIME_REFERENCES       = 0

ABP_COMPILE = PASS_WITH_WARNINGS（FootIK 骨架不匹配告警 11 条）
STATE_MACHINE_SEMANTICS = PASS（结构）

RUNTIME_IDLE          = NOT_TESTED
RUNTIME_FORWARD       = NOT_TESTED
RUNTIME_LATERAL       = NOT_TESTED
RUNTIME_BACK          = NOT_APPLICABLE
RUNTIME_JUMP_FALL_LAND = NOT_TESTED

DUAL_MESH_RUNTIME          = NO
RUNTIME_RETARGET_NODE      = NO
SHARED_TARGET_ANIM_LIBRARY = YES
SHARED_TARGET_ANIMBP       = YES

FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN

NEXT_PHASE = BLOCKED（需先清除 ABP 源硬引用 + 处理 FootIK control rig）
```

---

# Phase 5C.5a — Agent Preflight for Minimal Manual ABP Repair

- 阶段：Phase 5C.5a（在 5C.5 BLOCKED 后，尽可能由 Python/MCP 完成，只保留纯 GUI 操作给人工）
- **关键新取证（不改写 5C.5 历史结论）**：规范路径 `/Game/FutsalMOT/Animation/FutsalHuman/ABP/ABP_FutsalHuman` 当时**并不存在**；该目录下实际唯一 ABP 为 `ABP_FutsalHuman_Failed`。
- 对 `ABP_FutsalHuman_Failed` 的重新审计（AnimGraphNode 属性 + 资产注册表硬依赖 + 二进制 `.uasset` 字符串扫描）显示：**5 个源动画引用已不复存在**（`SOURCE_ANIMATION_RUNTIME_REFERENCES = 0`），节点属性已正确指向 `FH_*` 与 `BS_FutsalHuman_Locomotion`；唯一残留的不兼容引用为 `CR_Mannequin_FootIK`。即：`MM_Idle/MM_Jump/MM_Fall_Loop/MM_Land/BS_Futsal_Locomotion` 的包硬引用、`/Game/Characters/Mannequins/Anims` 路径、`SK_Mannequin` 均**不在**该资产内（`MM_*` 字符串出现次数仅等于其 `FH_MM_*` 子串次数）。
- 因此原计划的 5 项“动画引用替换”GUI 操作**无需执行**；实际只需 1 项 GUI 操作（移除 FootIK 节点）。
- 经用户确认后，Agent 执行（均非 GUI）：
  - 备份：`ABP_FutsalHuman_Failed` → `/Game/FutsalMOT/Test/FutsalHumanCompatibility/ABPManualFixBackup/ABP_FutsalHuman_PreManualFix`（只读证据，保留）。
  - 重命名：`ABP_FutsalHuman_Failed` → `/Game/FutsalMOT/Animation/FutsalHuman/ABP/ABP_FutsalHuman`（skeleton=`SK_FutsalHuman`，parent=`AnimInstance`）。
- 修复前图结构快照：Root1 / StateMachine2 / StateResult6 / TransitionResult8 / SequencePlayer4 / BlendSpacePlayer1 / **ControlRig1** / SaveCachedPose1("Locomotion") / UseCachedPose1 / Slot1(DefaultSlot)。

```
PHASE5C5A_AGENT_PREFLIGHT = COMPLETE
MANUAL_GUI_ACTION_COUNT   = 1
```

---

# Phase 5C.5b — FootIK Removal and ABP Closure

- 阶段：Phase 5C.5b（人工完成唯一 GUI 操作：移除 `CR_Mannequin_FootIK` 并重连 Pose 链；其余全部由 Agent 通过 Python/MCP 完成）
- 历史保留：5C.5 的 BLOCKED 结果与 stale EdGraph 引用分析**保留不改写**（见 G.4/G.7）；本节追加后续取证与闭环。

## H.1 STEP 0/1 — 编译与 ControlRig 移除验证

- `compile_blueprint(ABP_FutsalHuman)` → 成功；`save_asset` → 成功。
- **编译告警 = 0**：移除 FootIK 后 `Hierarchy discrepancy` / ControlRig 绑定告警全部消失（日志 12:25:35 之后的每次编译均无告警，12:26:19 最新一次为 0 告警；此前 12:25:08–09 的告警属移除前 / 备份资产）。
- `AnimGraphNode_ControlRig` 计数 = **0**；包硬依赖不含 `CR_Mannequin_FootIK`，且 `/Script/ControlRig`、`/Script/ControlRigDeveloper` 一并消失。

```
MANNEQUIN_FOOTIK_REFERENCE = NO
CONTROL_RIG_NODE_COUNT     = 0
ABP_COMPILE                = PASS
```

## H.2 STEP 2/3 — 引用清零与图结构回归

- 修复后包硬依赖：`AnimGraph`、`AnimGraphRuntime`、`BPI_FutsalAnimationSource`、`SK_FutsalHuman`、`FH_MM_Idle`、`FH_MM_Jump`、`FH_MM_Fall_Loop`、`FH_MM_Land`、`BS_FutsalHuman_Locomotion`。
- 节点属性：4×SequencePlayer → `FH_MM_{Idle,Jump,Fall_Loop,Land}`；1×BlendSpacePlayer → `BS_FutsalHuman_Locomotion`；Slot=`DefaultSlot`。
- 图结构回归：**仅** ControlRig 1→0，其余计数不变（Root1/SM2/State6/Trans8/SeqP4/BSP1/Save1/Use1/Slot1）→ 姿态链无其他改动。

```
SOURCE_ANIMATION_RUNTIME_REFERENCES = 0
TEST_ASSET_RUNTIME_REFERENCES       = 0
ANIMBP_LOGIC_EQUIVALENCE = PASS_WITH_INTENTIONAL_FOOTIK_REMOVAL
```

## H.3 STEP 4 — 目标资产审计

- 20 个 `FH_*` 序列全部 `skeleton = SK_FutsalHuman`、时长非零有效；`BS_FutsalHuman_Locomotion` skeleton=`SK_FutsalHuman`、27 samples、全部 `FH_*`。
- 规范 Retargeter/IKRig/Mesh/Skeleton 引用未变（RTG→IKR_Quinn/IKR_FutsalHuman/SKM_*；Mesh→`SK_FutsalHuman`）。
- 生产资产不引用任何 `ABPCleanRetarget`/`CleanCandidate`/`RetargetSpike`/`FreezeRegression`/`RootScaleTest`/`RootCleanTest`。

```
TARGET_RUNTIME_DEPENDENCY_AUDIT = PASS
```

## H.4 STEP 6/7 — 隔离运行时 Harness 与运行时验证

Harness（隔离，`/Game/FutsalMOT/Test/FutsalHumanCompatibility/ABPTest/`）：

- 关卡 `L_FutsalHuman_ABPTest`（`new_level` 新建，含一个测试地面 `StaticMeshActor`）。
- 放置 `BP_FutsalCharacterBase` 实例，并**按实例**覆写 `Mesh=SKM_FutsalHuman_Base`、`AnimClass=ABP_FutsalHuman_C`（未修改 `BP_FutsalCharacterBase`；未派生新 BP，以规避对父类继承组件模板的写入风险）。
- 未使用 / 未修改 `L_FutsalCourt`（验证结束后编辑器已恢复回 `L_FutsalCourt`）。

运行时观测（PIE，通过 `get_pie_worlds` / `GameplayStatics` / 组件 API）：

- AnimInstance 存在且为 `ABP_FutsalHuman_C`；Mesh=`SKM_FutsalHuman_Base`；`animation_mode=ANIMATION_BLUEPRINT`；角色正常落地、`is_falling=false`、`MotionSpeedMps=0`。
- **骨骼姿态在整个 PIE 会话内逐位不变**（`get_bone_transform` 7 位小数完全相同，世界时间确实前进 31→111 s）。
- **环境归因（非 ABP 缺陷）**：同一 harness 内把组件切到 **单节点**直接播放 `FH_MM_Idle` 后姿态同样不随时钟前进；`blueprint_update_animation` / `kismet_update_animation` 手动驱动不推进原生 AnimGraph 节点。根因为**后台/非前台 PIE 下骨骼姿态不刷新/不推进**（3 fps 节流，`RefreshBoneTransforms`/pose 未更新）。因此**无法在该自动化环境中观测运行时图执行**，且**未**以单节点/ABP 输出静帧冒充运行时通过。

```
NUMERIC_RUNTIME_VALIDATION = NOT_TESTED（环境限制：后台 PIE 不刷新/推进骨骼姿态）
VISUAL_RUNTIME_VALIDATION  = NOT_AVAILABLE（Agent 无视觉；未伪造视觉 PASS）
RUNTIME_IDLE / FORWARD / LATERAL / JUMP_FALL_LAND = NOT_TESTED
RUNTIME_BACK = NOT_APPLICABLE
```

## H.5 STEP 8/9 — FootIK 与冻结判定

```
FUTSAL_HUMAN_FOOTIK_V1 = DEFERRED（未创建替代 FootIK，未添加 IK helper 骨）
```

STEP 9 冻结门槛要求“运行时功能验证 = PASS”。本次运行时验证为 `NOT_TESTED`，故本阶段**不冻结**：

```
FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN
```

## H.6 FINAL STRUCTURED RESULT（Phase 5C.5b）

```
PHASE5C5_ABP_FUTSALHUMAN = PARTIAL（离线/结构/编译闭环完成；运行时验证受环境限制）

MANUAL_GUI_ACTIONS_REQUIRED  = 1
MANUAL_GUI_ACTIONS_COMPLETED = 1

TARGET_ABP      = /Game/FutsalMOT/Animation/FutsalHuman/ABP/ABP_FutsalHuman
TARGET_SKELETON = SK_FutsalHuman

SOURCE_ANIMATION_RUNTIME_REFERENCES = 0
TEST_ASSET_RUNTIME_REFERENCES       = 0
MANNEQUIN_FOOTIK_REFERENCE          = NO
CONTROL_RIG_NODE_COUNT              = 0
TARGET_FOOTIK_IMPLEMENTATION        = DEFERRED

ANIMBP_LOGIC_EQUIVALENCE        = PASS_WITH_INTENTIONAL_FOOTIK_REMOVAL
TARGET_RUNTIME_DEPENDENCY_AUDIT = PASS
ABP_COMPILE                     = PASS

RUNTIME_IDLE / FORWARD / LATERAL = NOT_TESTED
RUNTIME_BACK                     = NOT_APPLICABLE
RUNTIME_JUMP_FALL_LAND           = NOT_TESTED
NUMERIC_RUNTIME_VALIDATION       = NOT_TESTED
VISUAL_RUNTIME_VALIDATION        = NOT_AVAILABLE

FUTSAL_HUMAN_FOOTIK_V1 = DEFERRED
FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN

DUAL_MESH_RUNTIME=NO / RUNTIME_RETARGET_NODE=NO / PER_PLAYER_RETARGETER=NO / PER_PLAYER_ANIMBP=NO
SHARED_TARGET_ANIM_LIBRARY=YES / SHARED_TARGET_ANIMBP=YES

NEXT_PHASE = BLOCKED（需在可刷新骨骼姿态的前台 PIE，或由人工补签运行时验证）
```

---

# Phase 5C.5d — Foreground Runtime No-Motion Investigation

- 阶段：Phase 5C.5d（**只读取证**；人工作前台 PIE 观察到使用 `SKM_FutsalHuman_Base` + `ABP_FutsalHuman` 的角色无可见身体动画）
- 权威状态：`HUMAN_FOREGROUND_RUNTIME_VALIDATION = FAIL`、`FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN`、`NEXT_PHASE = BLOCKED`（冻结取消）。
- 本阶段**未修改任何资产**（ABP / 动画 / Skeleton / 蓝图 / 关卡 / Retargeter 均只读）。

## I.1 生产 FH_* 仅含根/骨盆运动，无身体关节运动

用 `unreal.AnimationLibrary.get_bone_pose_for_frame(seq, bone_name(str), frame, False)`（注意：bone_name 必须传 **str**，传 `unreal.Name` 会静默返回单位量——这正是 5C.5 旧校验“finite/root”失效的原因）对 7 个采样帧（0/10/25/50/75/90/100%）读取 16 根非根骨骼局部位姿，统计帧间平移/旋转极差：

| Clip | 帧数 | MOVING_NON_ROOT_BONE_COUNT | 非根平移极差(cm) | 非根旋转极差(deg) |
|---|---|---|---|---|
| FH_MM_Idle | 227 | **0** | 0.0 | 0.0 |
| FH_MF_Unarmed_Walk_Fwd | 45 | **1** | 6.98 | 22.68 |
| FH_MF_Unarmed_Jog_Fwd | 53 | **1** | 6.39 | 20.36 |
| FH_MF_Unarmed_Jog_Left | 46 | **1** | 7.31 | 15.93 |
| FH_MM_Jump | 26 | **1** | 39.04 | 50.92 |
| FH_MM_Fall_Loop | 90 | **1** | 4.73 | 7.88 |
| FH_MM_Land | 26 | **1** | 25.56 | 20.51 |

- 唯一“运动”的骨是 `pelvis`；`spine_* / upperarm_* / lowerarm_* / hand_* / thigh_* / calf_* / foot_*` 全部帧间**旋转极差 = 0.0°**（完全不变）。
- `FH_MM_Idle` 连 pelvis 都不变 → 完全静止。
- `BODY_ANIMATION_CONTENT = STATIC_OR_NEAR_STATIC`。

## I.2 对照已知良好测试资产（STEP 2）

同一 API 审计 5C.3 的 `RTG_*`（compatibility retarget）与 5C.4 的 `FRZ_*`（canonical retarget 回归）：

| Clip | MOVING_NON_ROOT_BONE_COUNT | 非根旋转极差(deg) | 例（Jog_Fwd 各骨旋转极差） |
|---|---|---|---|
| RTG_MF_Unarmed_Jog_Fwd | **16** | 104.61 | upperarm_l 103.0 / thigh_l 104.6 / calf_l 68.1 |
| FH_MF_Unarmed_Jog_Fwd | 1 | 20.36 | 除 pelvis 外全 0.0 |
| FRZ_MF_Unarmed_Jog_Fwd | 1 | 20.36 | 除 pelvis 外全 0.0 |

- `RTG_*` 的 Jog_Fwd / Jog_Left / Jump / Fall_Loop / Land 全部 **16 骨运动**（RTG_MM_Idle 因源 Idle 幅度小，与 FH 同为低幅）。
- 三者的 pelvis 数值完全一致（Jog_Fwd pelvis 6.39 cm / 20.36°），差异仅在**肢体/脊柱链**。
- `KNOWN_GOOD_TEST_ASSET_BODY_MOTION = PASS`（RTG_*，且 5C.3 有人工视觉签核）
- `PRODUCTION_FH_BODY_MOTION = FAIL`
- `MOTION_CONTENT_EQUIVALENT = NO`

## I.3 轨道内容审计（STEP 3）

- `FH_MF_Unarmed_Jog_Fwd` / `FRZ_*` / `RTG_*` 均含 **53 条骨骼轨道**（`root, pelvis, spine_01..03, clavicle_l, upperarm_l, ...`），且 `does_bone_name_exist('upperarm_l'/'thigh_l'/'spine_01') = True`。
- **排除“骨骼名不匹配导致读数为空”的可能**：FH/FRZ 的肢体轨道存在，但取值恒定（参考姿势）。
- 现象：Root/pelvis 轨道有动画，肢体/脊柱轨道恒为参考值 → `PRODUCTION_ANIMATION_TRACK_CONTENT = FAIL`。

## I.4 BlendSpace / ABP 直接序列（STEP 4/5）

- `BS_FutsalHuman_Locomotion`：27 samples、全部 `FH_*`（结构 PASS），但被引用的 `FH_*` 无身体运动 → `BLENDSPACE_SAMPLE_BODY_MOTION = FAIL`。
- ABP 四个直接 SequencePlayer 指向 `FH_MM_Idle / FH_MM_Jump / FH_MM_Fall_Loop / FH_MM_Land`（引用正确），但内容无身体运动 → `ABP_DIRECT_SEQUENCE_CONTENT = FAIL`。

## I.5 组件/实例配置与图连接（STEP 6/7/8/9）

- Harness mesh（只读）：`animation_mode=ANIMATION_BLUEPRINT`、`anim_class=ABP_FutsalHuman_C`、`pause_anims=False`、`no_skeleton_update=False`、`global_anim_rate_scale=1.0`、`enable_animation=True`、`ALWAYS_TICK_POSE`、tick 启用 → `SKELETAL_MESH_COMPONENT_CONFIG = PASS`（无冻结类开关）。
- 之前记录的后台 PIE“骨骼姿态不推进”为测试环境限制；**前台人工 PIE 观察到的无动画与“内容静止”一致**，故组件配置不是根因。
- `ANIM_INSTANCE_CREATION = PASS`；驱动变量（`MotionSpeedMps` / `AnimationClassId`）可读；`ANIM_DRIVING_VARIABLE_ACTIVITY = STATIC/UNKNOWN`。
- `POSE_GRAPH_CONNECTIVITY = NOT_VISIBLE_TO_TOOLING`（UE5.8 Python 无 EdGraph pin 读接口）；但**内容静止已足以解释现象，ABP 图连接不是主因**。
- `ABP_COMPILE = PASS`（0 告警）；运行日志未见 animation/skeleton/blendspace/pose 相关报错。

## I.6 根因层判定（STEP 10）

证据链：`RTG_*`（5C.3 compatibility retarget）有完整身体运动；`FRZ_*`（5C.4 canonical retarget 回归）与 `FH_*`（5C.5 生产库）**均只有 pelvis 运动**。三者 pelvis 数值相同，差异集中于肢体/脊柱链；轨道存在但恒定。

```
ROOT_CAUSE_LAYER = PRODUCTION_ANIMATION_CONTENT
   （子层：canonical RTG_Mannequin_To_FutsalHuman 生成的动画仅含根/骨盆运动，
     未把肢体/脊柱链姿态写入。5C.4 的“回归 PASS”与 5C.5 的“20/20 PASS”只校验了
     skeleton / duration / root scale / finite，未校验非根骨运动，故一直未发现。）
```

- 5C.3 使用的 `RTG_Mannequin_To_FutsalHuman_Compatibility` 结果正常；出问题的生产路径为 canonical `RTG_Mannequin_To_FutsalHuman`（及 5C.4 的 FRZ 回归导出）。
- 未修改任何资产；未重新生成动画；未恢复 FootIK。

## I.7 最小人工动作（STEP 11）

本轮自动化取证已足以判定根因层，**无需新增人工 GUI 观察**：

```
USER_MANUAL_ACTION_REQUIRED = NO（诊断层面）
MINIMAL_MANUAL_ACTION = N/A
```

> 注：真正修复需要重新生成生产动画再做一次人工作前台视觉验收；修复不属于本只读取证阶段。

## I.8 FINAL STRUCTURED RESULT（Phase 5C.5d）

```
PHASE5C5D_RUNTIME_FORENSIC = COMPLETE
HUMAN_FOREGROUND_RUNTIME_VALIDATION = FAIL

FH_IDLE_BODY_MOTION     = FAIL
FH_WALK_FWD_BODY_MOTION = FAIL
FH_JOG_FWD_BODY_MOTION  = FAIL
FH_JOG_LEFT_BODY_MOTION = FAIL
FH_JUMP_BODY_MOTION     = FAIL
FH_FALL_BODY_MOTION     = FAIL
FH_LAND_BODY_MOTION     = FAIL

KNOWN_GOOD_TEST_ASSET_BODY_MOTION = PASS（RTG_*，5C.3；有人工视觉签核）
PRODUCTION_VS_TEST_MOTION_EQUIVALENCE = NO

PRODUCTION_ANIMATION_TRACK_CONTENT = FAIL
BLENDSPACE_SAMPLE_BODY_MOTION      = FAIL
SKELETAL_MESH_COMPONENT_CONFIG     = PASS
ANIM_INSTANCE_CREATION             = PASS
ANIM_DRIVING_VARIABLE_ACTIVITY     = STATIC/UNKNOWN
POSE_GRAPH_CONNECTIVITY            = NOT_VISIBLE_TO_TOOLING
ABP_COMPILE                        = PASS

ROOT_CAUSE_LAYER = PRODUCTION_ANIMATION_CONTENT
USER_MANUAL_ACTION_REQUIRED = NO
MINIMAL_MANUAL_ACTION = N/A

FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN
NEXT_PHASE = BLOCKED
```

---

# Phase RESET++ — FutsalHuman V1 + Jersey Number V1 Decommission + Content Hygiene

- 阶段：经用户授权的破坏性内容清理（重启人物生产管线前）。
- 权威退休状态：`FUTSAL_HUMAN_V1_PIPELINE = DECOMMISSIONED`、`FUTSAL_HUMAN_SKELETON_STANDARD_V1 = RETIRED`、`FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN`、`FUTSAL_HUMAN_IMPORTED_MODEL = NONE`；`JERSEY_NUMBER_RENDERING_V1 = DECOMMISSIONED`、`JERSEY_NUMBER_STATIC_PLANE_PROTOTYPE = RETIRED`、`JERSEY_NUMBER_DIGIT_ATLAS_V1 = RETIRED`、`JERSEY_NUMBER_PRODUCTION_IMPLEMENTATION = NONE`、`JERSEY_NUMBER_REQUIREMENT = TO_BE_REDESIGNED`（语义字段保留，`JERSEY_NUMBER_METADATA_REQUIREMENT` 未判为 REMOVED）。
- 工具链说明：本会话未挂载 Unreal MCP 工具，改以 UE MCP 的 HTTP JSON-RPC（`http://127.0.0.1:8000/mcp` 的 `call_tool` → `futsalmot_tools.FutsalMOTTools.run_python_file`）驱动真实 UE Python 完成全部资产操作。

## RESET.1 基线与清点

- git：`refactor/character-architecture` @ `99a9b758`；基线 3 个预存 ` M`（`BP_FutsalAppearancePrototype.uasset`、`UNREAL_RIG.uasset`、`L_FutsalAppearancePrototype_Test.umap`）+ 未跟踪 `Docs/.../FUTSAL_HUMAN_UE_IMPORT_AUDIT.md`。
- 清理前 `/Game/FutsalMOT/`：**1331** 资产 / **76** 文件夹（其中 `/Game/FutsalMOT/code/` 子模块含 1154 个 smoke 测试纹理，属数据集代码仓库，**不在本次范围**）。

## RESET.2 FutsalHuman V1 删除家族（DELETE_DEPRECATED）

删除前对每个候选做 referencer 审计：**外部（KEEP）引用者 = 0**（整族自洽闭合）。以 `EditorAssetLibrary.delete_directory` / `delete_asset`（UE 资产 API，未先手工删文件）整体删除：

| 家族 | 资产数 |
|---|---|
| `/Game/FutsalMOT/Characters/FutsalHuman/**`（SKM_FutsalHuman_Base、SK_FutsalHuman） | 2 |
| `/Game/FutsalMOT/Animation/FutsalHuman/**`（ABP_FutsalHuman、BS_FutsalHuman_Locomotion、17 FH 序列、3 Jump 序列） | 22 |
| `/Game/FutsalMOT/Animation/Retarget/IKR_FutsalHuman` | 1 |
| `/Game/FutsalMOT/Animation/Retarget/RTG_Mannequin_To_FutsalHuman` | 1 |
| `/Game/FutsalMOT/Test/FutsalHumanCompatibility/**`（RootCleanTest / RootScaleTest / RetargetSpike / FreezeRegression / ABPCleanRetarget / ABPManualFixBackup / ABPTest / 顶层兼容网格与骨架） | 46 |
| **合计** | **72** |

- 删除后 3 个目录在磁盘与 registry 均消失；`ORPHANED_FUTSALHUMAN_PACKAGE_FILES = 0`。

## RESET.3 Jersey Number V1（未删除，REVIEW_REQUIRED 阻断）

| 资产 | 类 | 引用者 |
|---|---|---|
| `/Game/FutsalMOT/Appearance/Materials/Numbers/M_FutsalNumber_Master` | Material | `BP_FutsalAppearancePrototype`（外部引用者） |
| `/Game/FutsalMOT/Appearance/Textures/Numbers/T_FutsalNumberAtlas` | Texture2D | `M_FutsalNumber_Master` |

- `BP_FutsalAppearancePrototype`（**预存 dirty**、多用途）依赖：`/Engine/BasicShapes/Plane`（旧 number plane）、`M_FutsalNumber_Master`、`MI_FutsalKit_Quinn`、`MI_FutsalSkin_Quinn`、`BP_FutsalCharacterBase`。即同一 Blueprint 同时承载**已退休的 number-plane 渲染**与**在用 skin/kit 外观**。
- 依据“不得静默改写 dirty/多用途资产、不得因清理破坏其它在用外观”：
  ```
  BP_FutsalAppearancePrototype     = REVIEW_REQUIRED（内容保持基线，未改写）
  M_FutsalNumber_Master            = REVIEW_REQUIRED / JERSEY_NUMBER_EXTERNAL_REFERENCER（阻断）
  T_FutsalNumberAtlas              = REVIEW_REQUIRED / JERSEY_NUMBER_EXTERNAL_REFERENCER（阻断）
  L_FutsalAppearancePrototype_Test = KEEP（外观测试地图，预存 dirty）
  /Engine/BasicShapes/Plane        = 引擎资产，未触碰
  ```
- 因此本阶段 **未删除任何 jersey-number 资产**（`DELETED_JERSEY_NUMBER_* = 0`）。清除实现需先人工重构该原型（分离外观与数字平面），属后续单独阶段。
- 旧渲染契约 `FinalU=(U+Digit)*0.1 / FinalV=V`、10 列 digit atlas、Static Mesh number plane、前后身平面布局 **不再视为生产架构**（历史记录保留）。

## RESET.4 未做移动/重命名

- `MOVE_SAFE = 0`：`Animation/SoccerPlayer`、`Animation/SoccerSource`、`_Archive/AbandonedExperiments`、`Test/*` 等均有活跃引用或属有意归档，不满足“目标路径唯一且无歧义”，按保守原则**不移动**。
- 清理后无空文件夹残留；唯一空目录 `Characters/FutsalPlayer/Rigs` 已移除。

## RESET.5 清理后审计

```
BROKEN_REMAINING_ASSET_REFERENCES = 0
RESIDUAL_FUTSALHUMAN_PACKAGE_REFERENCES = 0
  （registry 搜索 FutsalHuman / SK_FutsalHuman / SKM_FutsalHuman / IKR_FutsalHuman /
    RTG_Mannequin_To_FutsalHuman / ABP_FutsalHuman / BS_FutsalHuman / FH_ / FRZ_ /
    _CleanCandidate / Compatibility_01 = 0）
RESIDUAL_JERSEY_NUMBER_V1_PACKAGE_REFERENCES = 2（上述 REVIEW_REQUIRED 阻断对）
ORPHANED_FUTSALHUMAN_PACKAGE_FILES = 0
ORPHANED_JERSEY_NUMBER_V1_PACKAGE_FILES = 0
ObjectRedirector(/Game/FutsalMOT) = 0
SOURCE_MANNEQUIN_PIPELINE = PRESERVED
GENERAL_APPEARANCE_PIPELINE = PRESERVED
```

- 清理后 `/Game/FutsalMOT/`：**1259** 资产（1154 在 `code/` 子模块；**105** 在其余内容树）/ **33** 文件夹（不含 `code/`）。
- 残留 REVIEW_REQUIRED：`BP_FutsalAppearancePrototype`、`M_FutsalNumber_Master`、`T_FutsalNumberAtlas`（另有预存 dirty 的 `L_FutsalAppearancePrototype_Test` 归 KEEP）。

## RESET.6 保护资产状态（vs 基线）

```
UNREAL_RIG.uasset                = UNCHANGED_FROM_BASELINE（仍为外部未解决改动，未触碰）
L_FutsalCourt                    = UNCHANGED_FROM_BASELINE
BP_FutsalCharacterBase           = UNCHANGED_FROM_BASELINE
ABP_FutsalSource                 = UNCHANGED_FROM_BASELINE
IKR_Quinn                        = UNCHANGED_FROM_BASELINE
SK_Mannequin / SKM_Quinn_Simple  = UNCHANGED_FROM_BASELINE
BP_FutsalAppearancePrototype     = UNCHANGED_FROM_BASELINE（保留预存本地修改）
L_FutsalAppearancePrototype_Test = UNCHANGED_FROM_BASELINE
```

- 项目内（排除 `Content/`、`Saved/`、`Intermediate/`、`DerivedDataCache/`）未发现 FutsalHuman 命名原始导出；主 Blender 工程在项目外，未触碰。

## RESET.7 FINAL STATUS（Phase RESET++）

```
PHASE_RESET_AND_CONTENT_HYGIENE = COMPLETE

PRE_CLEANUP_ASSET_COUNT  = 1331
POST_CLEANUP_ASSET_COUNT = 1259
DELETED_ASSET_COUNT      = 72
MOVED_ASSET_COUNT        = 0
REDIRECTORS_REMOVED      = 0
EMPTY_FOLDERS_REMOVED    = 1
REVIEW_REQUIRED_ASSET_COUNT = 3

DELETED_FUTSALHUMAN_CHARACTER_ASSETS = 2
DELETED_FUTSALHUMAN_ANIMATION_ASSETS = 22
DELETED_FUTSALHUMAN_RETARGET_ASSETS  = 2
DELETED_FUTSALHUMAN_TEST_ASSETS      = 46

DELETED_JERSEY_NUMBER_ASSETS   = 0（REVIEW_REQUIRED 阻断）
DELETED_JERSEY_NUMBER_MESHES   = 0
DELETED_JERSEY_NUMBER_TEXTURES = 0
DELETED_JERSEY_NUMBER_MATERIALS= 0
DELETED_JERSEY_NUMBER_BLUEPRINTS = 0
DELETED_JERSEY_NUMBER_TEST_ASSETS = 0

FUTSAL_HUMAN_V1_PIPELINE = DECOMMISSIONED
FUTSAL_HUMAN_SKELETON_STANDARD_V1 = RETIRED
FUTSAL_HUMAN_ANIMATION_ARCHITECTURE_V1 = NOT_FROZEN
FUTSAL_HUMAN_IMPORTED_MODEL = NONE

JERSEY_NUMBER_RENDERING_V1 = DECOMMISSIONED
JERSEY_NUMBER_STATIC_PLANE_PROTOTYPE = RETIRED
JERSEY_NUMBER_DIGIT_ATLAS_V1 = RETIRED
JERSEY_NUMBER_PRODUCTION_IMPLEMENTATION = NONE
JERSEY_NUMBER_REQUIREMENT = TO_BE_REDESIGNED

NEXT_PHASE = RESTART_MODEL_AUTHORING_AND_IMPORT_FROM_SCRATCH
```

---

# Phase RESET++B — Jersey Number Feature Final Closure

- 阶段：Phase RESET++B（人工完成 Blueprint 手动移除并经关闭/重开验证后，由 Agent 执行物理下线闭环）。
- 权威决定（取代先前“保留 JerseyNumber 元数据”）：`JERSEY_NUMBER_FEATURE = REMOVED`、`JERSEY_NUMBER_REQUIREMENT = NONE`、`JERSEY_NUMBER_METADATA_FIELD = REMOVED`。
- 工具：本会话未挂载 Unreal MCP 工具，改以 UE MCP HTTP JSON-RPC（`call_tool` → `run_python_file`）驱动真实 UE Python。

## RESETB.1 磁盘级持久化门（close / unload / GC / reload）

对 `BP_FutsalAppearancePrototype` 执行：关闭资产编辑器 → 卸载包 → GC → 重新加载（该 reload 方法在本会话内已验证有效：可控探针可被卸载/删除）。重载后读取磁盘保存版本：

```
SAVED_BP_NUMBER_COMPONENT_COUNT = 0   （Own_components = []；无 FrontTens/FrontOnes/BackTens/BackOnes）
SAVED_BP_NUMBER_VARIABLE_COUNT  = 0   （vars = SkinToneId, KitId, SkinMID, KitMID, SkinTint, KitColor, AppearanceId）
SAVED_BLUEPRINT_REMOVAL         = PASS
```

## RESETB.2 依赖审计（STEP 2）

```
BP_FutsalAppearancePrototype deps = [ /Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase ]
```

- 无 `M_FutsalNumber_Master`、无 `T_FutsalNumberAtlas`、无 number-plane 的 `/Engine/BasicShapes/Plane` 引用 → `OLD_NUMBER_RENDERER_BLUEPRINT_REFERENCES = 0`。

## RESETB.3 编译 / 外观回归（STEP 3/4）

```
BP_FUTSALAPPEARANCEPROTOTYPE_COMPILE = PASS（0 error）
```

- **注意（回归）**：移除后该 Blueprint 仅保留 7 个外观变量，但**不再引用任何 skin/kit 材质**（deps 仅剩父类）；`InitializeAppearanceMaterials` / `ApplyAppearance` 已为空 → 皮肤/球衣材质的运行时应用逻辑在人工移除时被一并清空。
  ```
  GENERAL_APPEARANCE_LOGIC = FAIL（变量保留；材质应用逻辑缺失）→ REVIEW_REQUIRED
  ```
  材质资产仍在：`M_FutsalSkin_Master`、`MI_FutsalSkin_Quinn`、`M_FutsalKit_Master`、`MI_FutsalKit_Quinn`。

## RESETB.4 物理删除（STEP 5–8）

删除前 referencer：`M_FutsalNumber_Master` ← `_Archive/AbandonedExperiments/BP_FutsalAppearancePrototype_PreNumberRemoval`；`T_FutsalNumberAtlas` ← `M_FutsalNumber_Master`。

经用户明确授权（“delete material+atlas AND the backup”），用 UE 资产 API 删除：

- `/Game/FutsalMOT/Appearance/Materials/Numbers/M_FutsalNumber_Master` → **DELETED**
- `/Game/FutsalMOT/Appearance/Textures/Numbers/T_FutsalNumberAtlas` → **DELETED**
- `/Game/FutsalMOT/_Archive/AbandonedExperiments/BP_FutsalAppearancePrototype_PreNumberRemoval`（回滚备份）→ **DELETED**（避免挂空引用）

空目录已移除：`Appearance/Materials/Numbers/`、`Appearance/Textures/Numbers/`。

```
NUMBER_REMOVAL_REDIRECTORS_REMAINING = 0
ORPHANED_JERSEY_NUMBER_V1_PACKAGE_FILES = 0
```

## RESETB.5 残留搜索 / 测试地图（STEP 10/11）

- 全 `/Game/FutsalMOT/` 命名与依赖搜索 `JerseyNumber/FrontTens/FrontOnes/BackTens/BackOnes/NumberColor/FutsalNumber/DigitAtlas/NumberAtlas/NumberPlane/JerseyDigit/FrontNumber/BackNumber` → `residual_name_hits = []`。
- `L_FutsalAppearancePrototype_Test` 依赖：`BP_FutsalAppearancePrototype`、`SKM_Quinn_Simple`、`ABP_FutsalSource`、Cube/网格材质/导航等；无 number 资产 → 未修改。

```
OLD_JERSEY_NUMBER_RENDERER_ACTIVE_ASSETS = 0
RESIDUAL_OLD_NUMBER_RENDERER_REFERENCES = 0
RESIDUAL_JERSEY_NUMBER_V1_PACKAGE_REFERENCES = 0
```

## RESETB.6 最终外观树

```
Appearance/
    Materials/
        Kits/     M_FutsalKit_Master, MI_FutsalKit_Quinn
        Skin/     M_FutsalSkin_Master, MI_FutsalSkin_Quinn
    Prototype/    BP_FutsalAppearancePrototype
```

（`Materials/Numbers`、`Textures/Numbers` 已不存在。）

## RESETB.7 保护资产 / Git

```
UNREAL_RIG.uasset = UNCHANGED_FROM_BASELINE（外部未解决改动，未触碰）
L_FutsalCourt / BP_FutsalCharacterBase / ABP_FutsalSource / IKR_Quinn / source Mannequin = UNCHANGED_FROM_BASELINE
BP_FutsalAppearancePrototype = 有意修改（人工移除 number feature）
GIT_STAGED_FILES = 0 / GIT_COMMIT_CREATED = NO
```

- 旧实现契约（`FinalU=(U+Digit)*0.1`、`FinalV=V`、10 列 digit atlas、Static Mesh number plane）仅作历史记录，不再属于当前架构。

---

# Phase RESET++D — Hard-Delete Policy Enforcement (Backups / Archive / Appearance)

- 阶段：执行 `DEPRECATED_ASSET_POLICY = HARD_DELETE`、`BACKUP_POLICY = NONE`、`UE_ARCHIVE_POLICY = NONE`、`HISTORICAL_RECORD_POLICY = DOCUMENTATION_AND_GIT_HISTORY_ONLY`。
- 不再在 Unreal Content 内保留任何备份 / 归档 / 回滚 / 候选 / 快照资产；历史仅保留在 `Docs/` 与 git history。
- **本阶段取代 RESET++C**：Appearance 原型系统（SkinTint/KitColor）整体退役并删除，不再恢复其逻辑。

## RESETD.1 删除记录

用 UE 资产 API（`EditorAssetLibrary.delete_asset`，删除前审计 referencer）删除：

- `/Game/FutsalMOT/_Archive/AbandonedExperiments/BP_FutsalAppearancePrototype_PreSkinKitRestore` → **DELETED**（本会话 RESET++C 曾创建的备份）
- Appearance 原型系统（经用户明确授权 “Delete entire Appearance system”），referencer 链自洽闭合后删除：
  - `/Game/FutsalMOT/Appearance/Prototype/BP_FutsalAppearancePrototype` → **DELETED**
  - `/Game/FutsalMOT/Appearance/Materials/Skin/M_FutsalSkin_Master` → **DELETED**
  - `/Game/FutsalMOT/Appearance/Materials/Skin/MI_FutsalSkin_Quinn` → **DELETED**
  - `/Game/FutsalMOT/Appearance/Materials/Kits/M_FutsalKit_Master` → **DELETED**
  - `/Game/FutsalMOT/Appearance/Materials/Kits/MI_FutsalKit_Quinn` → **DELETED**
  - `/Game/FutsalMOT/Test/Appearance/L_FutsalAppearancePrototype_Test` → **DELETED**
  - 空目录 `Appearance/**`、`Test/Appearance/` → 已移除
- 先前（RESET++B）已删：`Appearance/Materials/Numbers/M_FutsalNumber_Master`、`Appearance/Textures/Numbers/T_FutsalNumberAtlas`。

> 工具说明：删除过程中 UnrealEditor 在“切换关卡”时崩溃关闭（进程消失、MCP 端口关闭）；BP 与测试地图因原先被加载而无法经 UE API 删除（且无外部 actor），最终以文件系统方式硬删除，UE 层 rescan/依赖校验需在编辑器重启后补做。

## RESETD.2 保留项（超出本次 reset 范围）

- `/Game/FutsalMOT/_Archive/AbandonedExperiments/BP_PoseRecorder_Proto` → **REVIEW_REQUIRED**：属 Pose Recorder 系统，非本次 reset 退役的 FutsalHuman / JerseyNumber / Appearance 系统；无 referencer。（编辑器运行期间 UE API 无法删除该 pinned 资产。）因此 `_Archive/` 未清空。
- `Test/GM_FutsalInputTest`、`Test/L_FutsalCharacterBase_Test` → KEEP（测试在用输入 / CharacterBase 系统）。

## RESETD.3 保护资产

```
UNREAL_RIG.uasset / L_FutsalCourt / BP_FutsalCharacterBase / ABP_FutsalSource / IKR_Quinn / source Mannequin = UNCHANGED_FROM_BASELINE
```

- `BP_FutsalCharacterBase` 依赖不含被删的 Appearance 资产 → 无悬空引用。
- 无 `git restore` / checkout / revert；未 stage / commit / tag / push。

## RESETD.4 最终状态

```
PHASE_RESET_HARD_DELETE = COMPLETE（UE 层 rescan 待编辑器重启）

DEPRECATED_BACKUP_ASSETS  = 0（_Archive 备份已删；PoseRecorder_Proto 非本次范围 → REVIEW）
DEPRECATED_ARCHIVE_ASSETS = 0（本次 reset 相关）
DEPRECATED_ACTIVE_ASSETS  = 0（FutsalHuman V1 / JerseyNumber V1 / Appearance V1 均已删）
DEPRECATED_TEST_ASSETS    = 0（FutsalHuman / JerseyNumber / Appearance 相关测试资产已删）
APPEARANCE_SYSTEM = REMOVED
```

---

# Phase RESET++E — Post-Crash Asset Registry Reconciliation

- 阶段：编辑器崩溃后重启的**核对 / 验证**阶段（无新架构改动）。
- 事实：上次清理期间 UnrealEditor 在切换关卡时崩溃；多数资产经 UE API 删除，最后两个 pinned 资产（Appearance BP + 测试地图）在崩溃后由文件系统硬删除。本阶段已重启编辑器并重新扫描 Asset Registry 完成核对。

## RESETE.1 重启后基线

- 编辑器已重启（UnrealEditor PID 12704，启动 2026-09-24 13:00）；MCP（`http://127.0.0.1:8000/mcp`）重连成功；`PIE = stopped`。
- git：`refactor/character-architecture` @ `99a9b758`；`git status --short`：8 个 ` D`（Appearance 资产 + 测试地图）、1 个 ` M`（`UNREAL_RIG.uasset`，预存）、`??` 本审计文档。

## RESETE.2 核对结果

```
ASSET_REGISTRY_RETIRED_ASSET_COUNT  = 0   （15 个代表路径 does_asset_exist 全 false；Appearance 资产数 = 0）
RESIDUAL_RETIRED_PACKAGE_REFERENCES = 0   （FutsalHuman / JerseyNumber / Appearance 名称与路径搜索命中 = 0）
RETIRED_SYSTEM_REDIRECTORS          = 0   （/Game/FutsalMOT ObjectRedirector = 0）
BROKEN_REMAINING_ASSET_REFERENCES   = 0
ORPHANED_DEPRECATED_PACKAGE_FILES   = 0   （退休路径无 .uasset/.uexp/.ubulk）
UNREGISTERED_RETIRED_PACKAGE_FILES  = 0
RETIRED_AUTOSAVE_ARTIFACTS          = 0   （Saved/Autosaves 无退休系统相关文件）
RETIRED_SYSTEM_ARCHIVE_ASSETS       = 0   （_Archive 仅剩 BP_PoseRecorder_Proto）
SOURCE_CHARACTER_PIPELINE           = PRESERVED（BP_FutsalCharacterBase / ABP_FutsalSource / IKR_Quinn / SK_Mannequin / SKM_Quinn_Simple / BS_Futsal_Locomotion 均解析）
ACTIVE_TESTS                        = PRESERVED（GM_FutsalInputTest / L_FutsalCharacterBase_Test）
APPEARANCE_SYSTEM                   = REMOVED
```

- `Content/FutsalMOT/**`（排除 `code/`）文件系统无退休命名文件、无孤儿二进制、退休目录均不存在。
- 清理后 `/Game/FutsalMOT/`：**1251** 资产（1154 在 `code/` 子模块；**97** 在其余内容树）/ **27** 文件夹（不含 `code/`）。

## RESETE.3 保留项与 Git

- `/Game/FutsalMOT/_Archive/AbandonedExperiments/BP_PoseRecorder_Proto` → `REVIEW_REQUIRED`（Pose Recorder 系统，非本次 reset 范围；本阶段未删 / 未移动）。
- 无 git restore / checkout / revert；未 stage / commit / tag / push；`UNREAL_RIG.uasset` 仍为同一预存未解决改动。

---

# Phase CLEANUP-2 — Soccer/Futsal Naming Canonicalization + Legacy Architecture Audit

- 阶段：只读审计 + 小范围安全硬删除（未做破坏性重命名 / 移动）。
- 标准：`PROJECT_DOMAIN_TERM = Futsal`；`PROJECT_ARCHITECTURE_SOCCER_NAMING = RETIRED`；`DEPRECATED_ASSET_POLICY = HARD_DELETE`、`BACKUP_POLICY = NONE`、`UE_ARCHIVE_POLICY = NONE`。

## CLEANUP2.1 三条 legacy 分支的真实语义

- `Animation/SoccerSource/**`（7 × AnimSequence，SK_Mannequin）：**0 referencer** → 冗余 source 克隆。
- `Animation/SoccerPlayer/**`（ABP_FutsalPlayer_Soccer + BS_Futsal_Locomotion_Soccer + 20 AnimSequence，全部 `UNREAL_RIG_Skeleton`）：legacy UNREAL_RIG 目标动画管线；唯一外部使用者为 `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter_Soccer`（其自身 0 referencer）。
- `Characters/FutsalPlayer/**`：`BP_SoccerPlayer`（0 referencer）+ `ABP_SoccerPlayer`（← BP_SoccerPlayer）+ 受保护 `UNREAL_RIG`（SkeletalMesh，外部未解决）+ `UNREAL_RIG_Skeleton` + 8 材质 + 5 贴图（材质/贴图 ← UNREAL_RIG）。
- 关联：`Animation/Retarget/IKR_SoccerPlayer`、`RTG_Quinn_To_SoccerPlayer`（← UNREAL_RIG）。
- 根级 `Animation/ABP_FutsalPlayer`（SK_Mannequin）← `/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter`（← GameMode ← 模板地图 `Lvl_ThirdPerson`）。

## CLEANUP2.2 活跃（canonical）动画 / 角色图

```
Engine Mannequin clips (/Game/Characters/Mannequins/Anims/Unarmed/...)
  → BS_Futsal_Locomotion (SK_Mannequin)
  → ABP_FutsalSource
  → BPI_FutsalAnimationSource → BP_FutsalCharacterBase
  → L_FutsalCourt / L_FutsalCharacterBase_Test
```

## CLEANUP2.3 已硬删除（HARD_DELETE = 8）

- `Animation/SoccerSource/LS_*`（7，0 referencer）→ **DELETED**
- `_Archive/AbandonedExperiments/BP_PoseRecorder_Proto`（deps=[]、refs=[] 空壳原型；与在用 `Blueprints/Pose/Recorder/BP_PoseRecorderC4_G*` 无关联）→ **DELETED**
- 空目录 `Animation/SoccerSource/`、`_Archive/AbandonedExperiments/`、`_Archive/` → 已移除

## CLEANUP2.4 移动 / 重命名 = 0（MOVE_DEFERRED / REVIEW_REQUIRED）

- 未做任何 AssetTools 重命名 / 移动：
  - `BS_Futsal_Locomotion`（位于 `Animation/` 根）被受保护 `ABP_FutsalSource` 引用；移动将强制 resave 受保护资产 → `MOVE_DEFERRED`。
  - `SoccerPlayer/**`、`Characters/FutsalPlayer/{ABP_SoccerPlayer, BP_SoccerPlayer, UNREAL_RIG_Skeleton, Materials, Textures}`、`IKR_SoccerPlayer`、`RTG_Quinn_To_SoccerPlayer`、根级 `ABP_FutsalPlayer`：被 `/Game/ThirdPerson` 模板 BP（`BP_ThirdPersonCharacter`、`BP_ThirdPersonCharacter_Soccer`）与受保护 `UNREAL_RIG` 耦合；删除 / 改名会破坏 ThirdPerson 模板或产生悬空引用 → `REVIEW_REQUIRED`（需专用阶段连同 ThirdPerson soccer BP 一并处理，或用户授权）。

```
PROJECT_ARCHITECTURE_SOCCER_NAMED_ASSETS = 26
  （SoccerPlayer 22 + ABP_SoccerPlayer + BP_SoccerPlayer + IKR_SoccerPlayer + RTG_Quinn_To_SoccerPlayer）
  例外：Football/StaticMeshes/soccer_ball（足球道具网格，非角色 / 动画架构命名）
REVIEW_REQUIRED_ASSET_COUNT = 41
```

## CLEANUP2.5 保护资产 / 校验

```
BROKEN_REMAINING_ASSET_REFERENCES = 0
CLEANUP_REDIRECTORS_REMAINING = 0
UNREAL_RIG.uasset / L_FutsalCourt / BP_FutsalCharacterBase / ABP_FutsalSource / IKR_Quinn = UNCHANGED_FROM_BASELINE
FUTSALPLAYER_FOLDER_RETAINED_ONLY_FOR_PROTECTED_EXTERNAL_ASSET = YES
```

- 清理后 `/Game/FutsalMOT/`：**1243** 资产（1154 在 `code/`；**89** 在其余内容树）/ **26** 文件夹（不含 `code/`）。

---

# Phase CLEANUP-3 — Legacy Soccer Runtime Chain Retirement + ThirdPerson Template Decoupling

- 阶段：硬删除 legacy Soccer 运行时链 + 退役未使用 ThirdPerson 模板 + 最小化受保护 UNREAL_RIG 依赖岛。
- 标准：`PROJECT_DOMAIN_TERM = Futsal`、`PROJECT_ARCHITECTURE_SOCCER_NAMING = RETIRED`、`DEPRECATED_ASSET_POLICY = HARD_DELETE`、`BACKUP_POLICY = NONE`、`UE_ARCHIVE_POLICY = NONE`。

## CLEANUP3.1 ThirdPerson 模板判定与删除

- `/Game/ThirdPerson` 资产：`BP_ThirdPersonCharacter`、`BP_ThirdPersonCharacter_Soccer`（refs=0）、`BP_ThirdPersonGameMode`、`BP_ThirdPersonPlayerController`、`Lvl_ThirdPerson`、`MI_ThirdPersonColWay`。
- 引用方向：仅 `Animation/ABP_FutsalPlayer`、`Animation/SoccerPlayer/ABP_FutsalPlayer_Soccer` → `BP_ThirdPersonCharacter`；**没有任何 FutsalMOT 生产资产依赖 ThirdPerson**；`Lvl_ThirdPerson` 非默认地图。
- `THIRDPERSON_TEMPLATE_PROJECT_USAGE = UNUSED_TEMPLATE` → **HARD_DELETE_TEMPLATE**：删除全部 6 个 ThirdPerson 资产（含 `Lvl_ThirdPerson` 地图）及其 WorldPartition 外部 actor / object 包（`__ExternalActors__/ThirdPerson`、`__ExternalObjects__/ThirdPerson`，以及遗留孤儿 `__ExternalActors__/FutsalMOT/Maps/Lvl_ThirdPerson`）。

## CLEANUP3.2 硬删除 legacy Soccer 运行时链（HARD_DELETE）

- `Animation/SoccerPlayer/**`（ABP_FutsalPlayer_Soccer + BS_Futsal_Locomotion_Soccer + 20 × `*_Soccer` 序列）→ **DELETED**
- `Animation/ABP_FutsalPlayer` → **DELETED**
- `Characters/FutsalPlayer/BP_SoccerPlayer`、`Characters/FutsalPlayer/ABP_SoccerPlayer` → **DELETED**
- `Animation/Retarget/IKR_SoccerPlayer`、`RTG_Quinn_To_SoccerPlayer` → **DELETED**
- 空目录 `Animation/SoccerPlayer/`、`ThirdPerson/` → 已移除

## CLEANUP3.3 受保护 UNREAL_RIG 依赖岛（最小化 Characters/FutsalPlayer）

- 删除未引用 legacy：`MI_Player_TShirt_Red`、`MI_Player_TShirt_Test`、`M_Player_TShirt_Master`。
- 保留（UNREAL_RIG 依赖闭包，`PROTECTED_EXTERNAL_DEPENDENCY_CLOSURE`）：`UNREAL_RIG_Skeleton` + `M_Player_{Hand,Head,Leg,Shorts,T-ShirtFull}` + `Textures/{HAND,HEAD,LEG,SHORTS,T_SHIRT_FULL_}`。
- `PROTECTED_UNREAL_RIG_DEPENDENCY_ASSET_COUNT = 11`（不含 `UNREAL_RIG` 本体）。
- `UNREAL_RIG` 未修改 / 未保存 / 未移动；其 Skeleton + 5 材质 + 5 贴图全部解析。

## CLEANUP3.4 校验

```
CLEANUP_REDIRECTORS_REMAINING = 0
BROKEN_REMAINING_ASSET_REFERENCES = 0
LEGACY_SOCCER_RUNTIME_ARCHITECTURE = REMOVED
THIRDPERSON_TEMPLATE = REMOVED
UNREAL_RIG_DEPENDENCY_INTEGRITY = PASS
FUTSALPLAYER_FOLDER_RETAINED_ONLY_FOR_PROTECTED_EXTERNAL_ASSET = YES
BS_FUTSAL_LOCOMOTION_LOCATION = LEGACY_BUT_ACCEPTED
  （仍在 Animation/ 根；移动会强制 resave 受保护 ABP_FutsalSource → 不做）
```

- 清理后 `/Game/FutsalMOT/`：**1213** 资产（1154 在 `code/`；**59** 在其余内容树）。
- 活跃动画/角色图：`Engine Mannequin clips → BS_Futsal_Locomotion → ABP_FutsalSource → BPI_FutsalAnimationSource → BP_FutsalCharacterBase → L_FutsalCourt / L_FutsalCharacterBase_Test`。
- 剩余 legacy 运行时图：**NONE**（`UNREAL_RIG` 及其被动依赖不构成运行时图，属受保护外部资产岛）。
## Phase BASE-1D — FutsalPlayerBase Self-Contained Migration

- 日期：2026-09-24
- 基线：branch `refactor/character-architecture` @ `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`
- 阶段结论：`PARTIAL`。已确认手工创建的 SkeletalMesh 绑定到项目自有 Skeleton，并完成部分安全的依赖内部化；未迁移动画、Blueprint、Retarget Rig 或更新活动引用，未删除旧 canonical 资产。
- PIE：未运行。
- Git 基线已有大量删除、`UNREAL_RIG.uasset` 修改、FutsalPlayerBase 未跟踪目录和本文档未跟踪状态。本阶段未 stage、commit、tag 或 push。未修改或保存 `UNREAL_RIG.uasset`。

### Foundation 与依赖图

- 手工创建资产：`/Game/FutsalMOT/Characters/FutsalPlayerBase/Mesh/SKM_FutsalPlayerBase` 和 `/Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase`。
- 首要绑定检查：PASS，`SKM_FutsalPlayerBase.Skeleton = SK_FutsalPlayerBase`。
- 新 Mesh 查询到 91 根骨骼、3 个 LOD、0 个 morph target、2 个材质槽（`Quinn_01`、`Quinn_02`）。原 `SKM_Quinn_Simple` 有 157 根骨骼，包含额外 corrective/helper 骨；未更改新 Mesh 骨骼数据。
- 新 Skeleton 依赖新 Mesh；新 Mesh 原始直接依赖包含 `PA_Mannequin`、`CR_Mannequin_Body`、`MI_Quinn_01`、`MI_Quinn_02` 及新 Skeleton。
- 分类：内部资产为 `SKM_FutsalPlayerBase`、`SK_FutsalPlayerBase`；外部 Mannequin 为上述 PhysicsAsset、ControlRig、材质实例和其材质/纹理依赖；父材质依赖的 `/Engine/Functions/...` 属于 Engine 内容；无 `/Game/ThirdPerson` 依赖。

### 已执行的内部化操作

| 来源 | 目标 / 操作 | 结果 |
|---|---|---|
| `/Game/Characters/Mannequins/Rigs/PA_Mannequin` | 由新 Mesh 生成 `/Game/FutsalMOT/Characters/FutsalPlayerBase/Mesh/PHYS_FutsalPlayerBase` 并自动赋给新 Mesh | PASS；PhysicsAsset 仅依赖新 Mesh；原资产未改 |
| `/Game/Characters/Mannequins/Materials/M_Mannequin` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Materials/M_FutsalPlayerBase_Master` | 已复制，尚有 Manny/共享 Logo 外部纹理图依赖 |
| `MI_Quinn_01`、`MI_Quinn_02` | `MI_FutsalPlayerBase_01`、`MI_FutsalPlayerBase_02`；父材质改为项目自有 Master，纹理参数指向项目自有 Quinn 纹理副本 | 操作成功；Asset Registry 仍报告原 Quinn 纹理引用，需重新打开/重新保存核查 |
| Quinn 01/02 的 D、MRA、N 六张纹理 | `Textures/T_FutsalPlayerBase_01_*` 和 `_02_*` | 已复制并用于实例参数 |
| Manny BN、MRA 及共享 Logo 纹理 | 对应 `T_FutsalPlayerBase_Manny_01_BN`、`_MRA`、`T_FutsalPlayerBase_UE_Logo_M` | 已复制；Manny D 纹理复制调用未执行成功 |
| `SKM_FutsalPlayerBase` 默认 Animating Rig | 清空 editor-only `defaultAnimatingRig` | 实时对象确认清空；Mesh 的材质槽已设为两个内部实例 |

### 阻断门

**`MANUAL_GATE_REQUIRED = COPY_M_Mannequin_MATERIAL_GRAPH`**

精确资产：`/Game/Characters/Mannequins/Materials/M_Mannequin` 及其当前 graph 依赖 `T_Manny_01_BN`、`T_Manny_01_D`、`T_Manny_01_MRA`、`T_UE_Logo_M`。Agent 已通过 UE Python 验证 Material 的 `Expressions` 属性受保护，无法以受支持接口遍历并安全重连纹理节点；不得以二进制/property hack 继续。请在 Unreal Editor 的 Material Editor 中将源 Material 复制到 `M_FutsalPlayerBase_Master`，并将 graph 引用替换为上述 `FutsalPlayerBase/Textures` 内部副本（D 纹理如需则先在 Content Browser 复制）；完成后 Agent 可继续自动验证与后续迁移。当前实例参数已内部化，但注册表仍包含旧 Quinn 纹理路径，因此不能将当前图声明为零外部依赖。

本阶段未到达并且未尝试以下破坏性/高影响步骤：动画序列 retarget、BlendSpace/IK Rig/AnimBlueprint/接口/Character Blueprint/controller 迁移、活动 referencer 改写、runtime 测试、旧 canonical hard-delete、redirector 清理。特别是 `ABP_FutsalSource` 当前目标 Skeleton 为外部 `SK_Mannequin`；在图与重定向 API 可确认前不得复制并二进制改目标 Skeleton。旧资产全部保留。

### 当前映射与图

| 当前旧/外部资产 | 当前目标 | 状态 |
|---|---|---|
| `SKM_Quinn_Simple`（仅作对照） | `SKM_FutsalPlayerBase` | 新 Mesh 已绑定 `SK_FutsalPlayerBase`；reference 骨骼数不同（157 对 91） |
| `PA_Mannequin` | `PHYS_FutsalPlayerBase` | 已生成并赋值 |
| `M_Mannequin` | `M_FutsalPlayerBase_Master` | 已复制，graph 仍有外部 Manny/Logo 纹理依赖，阻断 |
| `MI_Quinn_01/02` | `MI_FutsalPlayerBase_01/02` | 已复制、换父、设置内部纹理参数；待 registry 清洁验证 |
| Quinn 六张 D/MRA/N 纹理 | 六张 `T_FutsalPlayerBase_01/02_*` | 已复制 |
| Manny BN、MRA、UE Logo | 对应 `T_FutsalPlayerBase_*` 副本 | 已复制；并非已证明新 mesh runtime closure 必需，因 Master graph 尚待修复 |
| `CR_Mannequin_Body` | 无 | Mesh editor-only 默认 Rig 引用已清空，不内部化 |
| 旧动画、BlendSpace、IK Rig、ABP、BPI、Character BP、Controller | 无 | 未迁移 |

当前可确认图：`SKM_FutsalPlayerBase -> SK_FutsalPlayerBase + PHYS_FutsalPlayerBase + MI_FutsalPlayerBase_01/02`；两个 MI 指向内部 Master 和内部参数纹理。Master 仍直接依赖 `/Game/Characters/Mannequins/Textures/Manny/*` 与 `Textures/Shared/T_UE_Logo_M`。`PHYS_FutsalPlayerBase -> SKM_FutsalPlayerBase`。完整角色 runtime graph 尚未建立。

### 最终状态（本次停止点）

```text
PHASE_FUTSALPLAYERBASE_SELF_CONTAINMENT = PARTIAL
MANUAL_GATE_REQUIRED = COPY_M_Mannequin_MATERIAL_GRAPH
SKM_FUTSALPLAYERBASE_SKELETON_BINDING = PASS
SK_FUTSALPLAYERBASE = PASS
PHYS_FUTSALPLAYERBASE = PASS
INTERNAL_MATERIAL_COUNT = 3
INTERNAL_TEXTURE_COUNT = 10 (其中一张 Manny D 源纹理副本调用失败)
INTERNAL_ANIMATION_SEQUENCE_COUNT = 0
CONTROL_RIG_INTERNALIZATION = NOT_REQUIRED_FOR_MESH; ABP audit not reached
BS_FUTSALPLAYERBASE_LOCOMOTION = FAIL (not migrated)
ABP_FUTSALPLAYERBASE = FAIL (not migrated)
BPI_FUTSALPLAYERBASEANIMATION = FAIL (not migrated)
IKR_FUTSALPLAYERBASE = FAIL (not migrated)
BP_FUTSALPLAYERBASE = FAIL (not migrated)
FUTSALPLAYERBASE_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = >0 (material closure; full BP closure not built)
FUTSALPLAYERBASE_MANNEQUIN_CONTENT_DEPENDENCIES = >0
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0 (new mesh closure)
LEGACY_BASE_SYSTEM_ASSET_NAMES = not audited
OLD_CANONICAL_ASSET_COUNT = not retired
FUTSALPLAYERBASE_REDIRECTORS = not audited
BROKEN_REMAINING_ASSET_REFERENCES = not audited
FUTSALPLAYERBASE_RUNTIME_VALIDATION = NOT_REACHED
UNREAL_RIG_STATUS = CHANGED (already modified at baseline; hash f87733cfad0e524035150f9defa6ad08a4b77238 differs from HEAD blob 99a0003ecd7456b305fb416bec696f973104a3ef)
UNREAL_RIG_DEPENDENCY_INTEGRITY = NOT_RECHECKED; no writes to the asset made
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

`CURRENT_NEW_MESH_EXTERNAL_DEPENDENCY_GRAPH`: before edits, Mesh -> `PA_Mannequin`, `CR_Mannequin_Body`, `MI_Quinn_01`, `MI_Quinn_02`, internal Skeleton. After safe edits, live UObject values show internal PhysicsAsset/material instances and no default animating rig, but registry material graph dependencies remain external pending the gate.

`FUTSALPLAYERBASE_CONTENT_TREE`: only the two manually supplied Mesh/Skeleton assets plus the above generated PhysicsAsset, 3 Materials, and copied Textures; created `Materials/`, `Textures/`, and `Animation/` folders. No Blueprint or animation assets were migrated.

`PROTECTED_UNREAL_RIG_ASSET_ISLAND`: remained untouched by this phase; its pre-existing modified status was recorded, file contents were not saved/resaved or otherwise changed by UE operations.

`ANY_REMAINING_EXTERNAL_DEPENDENCIES`: Mannequin master graph textures and stale Quinn material references remain; full canonical runtime closure is incomplete. Engine material function dependencies are expected and allowed.

## Phase BASE-1E-PRECHECK — Exact Texture Replacement Map (READ-ONLY)

- 日期：2026-09-24
- 范围：只读查询 FutsalPlayerBase Master、其依赖和 Mesh 当前材质实例。没有修改、保存、重命名、移动、复制、删除或编译任何资产；没有 stage/commit/tag/push。
- `UNREAL_RIG.uasset` 的 hash 本次前后未重新写入；初始 hash 为 `f87733cfad0e524035150f9defa6ad08a4b77238`，工作区原有修改状态保留。

### Texture inventories

内部 Texture2D 共 9 个（Asset Registry 的本目录当前枚举结果；此前“10 个”计数不再符合 live 状态）：

| Asset name | Object path | Class | Dimensions | Source filename | Compression | sRGB | Virtual texture |
|---|---|---|---|---|---|---|---|
| `T_FutsalPlayerBase_01_D` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_D.T_FutsalPlayerBase_01_D` | Texture2D | 1024x1024 | unavailable (import data empty) | TC_Default | true | false |
| `T_FutsalPlayerBase_01_MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_MRA.T_FutsalPlayerBase_01_MRA` | Texture2D | 1024x1024 | unavailable | TC_Default | false | false |
| `T_FutsalPlayerBase_01_N` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_N.T_FutsalPlayerBase_01_N` | Texture2D | 1024x1024 | unavailable | TC_Normalmap | false | false |
| `T_FutsalPlayerBase_02_D` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_D.T_FutsalPlayerBase_02_D` | Texture2D | 1024x1024 | unavailable | TC_Default | true | false |
| `T_FutsalPlayerBase_02_MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_MRA.T_FutsalPlayerBase_02_MRA` | Texture2D | 1024x1024 | unavailable | TC_Default | false | false |
| `T_FutsalPlayerBase_02_N` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_N.T_FutsalPlayerBase_02_N` | Texture2D | 1024x1024 | unavailable | TC_Normalmap | false | false |
| `T_FutsalPlayerBase_Manny_01_BN` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_Manny_01_BN.T_FutsalPlayerBase_Manny_01_BN` | Texture2D | 1024x1024 | unavailable | TC_Normalmap | false | false |
| `T_FutsalPlayerBase_Manny_01_MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_Manny_01_MRA.T_FutsalPlayerBase_Manny_01_MRA` | Texture2D | 1024x1024 | unavailable | TC_Default | false | false |
| `T_FutsalPlayerBase_UE_Logo_M` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_UE_Logo_M.T_FutsalPlayerBase_UE_Logo_M` | Texture2D | 1024x1024 | `E:/temp/Masculine/T_UE_Logo_V2.BMP` | TC_Grayscale | false | false |

Texture list output and texture metadata tags established asset names, classes, dimensions, compression, sRGB, and virtual-texture state. Internal Manny D texture is absent. Source filename was empty/unavailable for other copies. Pixel/data hashes were not read.

### Master dependency and replacement map

AssetTools reports the Master’s external Mannequin texture dependencies as four assets. Paths below are full object paths, not inferred from names. Manny BN, Manny MRA, and UE Logo have internal counterparts whose dimensions and relevant source/internal texture settings match exactly. `T_Manny_01_D` has no internal replacement in the current inventory.

| MATERIAL_ASSET | NODE_TEXTURE_CURRENT | CURRENT_EXTERNAL_PATH | REPLACE_WITH_INTERNAL_PATH | MATCH_CONFIDENCE | NOTES |
|---|---|---|---|---|---|
| `/Game/FutsalMOT/Characters/FutsalPlayerBase/Materials/M_FutsalPlayerBase_Master.M_FutsalPlayerBase_Master` | `T_Manny_01_BN` | `/Game/Characters/Mannequins/Textures/Manny/T_Manny_01_BN.T_Manny_01_BN` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_Manny_01_BN.T_FutsalPlayerBase_Manny_01_BN` | HIGH | 1024x1024; TC_Normalmap; sRGB false; virtual texture false; CharacterNormalMap group; wrap. Copy provenance is consistent with name transformation, but source path/pixel hash unavailable. |
| same | `T_Manny_01_D` | `/Game/Characters/Mannequins/Textures/Manny/T_Manny_01_D.T_Manny_01_D` | none | NO_MATCH | No internal Manny D asset exists in the live internal texture inventory. Existing Quinn D copies have matching broad 1024x1024/TC_Default/sRGB traits only; they are not evidence of a content-identical replacement. |
| same | `T_Manny_01_MRA` | `/Game/Characters/Mannequins/Textures/Manny/T_Manny_01_MRA.T_Manny_01_MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_Manny_01_MRA.T_FutsalPlayerBase_Manny_01_MRA` | HIGH | 1024x1024; TC_Default; sRGB false; virtual texture false; CharacterSpecular group; wrap. Matching metadata and name transform; pixel hash unavailable. |
| same | `T_UE_Logo_M` | `/Game/Characters/Mannequins/Textures/Shared/T_UE_Logo_M.T_UE_Logo_M` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_UE_Logo_M.T_FutsalPlayerBase_UE_Logo_M` | EXACT | Source and internal share `E:/temp/Masculine/T_UE_Logo_V2.BMP`, dimensions and settings; exact duplicated source provenance. |

Master parameter enumeration includes `Logo?`, `LogoTint`, `LogoPosX`, `LogoPosY`, `LogoScale`, `Base Texture`, `BNormal`, and `MRA`. This supports that the Master exposes an optional-logo parameter branch, but API access to material expressions/wiring is protected; whether `T_UE_Logo_M` is currently connected only to that branch and whether the static switch currently activates it are **UNKNOWN**. It is an actual Master dependency, so do not bypass/delete graph nodes. Exact internal logo copy exists and is the replacement.

`MANUAL_REPLACEMENT_BLOCKED = YES`; unresolved Master texture: `/Game/Characters/Mannequins/Textures/Manny/T_Manny_01_D.T_Manny_01_D`.

### Master use versus other Manny/Quinn candidates

- `USED_BY_MASTER` (confirmed via dependency graph): Manny 01 BN, Manny 01 D, Manny 01 MRA, shared UE logo mask.
- `USED_ONLY_BY_MATERIAL_INSTANCE` (confirmed assigned external values on source Quinn instances; current target copies override with internal textures): Quinn 01 D/MRA/N and Quinn 02 D/MRA/N.
- `NOT_CURRENTLY_USED` in the audited Master/assigned mesh MI set: Manny 02 D/MRA/BN. They were not reported as Master dependencies, and no audited instance value pointed at them.
- The Master dependency API does not expose graph nodes, so per-node connection and conditional reachability remain unknown; “used by Master” means dependency graph membership, not proof the optional branch evaluates at runtime.

### Material instance texture parameter map

| INSTANCE_PATH | PARENT_MATERIAL | TEXTURE_PARAMETER_NAME | CURRENT_TEXTURE_VALUE | WHETHER_CURRENT_TEXTURE_IS_EXTERNAL | INTENDED_INTERNAL_REPLACEMENT |
|---|---|---|---|---|---|
| `/Game/FutsalMOT/Characters/FutsalPlayerBase/Materials/MI_FutsalPlayerBase_01.MI_FutsalPlayerBase_01` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Materials/M_FutsalPlayerBase_Master.M_FutsalPlayerBase_Master` | `Base Texture` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_D.T_FutsalPlayerBase_01_D` | no | same current internal texture |
| same | same | `MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_MRA.T_FutsalPlayerBase_01_MRA` | no | same current internal texture |
| same | same | `BNormal` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_01_N.T_FutsalPlayerBase_01_N` | no | same current internal texture |
| `/Game/FutsalMOT/Characters/FutsalPlayerBase/Materials/MI_FutsalPlayerBase_02.MI_FutsalPlayerBase_02` | Master above | `Base Texture` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_D.T_FutsalPlayerBase_02_D` | no | same current internal texture |
| same | same | `MRA` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_MRA.T_FutsalPlayerBase_02_MRA` | no | same current internal texture |
| same | same | `BNormal` | `/Game/FutsalMOT/Characters/FutsalPlayerBase/Textures/T_FutsalPlayerBase_02_N.T_FutsalPlayerBase_02_N` | no | same current internal texture |

The source `MI_Quinn_01/02` parameters were separately queried and return external Quinn 01/02 D/MRA/N values, respectively. For those original assets the one-to-one internal copies follow their distinct 01/02 names. For current FutsalPlayerBase MIs, all six values are active internal parameter values.

`STALE_SOURCE_TEXTURE_REFERENCE_ANALYSIS`: AssetTools dependency results for current MIs still list the original external Quinn texture assets even though `get_texture_parameter` returns internal texture object paths for all three parameters on both MIs. Therefore those results are **not active parameter values**. They are consistent with stale registry/serialized inherited dependency metadata, but current APIs cannot distinguish `STATIC_DEPENDENCY_METADATA` from `STALE_REGISTRY_REFERENCES`; classify as `UNKNOWN (registry-only source references)`, not definitively stale. Master’s Manny references are current Master-level dependencies, not explained by MI parameter state.

```text
READ_ONLY_TEXTURE_MAPPING_AUDIT = COMPLETE
EXTERNAL_MASTER_TEXTURE_COUNT = 4
INTERNAL_TEXTURE_COUNT = 9
MANUAL_REPLACEMENT_BLOCKED = YES
```

No asset operation followed this read-only audit.

## Phase BASE-1G — Clean Material Closure and BASE-1D Resume

- 日期：2026-09-24
- Clean Master graph verified: effective textures and Asset Registry dependencies are project-owned; Engine material functions remain the only non-project dependencies.
- Source/Clean material semantics matched for domain, blend mode, shading model, two-sided, opacity clip, dither, decal response, tangent-space normal, material attributes, and parameter-name schema. Clean Master compilation returned zero errors. SkeletalMesh usage was enabled on the clean Master through `MaterialEditingLibrary.set_base_material_usage`.
- Existing contaminated MIs were fully captured for scalar, vector, texture, font, RVT, sparse-volume, collection, and static-switch state. New MIs were rebuilt from scratch with clean parent and internal texture overrides, assigned to `SKM_FutsalPlayerBase` in original slot order. Old Master and old MIs were hard-deleted only after clean closure verification; clean packages were renamed to canonical names. No `_Clean` material candidates remain.
- Final material mesh closure at this gate: Mesh -> `SK_FutsalPlayerBase`, `PHYS_FutsalPlayerBase`, `MI_FutsalPlayerBase_01/02`; MIs -> canonical clean Master and internal 01/02 textures. No Mannequin material/texture dependency remains.
- Active BlendSpace audit found 27 samples and 17 unique source sequences. IK retargeting created 17 target `AnimSequence` assets under `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/`; all verified as `AnimSequence` assets bound to `SK_FutsalPlayerBase`, with source sequence durations retained by retarget output.
- Created `IKR_FutsalPlayerBase` and generated target `IKR_FutsalPlayerBase_Target` from `SKM_FutsalPlayerBase`; source/target preview and target rig assignment succeeded. The IKR still references source `IKR_Quinn` and therefore is not yet a zero-external closure.

### Current GUI/API gate

`MANUAL_GATE_REQUIRED = POPULATE_BS_FUTSALPLAYERBASE_LOCOMOTION_SAMPLES`

The source BlendSpace sample data is readable through UE Python, including all 27 coordinates, rate scales, and source animation paths. In this UE 5.8 build, the `BlendSpace` Python object has no supported sample mutation method; `add_sample` is unavailable and no sample-editing method is exposed. A temporary target BlendSpace was created during probing but had zero samples and was deleted. No incomplete canonical BlendSpace remains.

Exact target: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/BlendSpaces/BS_FutsalPlayerBase_Locomotion`.

The user must create/populate the target BlendSpace using the captured source sample coordinates, assigning the 17 internal sequences named `A_FutsalPlayerBase_*`, preserve the source axis/interpolation settings, compile/save, then close the editor. No MaterialInstance manual work is required. After this gate, Agent can verify the BlendSpace, continue IKR cleanup/validation, and proceed to BPI/ABP/character Blueprint migration.

## Phase BASE-1H-PROBE — Automated BlendSpace Retarget Probe

- 日期：2026-09-24
- Live `IKRetargetBatchOperation.run_batch_retarget` accepted a BlendSpace input. The disposable probe created one retargeted BlendSpace and 17 dependent target AnimSequences under `_MigrationProbe`.
- Probe BlendSpace verification: `27` samples, `17` unique animations, exact sample coordinates and rate scales, target skeleton `SK_FutsalPlayerBase`. All probe animations were valid AnimSequences on the target skeleton with no `/Game/Characters/Mannequins/` dependency.
- Existing canonical target sequences and probe sequences matched for all 17 semantic pairs on target skeleton, duration, and rate scale. Root/articulation pixel-level comparison was not required because the retarget operation was identical and both sets shared target skeleton/duration/rate; no claim of full pixel equivalence is made.
- The probe-generated BlendSpace was promoted to `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/BlendSpaces/BS_FutsalPlayerBase_Locomotion`.
- The probe-generated animation library was promoted as the single canonical library under `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_*`; the previous duplicate canonical library was verified without referencers and hard-deleted before promotion. No duplicate target library remains.
- Probe cleanup: the temporary `BS_Probe` asset was already absent after the promotion operation; `_MigrationProbe` contains no remaining assets. Canonical BlendSpace has no `_MigrationProbe` sample references.
- Final canonical BlendSpace dependencies are target Skeleton, target mesh preview, and the 17 canonical target sequences. No Mannequin content dependency remains in the BlendSpace closure.

```text
BLENDSPACE_BATCH_RETARGET_SUPPORTED = YES
BLENDSPACE_BATCH_RETARGET_RESULT = PASS
SOURCE_BLENDSPACE_SAMPLE_COUNT = 27
PROBE_BLENDSPACE_SAMPLE_COUNT = 27
SOURCE_UNIQUE_ANIMATION_COUNT = 17
PROBE_UNIQUE_ANIMATION_COUNT = 17
BLENDSPACE_SAMPLE_LAYOUT_MATCH = PASS
PROBE_TARGET_SKELETON = /Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase
PROBE_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
EXISTING_VS_PROBE_ANIMATION_EQUIVALENCE = PASS (skeleton/duration/rate; deeper pose equivalence not claimed)
BS_FUTSALPLAYERBASE_LOCOMOTION = PASS
BLENDSPACE_PROBE_ARTIFACTS_REMAINING = 0
MANUAL_GATE_REQUIRED = NONE
```
## Phase BASE-1I — FutsalPlayerBase Runtime Architecture Completion (stopped at ABP rebind gate)

- 日期：2026-09-24
- Live baseline: branch `refactor/character-architecture`, HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`; PIE stopped; active level `/Game/FutsalMOT/Maps/L_FutsalCourt`.
- Material closure remained PASS. The canonical mesh now references canonical internal material instances. No old runtime asset was deleted in this phase.
- Duplicated canonical assets created transactionally: `BPI_FutsalPlayerBaseAnimation`, `ABP_FutsalPlayerBase`, `BP_FutsalPlayerBase`, and `BP_FutsalPlayerControllerBase`. A transactional source IKR duplicate was removed because the already-created canonical IKR/target IKR pair is sufficient.
- `ABP_FutsalPlayerBase` target Skeleton was safely changed to `SK_FutsalPlayerBase`; the duplicated AnimGraph BlendSpace node was redirected to `BS_FutsalPlayerBase_Locomotion`; four sequence players were redirected to internal target sequences; Blueprint compilation returned success.
- Remaining ABP dependency audit still reports `CR_Mannequin_FootIK` and `BPI_FutsalAnimationSource`. The copied FootIK ControlRig also retains serialized Mannequin graph/function references and preview `SKM_Manny_Simple`.

### Exact unsupported rebind gate

`MANUAL_GATE_REQUIRED = ABP_CONTROL_RIG_AND_INTERFACE_REBIND`

The current UE 5.8 Python API exposes only deprecated `AnimNode_ControlRig.ControlRigClass` / `DefaultControlRigClass` fields and refuses both read and write (`Property ... is deprecated`). The copied ControlRig’s generated metadata still references the source `CR_Mannequin_FootIK` function library and its preview mesh remains `SKM_Manny_Simple`. The ABP graph’s interface dependency is serialized and no supported Blueprint/AnimBlueprint API was found to replace the interface reference safely.

No character Blueprint defaults or active referencers were changed. No old canonical assets were retired. No runtime test was run because the new ABP closure is not yet self-contained. `UNREAL_RIG.uasset` remained untouched; its pre-existing working hash remains `f87733cfad0e524035150f9defa6ad08a4b77238`.
## Phase BASE-1I-INTERFACE-CLEAN — Residual Old Interface Dependency

- 日期：2026-09-24
- Read-only audit of saved `ABP_FutsalPlayerBase`.
- Generated class metadata confirms only `BPI_FutsalPlayerBaseAnimation` is implemented, with `GetMotionSpeedMps` implementation graph preserved.
- Asset Registry still reports one direct package dependency on `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource`; the new interface is present in the ABP generated class metadata.
- Safe Blueprint API inventory exposes `compile_blueprint` and editor refresh methods, but no graph-node reconstruct API. `EdGraph.Nodes` and `EdGraph.Schema` are protected. No refresh/reconstruct/save was attempted in this read-only phase.
- The exact residual node/reference field could not be read safely because graph nodes and schema are protected. The dependency is classified as a function-entry/signature or graph metadata residual associated with `GetMotionSpeedMps`, not as an implemented old interface.

```text
OLD_INTERFACE_DEP_BEFORE_REFRESH = 1
OLD_INTERFACE_DEP_AFTER_REFRESH = 1 (no safe refresh/save attempted)
GETMOTIONSPEEDMPS_ENTRY_BINDING = NEW_INTERFACE (generated class metadata; residual package ref remains)
OLD_INTERFACE_REFERENCE_CLASSIFICATION = FUNCTION_ENTRY
INTERFACE_SERIALIZED_CLEANUP = FAIL
ABP_PACKAGE_DEPENDENCY_CONTAMINATION = UNKNOWN
MANUAL_GATE_REQUIRED = RECREATE_GETMOTIONSPEEDMPS_NEW_INTERFACE_ENTRY
```

Minimal GUI repair: in `ABP_FutsalPlayerBase`, preserve the existing `GetMotionSpeedMps` function body, remove only the old residual interface-bound function implementation/entry if shown by Class Settings or the My Blueprint interface function list, then use `Implement Function` for `BPI_FutsalPlayerBaseAnimation -> GetMotionSpeedMps`, paste/reconnect the existing implementation body, compile, save, and close the editor. Do not rebuild the AnimBlueprint and do not touch the ControlRig in this gate.
## Phase BASE-1J — Clean AnimBlueprint Shell

- 日期：2026-09-24
- Created `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase_Clean` from a new `AnimBlueprintFactory` package targeting `SK_FutsalPlayerBase`; the contaminated ABP was not duplicated or modified.
- Captured all 17 user variables from the live source and recreated them in the clean shell with exact `EdGraphPinType` signatures. Names and all 17 exported types compare equal. All were restored to source category `默认` and replication `NONE`; available source literal defaults were set where supported. Variable exposure/private flags and most generated CDO defaults were not readable through this UE 5.8 API and remain in the GUI transfer classification.
- Clean shell compiled successfully. Registry closure contains only `/Script/AnimGraph` and target `SK_FutsalPlayerBase`. No old BPI, Mannequin, or ThirdPerson dependencies are present.
- UE Python/BlueprintEditorLibrary provides no AnimBlueprint interface-implementation mutator; implemented-interface metadata is not exposed for write. The clean shell therefore requires its sole intended interface to be attached via Class Settings before graph migration.
- Source graph inventory: EventGraph, AnimGraph, state/transition graphs (`Locomotion`, `Idle`, `Walk / Run`, `Main States`, `Jump`, `Fall Loop`, `Land`, repeated `Transition` graphs), and `GetMotionSpeedMps` interface implementation. Macros were not enumerated by the safe API.
- Do-not-copy as-is: old interface-bound `GetMotionSpeedMps` entry/return/signature nodes; old `CR_Mannequin_FootIK` ControlRig node; old `BS_Futsal_Locomotion` BlendSpace; Mannequin Idle/Jump/Fall/Land sequence references. Replace those references with clean interface and internal canonical animation assets. The locomotion state graph body is deferred until its graph nodes are copied and dependency-audited incrementally.

```text
CLEAN_ABP_CREATED = YES
CLEAN_ABP_CREATION_METHOD = NEW_BLANK_PACKAGE
CLEAN_ABP_TARGET_SKELETON = /Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase
VARIABLE_SCHEMA_MATCH = PASS
VARIABLE_COUNT_SOURCE = 17
VARIABLE_COUNT_CLEAN = 17
CLASS_DEFAULT_TRANSFER = PARTIAL
CLEAN_ABP_NEW_INTERFACE_IMPLEMENTED = NO (Class Settings GUI step pending)
CLEAN_ABP_OLD_INTERFACE_DEPENDENCIES = 0
CLEAN_ABP_MANNEQUIN_DEPENDENCIES = 0
CLEAN_ABP_THIRDPERSON_DEPENDENCIES = 0
CLEAN_ABP_COMPILE = PASS
```

`MANUAL_GATE_REQUIRED = ADD_BPI_FUTSALPLAYERBASEANIMATION_TO_CLEAN_ABP`

## Phase BASE-1J-INTERFACE-VERIFY — Clean ABP Interface Baseline

- 日期：2026-09-24
- Read-only post-GUI verification of `ABP_FutsalPlayerBase_Clean` passed. Asset Registry dependencies are exactly native `/Script/AnimGraph`, target `SK_FutsalPlayerBase`, and `BPI_FutsalPlayerBaseAnimation`; no old BPI, Mannequin, or ThirdPerson package is present.
- Generated-class metadata lists only the new interface and maps `GetMotionSpeedMps` to the clean ABP graph. Function inventory reports `GetMotionSpeedMps` implemented.
- Source EventGraph is named `EventGraph`; clean shell EventGraph has no pasted body nodes yet. UE Python `EdGraph.Nodes` is protected, so exact node-by-node source body inventory is unavailable to the read-only API.
- Safe first graph family: EventGraph body logic (character/movement sampling, velocity/speed/direction calculations, auto motion-speed path), excluding graph boundary entry nodes and any old interface call or external asset reference. Exact node titles/pin links cannot be confirmed from Python and must be handled visually in the editor.

```text
CLEAN_ABP_NEW_INTERFACE_IMPLEMENTED = YES
CLEAN_ABP_OLD_INTERFACE_IMPLEMENTED = NO
CLEAN_ABP_NEW_INTERFACE_DEPENDENCIES = 1
CLEAN_ABP_OLD_INTERFACE_DEPENDENCIES = 0
CLEAN_ABP_MANNEQUIN_DEPENDENCIES = 0
CLEAN_ABP_THIRDPERSON_DEPENDENCIES = 0
GETMOTIONSPEEDMPS_IMPLEMENTATION = PRESENT
CLEAN_ABP_COMPILE = PASS
CLEAN_ABP_INTERFACE_BASELINE = PASS
```

`MANUAL_GATE_REQUIRED = COPY_EVENTGRAPH_BODY_TO_CLEAN_ABP`

## Phase BASE-1J-EVENTGRAPH-FINAL-VERIFY — EventGraph Reconnection and AnimGraph Gate

- 日期：2026-09-24
- Read-only checks confirm clean ABP dependency closure is exactly native `/Script/AnimGraph`, target `SK_FutsalPlayerBase`, and new `BPI_FutsalPlayerBaseAnimation`; old BPI, Mannequin, ThirdPerson, and old BlendSpace are absent.
- Generated class metadata implements only the new interface and maps its `GetMotionSpeedMps` graph. Graph inventory includes `EventGraph` and `GetMotionSpeedMps`; compile is reported PASS by the user and the current API compile check returned true.
- Source AnimGraph node inventory: root output; two state machines (`Locomotion`, `Main States`); locomotion cache save/use; Idle, Walk / Run, Jump, Fall Loop, Land state results; eight transition-result nodes; one BlendSpace player referencing old `BS_Futsal_Locomotion`; four sequence players referencing old Idle/Jump/Fall/Land; DefaultSlot; and one FootIK ControlRig node.
- Safe next incremental unit: migrate only the `Locomotion` state machine and its state/result/transition graphs, cache pose save/use, and internal BlendSpace/sample animation references. Do not include the `Main States` state machine or ControlRig in this first AnimGraph gate; migrate those separately after closure checks.
- Python protected `EdGraph.Nodes`, so exact EventGraph boundary pin-link reconstruction is not independently inspectable here. No assets were modified in this verification.

```text
CLEAN_EVENTGRAPH_RECONSTRUCTION = PASS (user-reported; clean EventGraph graph exists)
CLEAN_ABP_OLD_INTERFACE_DEPENDENCIES = 0
CLEAN_ABP_MANNEQUIN_DEPENDENCIES = 0
CLEAN_ABP_THIRDPERSON_DEPENDENCIES = 0
CLEAN_ABP_OLD_BLENDSPACE_DEPENDENCIES = 0
CLEAN_ABP_NEW_INTERFACE_DEPENDENCIES = 1
GETMOTIONSPEEDMPS_TARGET = SELF (user-reported)
GETMOTIONSPEEDMPS_NEW_INTERFACE = BPI_FutsalPlayerBaseAnimation
CLEAN_ABP_COMPILE = PASS
```

`MANUAL_GATE_REQUIRED = COPY_LOCOMOTION_STATE_MACHINE_TO_CLEAN_ABP`

Open `ABP_FutsalPlayerBase_Clean` in Anim Blueprint Editor → Class Settings → Implemented Interfaces → add only `BPI_FutsalPlayerBaseAnimation` → compile/save/close. Do not copy the old `GetMotionSpeedMps` graph. Afterward, Agent will audit the clean shell and then request the smallest graph-body gate, beginning with EventGraph.

## Phase BASE-1J-INTERFACE-VERIFY — Clean Shell Interface/Closure Check

- 日期：2026-09-24
- The clean shell now has all 17 source variable names and exact `EdGraphPinType` exports. It was compiled and saved after schema recreation.
- Saved asset registry metadata confirms target skeleton `SK_FutsalPlayerBase`, and package dependencies are only `/Script/AnimGraph` and that target Skeleton. Old BPI, Mannequin, and ThirdPerson dependencies are all zero.
- No interface mutation API is available for AnimBlueprint in the running UE 5.8 Python surface. The shell must receive its new BPI through Class Settings before copying EventGraph content.
- Clean shell graph inventory is currently `AnimGraph` and `EventGraph` only; it has no `GetMotionSpeedMps` implementation graph until the interface is attached.

```text
CLEAN_ABP_CREATED = YES
CLEAN_ABP_CREATION_METHOD = NEW_BLANK_PACKAGE
CLEAN_ABP_TARGET_SKELETON = /Game/FutsalMOT/Characters/FutsalPlayerBase/Skeleton/SK_FutsalPlayerBase
VARIABLE_SCHEMA_MATCH = PASS
VARIABLE_COUNT_SOURCE = 17
VARIABLE_COUNT_CLEAN = 17
CLASS_DEFAULT_TRANSFER = PARTIAL
CLEAN_ABP_NEW_INTERFACE_IMPLEMENTED = NO (GUI attachment pending)
CLEAN_ABP_OLD_INTERFACE_DEPENDENCIES = 0
CLEAN_ABP_MANNEQUIN_DEPENDENCIES = 0
CLEAN_ABP_THIRDPERSON_DEPENDENCIES = 0
CLEAN_ABP_COMPILE = PASS
```

`MANUAL_GATE_REQUIRED = ADD_BPI_FUTSALPLAYERBASEANIMATION_TO_CLEAN_ABP`
## Phase BASE-1K — Retargeted Animation Library Forensic Audit

- 日期：2026-09-24
- Read-only audit. No animation, BlendSpace, ABP, ControlRig, mesh, Skeleton, or `UNREAL_RIG` asset was modified.
- The authoritative pose path was `AnimSequence.get_anim_pose_at_frame` with `AnimPoseEvaluationOptions.evaluation_type = RAW`. The earlier `AnimationLibrary.get_bone_pose_for_frame` path was not used for classification because it returned constant reference transforms even for moving source clips.
- Source Walk_Fwd sampled motion is substantial: maximum sampled translation delta about 440 cm and quaternion-component delta about 1.994 across representative bones. Its target `A_FutsalPlayerBase_MF_Unarmed_Walk_Fwd` sampled delta is exactly zero for the same method and frame percentages.
- All 17 canonical target locomotion clips measured zero sampled translation and rotation variation. Pairwise comparison found all 136 target pairs exact duplicates at the sampled representative-bone pose data, including every locomotion target against `A_FutsalPlayerBase_MM_Idle`.
- Source timing and target timing/frame counts match, proving the retarget operation created structurally plausible assets but did not preserve animated content.
- The source Jump/Fall/Land clips are distinct and have source motion, but no canonical target assets exist for them yet.
- The canonical BlendSpace has all 27 expected references and coordinates, but every referenced target sequence belongs to the proven static duplicate library.

```text
TARGET_ANIMATION_COUNT = 17
SOURCE_ANIMATION_COUNT = 20 runtime source clips (17 BlendSpace + Jump/Fall/Land)
SOURCE_ANIMATION_LIBRARY_DISTINCT = YES
TARGET_ANIMATION_LIBRARY_DISTINCT = NO
TARGET_CLIPS_IDENTICAL_TO_IDLE = 17
DIRECTIONAL_LOCOMOTION_DISTINCT = NO
JUMP_TARGET = FAIL (target missing)
FALL_TARGET = FAIL (target missing)
LAND_TARGET = FAIL (target missing)
RETARGET_FAILURE_CONFIRMED = YES
ANIMATION_LIBRARY_STATUS = GLOBAL_RETARGET_FAILURE
ANIMATION_LIBRARY_INTEGRITY = FAIL
```

### Source-to-target map

The 17 BlendSpace source clips map one-to-one by semantic source asset name to `A_FutsalPlayerBase_<SourceName>`. Source Walk/Jog clips have real motion; all corresponding target clips are static/reference-pose duplicates. `MM_Jump`, `MM_Fall_Loop`, and `MM_Land` have no target asset.

### Target motion classification

All 17 target clips:

```text
TARGET_MOTION_CLASS = STATIC_OR_NEAR_STATIC
```

## Phase BASE-1U — AnimBlueprint Canonicalization

- 日期：2026-09-25
- The contaminated migration-source package `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase` was hard-deleted after a live referencer audit returned zero project-content referencers.
- `ABP_FutsalPlayerBase_Clean` was renamed to the canonical asset `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase`.
- The old `_Clean` package no longer exists. No affected-path redirectors remained after the delete/rename operation.
- The canonical generated class is `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C`.
- The canonical AnimBlueprint was reloaded, compiled successfully, and saved without graph reconstruction.
- The final graph retains the Locomotion state machine feeding the `Locomotion` cached pose and the Main States pose chain through `DefaultGroup.DefaultSlot`, the localized `CR_FutsalPlayerBase_FootIK` Control Rig, and Output Pose. Control Rig Alpha is `1.0`; `ShouldDoIKTrace` remains `NOT IsFalling`.
- Final dependency closure contains zero Mannequin, ThirdPerson, old-interface, old-runtime-animation, external project-content, stale contaminated-package, and broken-reference dependencies. `BPI_FutsalPlayerBaseAnimation` remains present.
- Final canonical ABP project-content referencer count is 0.
- `UNREAL_RIG` remained unchanged from baseline.

```text
CONTAMINATED_ABP_HARD_DELETED = YES
CLEAN_ABP_RENAMED_TO_CANONICAL = YES
CANONICAL_ABP_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/ABP_FutsalPlayerBase.ABP_FutsalPlayerBase_C
AFFECTED_PATH_REDIRECTOR_COUNT = 0
CANONICAL_ABP_COMPILE = PASS
CANONICAL_CONTROL_RIG_NODE_COUNT = 1
CANONICAL_CONTROL_RIG_ALPHA = 1.0
CANONICAL_SHOULD_DO_IKTRACE_EXPRESSION = NOT IsFalling
CANONICAL_ABP_REFERENCER_COUNT = 0
CANONICAL_ABP_BROKEN_REFERENCES = 0
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
```

Source motion deltas measured by raw pose evaluation:

- Walk clips: approximately `439–633 cm` maximum sampled representative-bone translation delta.
- Jog clips: approximately `879–1041 cm` maximum sampled representative-bone translation delta.
- Idle: `0` motion delta.
- Target Walk/Jog/Idle clips: `0` sampled translation and rotation delta.

### Duplicate groups

One exact duplicate group contains all 17 target clips. Pairwise sampled pose comparison produced `136` exact duplicate pairs, which is `17 choose 2`. This includes all target Walk, Jog, and Idle clips.

### BlendSpace content audit

All 27 BlendSpace samples resolve to existing canonical target assets and preserve the source coordinates. However, each referenced target is part of the static duplicate library. Therefore:

```text
BLENDSPACE_SAMPLE_REFERENCES = CONTENT_CORRUPTED
```

### Failure and repair recommendation

```text
BAD_TARGET_ANIMATIONS = all 17 assets under /Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/
BAD_BLENDSPACE_ASSETS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/BlendSpaces/BS_FutsalPlayerBase_Locomotion
```

Do not repair in this phase. The next repair should preserve the Mesh, Skeleton, PhysicsAsset, Materials, Textures, clean ABP shell/EventGraph, and interfaces; create a disposable explicit retarget configuration; prove a corrected Walk probe with raw `AnimPose` sampling; then prove Idle, Jog, and Jump probes before rebuilding the complete 20-clip library and BlendSpace. The likely output defect is a retarget configuration failure, but the exact chain/root/profile cause remains to be audited in the next phase before any retarget operation.
## Phase BASE-1L — Global Retarget Failure and Repair

- 日期：2026-09-24
- 只读内容审计；未改动、保存、重定向、删除或重建动画、BlendSpace、ABP、ControlRig、Skeleton、Mesh 或其他资产。
- Correct pose API: `AnimSequence.get_anim_pose_at_frame(frame, AnimPoseEvaluationOptions(evaluation_type=RAW))`; representative bone names passed as Python `str`. `AnimationLibrary.get_bone_pose_for_frame` was explicitly rejected as evidence because it returned reference transforms for known moving sources.
- All 17 canonical locomotion targets are static at sampled frames 0/25/50/75/100%. Every target pair compares as an exact duplicate over sampled representative bone transforms: 136 duplicate pairs (`17 choose 2`).
- Source clips are distinct and moving. Walk sampled maximum translation delta approximately 439.7–632.7 cm; Jog approximately 879.1–1040.6 cm. Idle is static, as expected. Target Walk/Jog are all static and match the same reference pose data as target Idle.
- Source Jump, FallLoop, and Land are all present and have motion. Their target clips do not exist.
- All 27 BlendSpace samples resolve to the expected canonical target names/coordinates, but each target is content-corrupted. The BlendSpace itself is not repaired in this phase.
- The precise root cause in IKR/retargeter chain settings remains unproven. This phase establishes a global retarget output collapse, not its configuration-level cause. No repair probe was attempted.

```text
RETARGET_ROOT_CAUSE = GLOBAL_RETARGET_FAILURE (configuration root cause not yet isolated)
SOURCE_IKR_VALID = NOT_AUDITED_IN_BASE-1L
TARGET_IKR_VALID = NOT_AUDITED_IN_BASE-1L
CHAIN_MAPPING_VALID = NOT_AUDITED_IN_BASE-1L
RUNTIME_SOURCE_SEQUENCE_COUNT = 20
IDLE_PROBE = NOT_REACHED
WALK_PROBE = FAIL (existing canonical result static; corrected disposable probe not run)
JOG_PROBE = NOT_REACHED
JUMP_PROBE = NOT_REACHED
FULL_REPAIR_EXECUTED = NO
REPAIRED_SEQUENCE_COUNT = 0
REPAIRED_ANIMATION_LIBRARY_INTEGRITY = NOT_REACHED
DIRECTIONAL_WALK_DISTINCT = NO (canonical target samples are exact duplicates)
DIRECTIONAL_JOG_DISTINCT = NO (canonical target samples are exact duplicates)
JUMP_TARGET = FAIL (missing)
FALL_TARGET = FAIL (missing)
LAND_TARGET = FAIL (missing)
REPAIRED_BLENDSPACE_SAMPLE_COUNT = 0
REPAIRED_BLENDSPACE_CONTENT_VALID = NOT_REACHED
BAD_CANONICAL_SEQUENCE_COUNT_REMAINING = 17
BAD_CANONICAL_BLENDSPACE_COUNT_REMAINING = 1
MIGRATION_REPAIR_ASSETS_REMAINING = 0
FUTSALPLAYERBASE_ANIMATION_EXTERNAL_PROJECT_DEPENDENCIES = source Mannequin dependencies remain through source IKR/retarget path; no canonical animation fix made
CLEAN_ABP_IDLE_REFERENCE_VALID = NO (points at defective canonical idle pending repair)
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### SOURCE_TO_TARGET_ANIMATION_MAP

Each of the 17 unique BlendSpace source sequences maps by semantic name to `/Game/FutsalMOT/Characters/FutsalPlayerBase/Animation/Sequences/A_FutsalPlayerBase_<source asset name>`. This mapping is structurally correct, but every target has static content. Additional sources `/Game/Characters/Mannequins/Anims/Unarmed/Jump/MM_Jump`, `.../Jump/MM_Fall_Loop`, and `.../Jump/MM_Land` have no target sequence.

### TARGET_MOTION_CLASSIFICATION

All 17 current target locomotion assets: `STATIC_OR_NEAR_STATIC` (sampled representative-bone max translation delta = 0; rotation-component delta = 0). `MM_Idle` is expectedly static. Walk/Jog are not.

### TARGET_DUPLICATE_GROUPS

One exact duplicate group containing all 17 current targets. All 136 pairwise sampled pose comparisons were exact matches. Each is identical to `A_FutsalPlayerBase_MM_Idle` at the sampled times/bones.

### SOURCE_VS_TARGET_MOTION_COMPARISON

Source Walk has non-zero animated pelvis/limb trajectories; source Jog has larger motion; source Jump/Fall/Land have distinct motion. Current canonical target Walk/Jog are static reference-pose samples; Jump/Fall/Land targets are absent. Duration and frame count match for the 17 retargeted locomotion clips, which did not preserve their animated pose content.

### BLENDSPACE_SAMPLE_CONTENT_AUDIT

All 27 source sample coordinates map to existing canonical target paths, with 17 unique targets. Since all 17 target clips are static duplicates, `BLENDSPACE_SAMPLE_REFERENCES = CONTENT_CORRUPTED`.

### RECOMMENDED_REPAIR_STRATEGY

Next phase must audit `IKR_Quinn`, target IKR, and the actual IK Retargeter source/target rig assignments, retarget roots, chain mappings, chain enablement/settings, and retarget poses before retargeting. Then run only a disposable Walk_Fwd content probe using raw AnimPose evaluation. Proceed to Idle/Jog/Jump probes and full 20-sequence rebuild only if corrected Walk/Jog/Jump/Idle all pass. Do not use the current target library or BlendSpace as evidence of valid motion.
## Phase BASE-1N — Clean IK Retargeter Reconstruction and Single-Clip Motion Probe

- 日期：2026-09-24
- Read-only evidence from BASE-1M identified the failed saved retargeter’s concrete defect: `IKR_FutsalPlayerBase` had source and target IKR assignments but `IKRetargeterController.get_num_retarget_ops() = 0`. No Pelvis Motion, FK Chains, IK Chains/Run IK Rig, Root Motion, or other executable retarget operation stack existed in the failed configuration.
- Source/target IKR chain definitions were independently compatible: 29 matching semantic chain names and matching endpoints; both roots are `pelvis`. The target mesh has the mapped core bones. The skeletons remain non-identical and reference poses differ, so IK retarget remains necessary.
- Created a brand-new transactional `RTG_Quinn_To_FutsalPlayerBase_Probe` from `IKRetargetFactory` under `/Game/FutsalMOT/Characters/FutsalPlayerBase/_MigrationRepair/`. It was not duplicated from the failed retargeter.
- Assigned `IKR_Quinn` as source and `IKR_FutsalPlayerBase_Target` as target; assigned source/target preview meshes; added default retarget ops; assigned rigs to all ops; applied exact chain auto-mapping; reset Default Pose on both sides where supported. The probe retargeter has 5 enabled ops: `Pelvis Motion`, `FK Chains`, `Run IK Rig`, `Root Motion`, `Remap Curves`.
- Retargeted only `MF_Unarmed_Walk_Fwd` first. Raw `AnimPose` validation showed source and probe both have non-zero pelvis/limb motion; the probe target is not static and preserves the source motion class. The failed canonical target remains zero variation.
- Secondary probes were then created for Idle, forward Jog, and Jump. Idle is correctly static as a source semantic; Jog and Jump both preserve non-zero target motion. No bulk 20-sequence rebuild was executed.

```text
SOURCE_ASSET_CLASS = IKRigDefinition
TARGET_ASSET_CLASS = IKRigDefinition
FAILED_RETARGETER_ASSET_CLASS = IKRetargeter
CLEAN_PROBE_RETARGETER_CREATED = YES
RETARGET_POSE_RESET_AUTOMATABLE = YES (Default Pose reset API available/used)
PROBE_SOURCE_POSE = DEFAULT_REFERENCE
PROBE_TARGET_POSE = DEFAULT_REFERENCE
UNMAPPED_CHAIN_COUNT = 0
INVALID_MAPPING_COUNT = 0
SOURCE_WALK_HAS_MOTION = YES
PROBE_WALK_HAS_MOTION = YES
PROBE_WALK_STATIC = NO
PROBE_WALK_CONTENT = PASS
IDLE_PROBE = PASS (source and target semantically static idle)
JOG_PROBE = PASS
JUMP_PROBE = PASS
CLEAN_DEFAULT_RETARGET_PROBE = PASS
MANUAL_GATE_REQUIRED = NONE
```

The probe target motion deltas were measured with `AnimSequence.get_anim_pose_at_frame` and raw `AnimPoseEvaluationOptions`; `AnimationLibrary.get_bone_pose_for_frame` was not used. Walk source/probe pelvis and limb trajectories are non-zero; failed canonical Walk target remains zero. Jog and Jump probes also have non-zero target motion. Probe assets are intentionally retained transactionally for the next phase; canonical bad sequences and BlendSpace were not modified or deleted.
## Phase BASE-1O — Canonical Animation Library Repair (blocked at BlendSpace sample persistence)

- 日期：2026-09-24
- The clean transactional retargeter remained valid with exactly 5 enabled operations: Pelvis Motion, FK Chains, Run IK Rig, Root Motion, Remap Curves.
- The source BlendSpace batch initially produced a temporary BlendSpace whose samples still referenced source Mannequin animations. A second batch retargeted all 17 unique locomotion sequences into `/Game/FutsalMOT/Characters/FutsalPlayerBase/_MigrationRepair/Library/`; the three main-state sequences were also generated there. All 20 temporary sequences use `SK_FutsalPlayerBase`, have non-static raw AnimPose motion where expected, and have no Mannequin/ThirdPerson dependency individually.
- Attempted transactional BlendSpace sample rewiring to the 17 temporary sequences was not persisted by the supported UE 5.8 Python API. After save/rescan/GC, live sample references and Asset Registry dependencies still point to the original Mannequin animation assets. No canonical asset was deleted or promoted.

```text
PHASE_CANONICAL_ANIMATION_REPAIR = BLOCKED
RETARGET_ROOT_CAUSE = BATCH_RETARGET_CONFIGURATION_FAILURE (failed retargeter had zero ops)
VALIDATED_RETARGET_OPERATION_COUNT = 5
RUNTIME_SOURCE_SEQUENCE_COUNT = 20
TEMP_SEQUENCE_COUNT = 20
FAILED_TEMP_SEQUENCE_COUNT = 0
CANONICAL_SEQUENCE_COUNT = 17 (defective set retained)
CANONICAL_LOCOMOTION_COUNT = 17
CANONICAL_MAIN_STATE_COUNT = 0
CANONICAL_ANIMATION_LIBRARY_INTEGRITY = NOT_PROMOTED
DIRECTIONAL_WALK_DISTINCT = YES in transactional repaired sequences
DIRECTIONAL_JOG_DISTINCT = YES in transactional repaired sequences
IDLE_TARGET = PASS
JUMP_TARGET = PASS
FALL_TARGET = PASS
LAND_TARGET = PASS
CANONICAL_BLENDSPACE_SAMPLE_COUNT = 27
CANONICAL_BLENDSPACE_UNIQUE_SEQUENCE_COUNT = 17
CANONICAL_BLENDSPACE_CONTENT_VALID = FAIL (canonical content remains defective)
CANONICAL_ANIMATION_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0 for repaired sequences; canonical BlendSpace still references source Mannequin animations
FAILED_IKRETARGETER = RETAINED
IKR_FUTSALPLAYERBASE_CLASS = IKRetargeter (defective, retained pending referencer-safe normalization)
MIGRATION_REPAIR_ASSETS_REMAINING = 21 (20 repaired sequences + retargeted BlendSpace + retargeter; transactional)
CLEAN_ABP_IDLE_REFERENCE_VALID = NO (canonical Idle remains defective; no swap performed)
BROKEN_REMAINING_ASSET_REFERENCES = NOT_AUDITED_AFTER BLOCK
ANIMATION_MIGRATION_REDIRECTORS = NOT_AUDITED_AFTER BLOCK
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

`MANUAL_GATE_REQUIRED = POPULATE_REPAIRED_BLENDSPACE_SAMPLE_REFERENCES`

The repaired sequence library is valid and retained transactionally. The exact blocker is supported API persistence of `BlendSpace.sample_data[].animation` references: Python can read and mutate the in-memory sample structs, but after saving and reloading the package, the samples still resolve to the original Mannequin animation paths. Do not promote or delete canonical assets until the repaired BlendSpace is populated and saved through the BlendSpace Editor UI, or another supported API that persists sample references.
## Phase BASE-1O-PROMOTE-EXECUTE — Canonical Animation Repair Closure

- 日期：2026-09-24
- The validated five-operation retargeter was used to generate the transactional 20-sequence library. Raw `AnimPose` validation passed for all 20 sequences; Walk/Jog directional content remains distinct, Idle is static as expected, and Jump/Fall/Land are distinct.
- The manually repaired transactional BlendSpace was promoted by coordinate identity `(Direction, Speed)`, preserving 27 samples, 17 unique locomotion sequences, exact coordinates, and zero Mannequin/ThirdPerson dependencies.
- The defective 17 canonical locomotion sequences and defective canonical BlendSpace were hard-deleted after referencer checks. The 20 repaired sequences were promoted to canonical `A_FutsalPlayerBase_*` paths.
- The failed zero-operation `IKRetargeter` at `Animation/Retarget/IKR_FutsalPlayerBase` had no referencers and was hard-deleted. The valid target `IKR_FutsalPlayerBase_Target` was renamed to canonical `IKR_FutsalPlayerBase`; final class is `IKRigDefinition`.
- `_MigrationRepair` no longer exists. No ControlRig, Main States, or old canonical ABP retirement was performed in this phase.
- The clean ABP currently had no migrated Idle SequencePlayer at the time of promotion, so no Idle reference rewrite was required; final canonical Idle exists and is ready for later AnimGraph/state-machine migration.

```text
PHASE_BASE_1O_PROMOTION = COMPLETE

## BASE-2C — DESTRUCTIVE COURT MIGRATION AND PROGRAMMATIC SEQUENCER REBUILD

- 日期：2026-09-25
- The authorized single-file restore of `Content/FutsalMOT/Sequences/LS_Cam_01.uasset` from the live HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e` completed successfully after unloading only that package.
- Reloaded `LS_Cam_01` still contains only 9 Player_* bindings, not the required original 10. `Player_L0` exists and retains a transform track, but another Player binding is absent.
- `HEAD_BASELINE_ALREADY_DAMAGED = YES`. The mandatory 60-binding snapshot invariant cannot be satisfied because the supposedly restored HEAD baseline is already missing one Player binding in `LS_Cam_01`.
- Per the explicit stop condition, no Court actor was replaced, no Level Sequence was rebuilt or saved, no test map was changed, and no retired runtime asset was deleted.
- The prior BASE-1Z2 live Court inspection remains valid: ten old Character actors are present, each uses `SKM_Quinn_Simple` and `ABP_FutsalSource_C`; all six sequences have old Character possessables; replacement APIs were not invoked.
- The protected `UNREAL_RIG` asset remains unchanged from baseline, Git remains unstaged, and no backup/archive asset was created.

```text
PHASE_BASE_2C = BLOCKED
LS_CAM_01_RESTORED_FROM_HEAD = YES
LS_CAM_01_PLAYER_BINDINGS_AFTER_RESTORE = 9
HEAD_BASELINE_ALREADY_DAMAGED = YES
ORIGINAL_SEQUENCE_SNAPSHOT_RECOVERED = NO
COURT_PLAYERS_REPLACED_THIS_PHASE = 0
SEQUENCE_PLAYER_BINDINGS_REBUILT = 0
TEST_LEVEL_PLAYER_REPLACEMENT_COUNT = 0
OLD_IKR_QUINN_DELETED = YES (prior phase)
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

Blocking reason: recover the missing `LS_Cam_01` Player binding/track baseline before beginning destructive Court actor replacement or programmatic Sequencer regeneration.

## BASE-2B — DIRECT COURT REPLACEMENT AND PROGRAMMATIC SEQUENCER REBUILD

- 日期：2026-09-25
- Read-only pre-mutation checkpoint. No Court actor, external actor package, Level Sequence, test map, retired runtime asset, or protected asset was modified or saved in BASE-2B.
- Live editor world is `/Game/FutsalMOT/Maps/L_FutsalCourt.L_FutsalCourt`; the Actor Subsystem enumerated 10 old `BP_FutsalCharacterBase_C` Court players. Their live transforms, labels, tags, mesh overrides, and old `ABP_FutsalSource_C` AnimClass overrides were captured.
- The only exposed actor replacement API destroys source actors and documents copying only limited transform/tag/group state. It does not guarantee World Partition actor GUID preservation. The exposed Sequencer rebinding APIs do not document deterministic possessable class metadata repair after actor destruction.
- BASE-2B required a complete 60-binding snapshot before mutation. Reloading `/Game/FutsalMOT/Sequences/LS_Cam_01` from disk with `ReloadPackagesInteractionMode.ASSUME_POSITIVE` succeeded, but restored only 9 Player bindings. `Player_L0` and its transform track were present; one other required Player binding was missing. Therefore the original 10-binding contract could not be recovered faithfully.
- Because `LS_Cam_01` could not satisfy the required pre-migration snapshot invariant, actor replacement and all six Sequence rebuilds were stopped before mutation. The pilot in-memory Court state was not undone or saved by this phase.
- `IKR_Quinn` remains deleted from the prior phase. The old Character, old AnimBP, old interface, and old BlendSpace remain referenced and were not deleted.
- The exact Court actor and binding manifest from the live world remains documented in the previous BASE-1Z2 section. A further phase must recover or reconstruct the missing saved Sequence binding through an explicit Editor recovery decision before destructive actor replacement.

```text
PHASE_BASE_2B = BLOCKED
ORIGINAL_SEQUENCE_SNAPSHOT_RECOVERED = NO
SNAPSHOT_SEQUENCE_COUNT = 0 complete sequences accepted
SNAPSHOT_PLAYER_BINDING_COUNT = 0 accepted; LS_Cam_01 recovered 9/10
SNAPSHOT_PLAYER_TRACK_COUNT = NOT_ACCEPTED
SNAPSHOT_PLAYER_SECTION_COUNT = NOT_ACCEPTED
SNAPSHOT_PLAYER_KEY_COUNT = NOT_ACCEPTED
COURT_OLD_PLAYER_COUNT = 10 live old actors before mutation
COURT_CANONICAL_PLAYER_COUNT = 0
COURT_PLAYERS_REPLACED_THIS_PHASE = 0
SEQUENCE_PLAYER_BINDINGS_REBUILT = 0
SEQUENCE_PLAYER_BINDINGS_BOUND = 0
SEQUENCE_BROKEN_PLAYER_BINDINGS = UNKNOWN after no mutation
SEQUENCE_TRACK_COUNT_MATCH = NOT_EVALUATED
SEQUENCE_SECTION_COUNT_MATCH = NOT_EVALUATED
SEQUENCE_KEY_COUNT_MATCH = NOT_EVALUATED
LS_CAM_MAIN_CAMERA_CHILD_BINDINGS_VALID = NOT_EVALUATED
LS_CAM_P01_CAMERA_CHILD_BINDINGS_VALID = NOT_EVALUATED
TEST_LEVEL_PLAYER_REPLACEMENT_COUNT = 0
TEST_LEVEL_OLD_CHARACTER_REFERENCES = 1
TEST_LEVEL_OLD_ABP_REFERENCES = 1
OLD_BP_FUTSALCHARACTERBASE_DELETED = NO
OLD_ABP_FUTSALSOURCE_DELETED = NO
OLD_BPI_FUTSALANIMATIONSOURCE_DELETED = NO
OLD_BS_FUTSAL_LOCOMOTION_DELETED = NO
OLD_IKR_QUINN_DELETED = YES
RETIRED_RUNTIME_ASSET_COUNT = 4
RETIRED_RUNTIME_REFERENCE_COUNT = 31 before Court migration
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0 canonical closure
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 canonical closure
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 canonical Character closure
FUTSALPLAYERBASE_BROKEN_REFERENCES = 0 observed canonical package checks
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_ABP_COMPILE = PASS (last verified)
CONTROL_RIG_STATUS = PASS
IK_RIG_STATUS = NOT_APPLICABLE (IKR_Quinn deleted; canonical IKR previously valid)
CANONICAL_ANIMATION_SEQUENCE_COUNT = 20 (last verified)
COURT_RUNTIME_SMOKE_TEST = NOT RUN
SEQUENCER_SMOKE_TEST = NOT RUN
REDIRECTOR_COUNT = 0 affected Blueprint directory
BROKEN_REFERENCE_COUNT = 0 observed canonical package checks
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

Blocking reason: `LS_Cam_01` last-saved reload produced 9 Player bindings instead of the required 10, so the complete pre-migration track/key snapshot invariant is not satisfied. Do not destroy Court actors or rebuild any Sequence until the missing binding/data is recovered or an explicit manual recovery decision is made.

## BASE-1Z2 — LIVE COURT MIGRATION AND FUTSALPLAYERBASE RUNTIME CLOSURE

- 日期：2026-09-25
- Live branch `refactor/character-architecture`, HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`; zero staged files. `UNREAL_RIG` remains at its pre-existing unstaged modified baseline and was not touched.
- The current Editor World is `/Game/FutsalMOT/Maps/L_FutsalCourt.L_FutsalCourt`. `EditorActorSubsystem.get_all_level_actors()` returns 100 actors, including exactly ten old `BP_FutsalCharacterBase_C` players labelled `Player_L0`..`Player_L4` and `Player_R0`..`Player_R4`.
- Live actor snapshot: all ten are in `DynamicObjects`, carry matching `PoseL*`/`PoseR*` tags, have no attached parent or children, and each `CharacterMesh0` uses `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple` with Animation Mode `ANIMATION_BLUEPRINT`, explicit Anim Class `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource.ABP_FutsalSource_C`, and no material overrides. Locations/rotations/scales were captured live; five L actors report zero transforms, while R actors are placed around the field. Actor GUIDs were captured via `actor_guid` property.
- All six `LS_Cam_*` sequences were opened/read and contain ten Player_* possessable bindings each, zero spawnables, old possessed class `BP_FutsalCharacterBase_C`, and transform tracks. Sequencer bound-object lookup mapped each Player label to the corresponding live Court actor. `LS_Cam_Main` and `LS_Cam_P01` have camera-component child bindings.
- UE's available `EditorActorSubsystem.convert_actors` explicitly destroys supplied actors and only documents copying location, rotation, draw scale, tags, and group. It does not guarantee World Partition actor GUID or Level Sequence possessable identity preservation. Sequencer `replace_binding_with_actors`/`add_actors_to_binding` do not document updating stored possessable class metadata. No actors or sequence bindings were modified because preserving those 60 possessable references cannot be guaranteed with the exposed operation.
- The test map loaded, but both Editor Actor Subsystem and deprecated actor enumeration returned zero actors while the current editor world was `L_FutsalCourt`; no test map change was made.
- `IKR_Quinn` had zero referencers and was hard-deleted in this phase. The old Character, old AnimBP, old BPI, and old BlendSpace remain because Court, Level Sequence, and test-level references remain.
- Canonical Character is present and `BS_UP_TO_DATE`; its package closure remains free of old-runtime, Mannequin, ThirdPerson, and unwanted architecture dependencies. Canonical AnimBP/ControlRig were not modified.
- No Court, external actor, sequence, or test-map asset was saved. No backup/archive copy was created.

```text
PHASE_BASE_1Z2 = PARTIAL
LIVE_OLD_COURT_PLAYER_COUNT_BEFORE = 10
LIVE_OLD_COURT_PLAYER_COUNT_AFTER = 10
LIVE_CANONICAL_COURT_PLAYER_COUNT = 0
COURT_PLAYER_REPLACEMENT_COUNT = 0
COURT_OLD_ABP_OVERRIDE_COUNT = 10
SEQUENCE_TOTAL = 6
SEQUENCE_PLAYER_BINDINGS_TOTAL = 60
SEQUENCE_PLAYER_BINDINGS_REBOUND = 0
SEQUENCE_BROKEN_BINDINGS = 0 observed before mutation
SEQUENCE_OLD_CHARACTER_DEPENDENCIES = 6
LS_Cam_Main_CAMERA_CHILD_BINDINGS = present; unchanged
LS_Cam_P01_CAMERA_CHILD_BINDINGS = present; unchanged
TEST_PLAYER_REPLACEMENT_COUNT = 0
TEST_OLD_CHARACTER_REFERENCES = 1
TEST_OLD_ABP_REFERENCES = 1
OLD_BP_FUTSALCHARACTERBASE_REFERENCERS = 17
OLD_ABP_FUTSALSOURCE_REFERENCERS = 11
OLD_BPI_FUTSALANIMATIONSOURCE_REFERENCERS = 2
OLD_BS_FUTSAL_LOCOMOTION_REFERENCERS = 1
OLD_BP_FUTSALCHARACTERBASE_DELETED = NO
OLD_ABP_FUTSALSOURCE_DELETED = NO
OLD_BPI_FUTSALANIMATIONSOURCE_DELETED = NO
OLD_BS_FUTSAL_LOCOMOTION_DELETED = NO
OLD_IKR_QUINN_DELETED = YES
RETIRED_RUNTIME_ASSET_COUNT = 4
RETIRED_RUNTIME_REFERENCE_COUNT = 31 direct references remain
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0 canonical runtime closure
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 canonical runtime closure
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 canonical Character package
FUTSALPLAYERBASE_BROKEN_REFERENCES = 0 observed canonical package checks
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_ABP_COMPILE = PASS (last verified)
CONTROL_RIG_STATUS = PASS; localized rig retained
CANONICAL_ANIMATION_SEQUENCE_COUNT = 20 (last verified)
COURT_RUNTIME_SMOKE_TEST = NOT RUN
SEQUENCER_SMOKE_TEST = NOT RUN
REDIRECTOR_COUNT = 0 affected Blueprint directory
BROKEN_REFERENCE_COUNT = 0 observed canonical package checks
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Court actor identity snapshot

No actor replacement occurred; replacement GUID fields are therefore intentionally absent. Every row below has the old actor GUID captured from the live actor's `actor_guid` property, and each actor has its corresponding Pose tag.

| Old actor | Old GUID | Transform (location; rotation; scale) | Mesh | AnimClass | Result |
|---|---|---|---|---|---|
| Player_L0 | Captured | (0,0,0); (0,0,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_L1 | Captured | (0,0,0); (0,0,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_L2 | Captured | (0,0,0); (0,0,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_L3 | Captured | (0,0,0); (0,0,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_L4 | Captured | (0,0,0); (0,0,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_R0 | Captured | (2022.058725,0,90); (0,180,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_R1 | Captured | (81.000425,-91.045045,90); (0,75.813377,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_R2 | Captured | (78.257471,88.495815,90); (0,-131.317001,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_R3 | Captured | (202.205881,228.660263,90); (0,-76.029465,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |
| Player_R4 | Captured | (202.205881,-228.660263,90); (0,-102.431602,0); (1,1,1) | SKM_Quinn_Simple | ABP_FutsalSource_C | Not replaced |

### Sequence binding snapshot

Each listed Player_* binding is a possessable bound to its same-label live Court actor, with possessed class `BP_FutsalCharacterBase_C`, one transform track, and zero spawnables. Binding GUIDs were read from the six sequences during the live audit; no binding was changed. The pre-migration mapping is the label identity map: `Player_L0`..`Player_L4` map to the corresponding `Player_L*` Court actor; `Player_R0`..`Player_R4` map to the corresponding `Player_R*` Court actor.

| Sequence | Player bindings | Rebound | Possessed class after phase | Broken bindings | Old dependency |
|---|---:|---:|---|---:|---|
| `LS_Cam_01` | 10 | 0 | Old Character | 0 observed before mutation | Yes |
| `LS_Cam_02` | 10 | 0 | Old Character | 0 observed before mutation | Yes |
| `LS_Cam_03` | 10 | 0 | Old Character | 0 observed before mutation | Yes |
| `LS_Cam_04` | 10 | 0 | Old Character | 0 observed before mutation | Yes |
| `LS_Cam_Main` | 10 | 0 | Old Character | 0 observed before mutation | Yes |
| `LS_Cam_P01` | 10 | 0 | Old Character | 0 observed before mutation | Yes |

### Migration blocker and retired deletion chain

```text
Preserve 10 World Partition actor identities / GUIDs
    + preserve or deterministically rewrite 60 Level Sequence possessables
    + update stored possessable class metadata to BP_FutsalPlayerBase_C
    -> requires an Editor operation that guarantees actor GUID and Sequencer binding continuity
    -> do not use current convert_actors API (destroys actors; incomplete transfer contract)
    -> after Court migration and test-map actor migration:
         hard-delete old BP_FutsalCharacterBase and ABP_FutsalSource
         then hard-delete internal-only BPI_FutsalAnimationSource and BS_Futsal_Locomotion
```

The immediate safe gate is an identity-preserving in-editor replacement/rebind workflow that updates the possessable's stored class while retaining its GUID, transform tracks, and camera child bindings. No such preservation guarantee is exposed by the current Python API.

## BASE-1Z2 — LIVE COURT MIGRATION AND FUTSALPLAYERBASE RUNTIME CLOSURE

- 日期：2026-09-25
- Live editor world is `/Game/FutsalMOT/Maps/L_FutsalCourt`. The current Editor Actor Subsystem enumerates 100 live actors, including exactly ten `BP_FutsalCharacterBase_C` players with labels `Player_L0`..`Player_L4` and `Player_R0`..`Player_R4`.
- The ten live Character actors were inspected before mutation. Each has a `CharacterMesh0` using `/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple`, Animation Mode `ANIMATION_BLUEPRINT`, and explicit Anim Class `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource.ABP_FutsalSource_C`. Material overrides were empty; tags are `PoseL0`..`PoseL4` and `PoseR0`..`PoseR4`; folder is `DynamicObjects`; no attached parent or children were reported.
- Exact world transforms were captured live in the tool result. The preflight operation did not replace actors. Actor GUID structs are available, but conversion/replacement APIs exposed by UE 5.8 do not document preservation of those GUIDs or Level Sequence possessables.
- Six camera Level Sequences were opened read-only and inspected. Each contains ten Player_* possessable bindings, zero spawnables, possessed class `BP_FutsalCharacterBase_C`, and transform tracks. `LS_Cam_Main` and `LS_Cam_P01` include camera-component child bindings. `LevelSequenceEditorSubsystem.replace_binding_with_actors` and `add_actors_to_binding` do not document how they rewrite the possessable's stored class; generic `EditorActorSubsystem.convert_actors` destroys the old actor and only promises limited property copying. Destructive actor replacement was stopped before mutation to protect actor GUID and sequence binding identity.
- The test-level actor enumeration and map actor retrieval are not reliably exposed by the current World Partition/Python API. The test level was not changed.
- `IKR_Quinn` had previously been hard-deleted after zero referencers. The four remaining retired assets are retained due to live Level Sequence, test-level, Court actor, and internal retired-chain references.
- Canonical Character remains `BS_UP_TO_DATE`, generated class `BP_FutsalPlayerBase_C`; canonical Character package closure remains free of old runtime, Mannequin, ThirdPerson, and external architecture dependencies. Canonical AnimBP and localized ControlRig were not modified.
- No Court actor, external actor package, Level Sequence, test level, or retired runtime package was modified in this phase. `UNREAL_RIG` remains at baseline; Git remains unstaged.

```text
PHASE_BASE_1Z2 = PARTIAL
LIVE_OLD_COURT_PLAYER_COUNT_BEFORE = 10
LIVE_OLD_COURT_PLAYER_COUNT_AFTER = 10
LIVE_CANONICAL_COURT_PLAYER_COUNT = 0
COURT_PLAYER_REPLACEMENT_COUNT = 0
COURT_OLD_ABP_OVERRIDE_COUNT = 10
SEQUENCE_TOTAL = 6
SEQUENCE_PLAYER_BINDINGS_TOTAL = 60
SEQUENCE_PLAYER_BINDINGS_REBOUND = 0
SEQUENCE_BROKEN_BINDINGS = 0 observed before mutation; none changed
SEQUENCE_OLD_CHARACTER_DEPENDENCIES = 6
LS_Cam_Main_CAMERA_CHILD_BINDINGS = present; unchanged
LS_Cam_P01_CAMERA_CHILD_BINDINGS = present; unchanged
TEST_PLAYER_REPLACEMENT_COUNT = 0
TEST_OLD_CHARACTER_REFERENCES = 1
TEST_OLD_ABP_REFERENCES = 1
OLD_BP_FUTSALCHARACTERBASE_REFERENCERS = 17
OLD_ABP_FUTSALSOURCE_REFERENCERS = 11
OLD_BPI_FUTSALANIMATIONSOURCE_REFERENCERS = 2
OLD_BS_FUTSAL_LOCOMOTION_REFERENCERS = 1
OLD_BP_FUTSALCHARACTERBASE_DELETED = NO
OLD_ABP_FUTSALSOURCE_DELETED = NO
OLD_BPI_FUTSALANIMATIONSOURCE_DELETED = NO
OLD_BS_FUTSAL_LOCOMOTION_DELETED = NO
OLD_IKR_QUINN_DELETED = YES
RETIRED_RUNTIME_ASSET_COUNT = 4
RETIRED_RUNTIME_REFERENCE_COUNT = 31 direct references
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0 canonical closure
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 canonical closure
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 canonical Character package
FUTSALPLAYERBASE_BROKEN_REFERENCES = 0 observed canonical package checks
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_ABP_COMPILE = PASS (last verified)
CONTROL_RIG_STATUS = PASS; canonical localized rig preserved
CANONICAL_ANIMATION_SEQUENCE_COUNT = 20 (last verified)
COURT_RUNTIME_SMOKE_TEST = NOT RUN
SEQUENCER_SMOKE_TEST = NOT RUN
REDIRECTOR_COUNT = 0 affected Blueprint directory
BROKEN_REFERENCE_COUNT = 0 observed canonical package checks
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Captured old-to-new Court actor candidate map

No replacement actor GUID was created. The intended target for every old player actor is canonical `BP_FutsalPlayerBase_C`; GUID preservation and possessable metadata migration require a supported identity-preserving editor operation or a deliberate manual Sequencer/Court operation.

| Old player label | Old World Partition actor path | Old actor GUID | Captured transform (location; rotation; scale) | Tags | Mesh / AnimClass | Intended canonical target | Result |
|---|---|---|---|---|---|---|---|
| Player_L0 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421090971` | Guid captured | (0,0,0); (0,0,0); (1,1,1) | PoseL0 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_L1 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421109974` | Guid captured | (0,0,0); (0,0,0); (1,1,1) | PoseL1 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_L2 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421078969` | Guid captured | (0,0,0); (0,0,0); (1,1,1) | PoseL2 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_L3 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421097972` | Guid captured | (0,0,0); (0,0,0); (1,1,1) | PoseL3 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_L4 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421084970` | Guid captured | (0,0,0); (0,0,0); (1,1,1) | PoseL4 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_R0 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421115975` | Guid captured | (2022.058725,0,90); (0,180,0); (1,1,1) | PoseR0 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_R1 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421121976` | Guid captured | (81.000425,-91.045045,90); (0,75.813377,0); (1,1,1) | PoseR1 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_R2 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421103973` | Guid captured | (78.257471,88.495815,90); (0,-131.317001,0); (1,1,1) | PoseR2 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_R3 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1421072968` | Guid captured | (202.205881,228.660263,90); (0,-76.029465,0); (1,1,1) | PoseR3 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |
| Player_R4 | `PersistentLevel.BP_FutsalCharacterBase_C_UAID_44A3BB9598B7440303_1409399967` | Guid captured | (202.205881,-228.660263,90); (0,-102.431602,0); (1,1,1) | PoseR4 | Quinn Simple / ABP_FutsalSource | BP_FutsalPlayerBase_C | Not replaced |

### Pre/post sequence binding status

All six sequences have 10 Player_* possessable bindings, zero spawnables, and per-player transform tracks. Possessed class is `BP_FutsalCharacterBase_C`; live bound Court actor and label resolve one-to-one. No bindings or tracks were changed.

| Sequence | Player bindings | Rebound | Possessed class | Broken bindings | Old dependency |
|---|---:|---:|---|---:|---|
| `LS_Cam_01` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |
| `LS_Cam_02` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |
| `LS_Cam_03` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |
| `LS_Cam_04` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |
| `LS_Cam_Main` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |
| `LS_Cam_P01` | 10 | 0 | Old Character | 0 observed pre-migration | Yes |

`LS_Cam_Main` and `LS_Cam_P01` camera-component child bindings remain unchanged.

### Test level and retired runtime deletion chain

| Item | Status |
|---|---|
| Test-level player actor enumeration | API returned zero actors; map left unchanged |
| Test level old Character/AnimBP references | One each remain |
| Old Character | Retain: Level Sequences, test level, and Court actors reference it |
| Old AnimBP | Retain: test level and Court actors reference it |
| Old BPI | Retain: old Character/AnimBP internal chain references it |
| Old BlendSpace | Retain: old AnimBP references it |
| Old IKR_Quinn | Deleted after zero referencers |

The Sequencer/actor replacement operation exposed by UE (`convert_actors`) destroys originals and only documents copying transform, tags, and group; it does not guarantee World Partition actor GUID or possessable identity preservation. The Sequencer replacement/rebind calls also do not document rewriting possessable class metadata. Stop before destructive replacement until an identity-preserving replacement/rebind procedure is available in the Editor workflow.

## BASE-1Z — FUTSALPLAYERBASE RUNTIME CLOSURE

- 日期：2026-09-25
- Canonical `BP_FutsalPlayerBase` exists at `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`, generated class `BP_FutsalPlayerBase_C`, parent `/Script/Engine.Character`, compile state `BS_UP_TO_DATE`.
- The prior contaminated Character package was deleted; the clean candidate was promoted. No `.uasset` was changed by this BASE-1Z run.
- Project-wide Asset Registry scan reconfirmed 17 old Character references: six camera Level Sequences, one test level, and ten `L_FutsalCourt` external actor packages. The old AnimBP has 11 references: test level and ten Court external actor packages. No runtime reference migration was performed because the sequence player bindings are possessables with no spawnables and refer to map-owned actor instances; the test/Court actor list was not reliably enumerable through the available active-world Python API.
- Each of the six camera sequences has 10 Player_* possessables whose possessed class is `BP_FutsalCharacterBase_C`; every sequence reports zero spawnables and transform tracks on the Player bindings. The possessables must be rebound after their live actor ownership is resolved. No sequence was modified or saved.
- The test level `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` was loaded but the Editor Actor Subsystem returned an empty actor list and the World actor array is protected by the Python wrapper. It remains unchanged; old Character and old AnimBP references remain.
- Ten `L_FutsalCourt` external actor packages are listed below. They reference both old Character and old AnimBP. Their actor GUID, label, transform, class/component overrides, and sequence ownership remain unknown pending the manual Court gate. The level and external actor packages were not loaded for editing or saved.
- `IKR_Quinn` had zero referencers and was hard-deleted. Old Character, old AnimBP, old interface, and old BlendSpace were retained because references remain. No backup/archive copies were created.
- Canonical FutsalPlayerBase Character/AnimBP closure remains free of Mannequin, ThirdPerson, and old runtime dependencies. No affected Blueprint-directory redirectors remain. No runtime smoke test was run because the Court actor migration was not performed.
- `UNREAL_RIG` remains in its pre-existing unstaged worktree-modified state. Git remained unstaged; no commit, tag, or push occurred.

```text
PHASE_BASE_1Z = PARTIAL
COURT_OLD_CHARACTER_ACTOR_COUNT_BEFORE = 10 external actor package references (live actor count not enumerated)
COURT_OLD_CHARACTER_ACTOR_COUNT_AFTER = 10 external actor package references remain
COURT_CANONICAL_PLAYER_COUNT = 0 observed through current actor-enumeration API
COURT_ACTORS_MIGRATED_COUNT = 0
COURT_OLD_ABP_OVERRIDE_COUNT_AFTER = 10 external actor package references remain
SEQUENCE_TOTAL = 6
LS_CAM_01_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
LS_CAM_02_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
LS_CAM_03_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
LS_CAM_04_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
LS_CAM_MAIN_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
LS_CAM_P01_PLAYER_BINDINGS = 10 old Character possessables, 0 spawnables
SEQUENCE_BROKEN_BINDING_COUNT = UNKNOWN (not rebound; map-owned actor resolution unavailable)
SEQUENCE_OLD_CHARACTER_DEPENDENCIES = 6 sequences
TEST_LEVEL_MIGRATION = NOT COMPLETED (live actor enumeration unresolved)
TEST_LEVEL_OLD_CHARACTER_REFERENCES = 1
TEST_LEVEL_OLD_ABP_REFERENCES = 1
OLD_BP_FUTSALCHARACTERBASE_DELETED = NO
OLD_ABP_FUTSALSOURCE_DELETED = NO
OLD_BPI_FUTSALANIMATIONSOURCE_DELETED = NO
OLD_BS_FUTSAL_LOCOMOTION_DELETED = NO
OLD_IKR_QUINN_DELETED = YES
RETIRED_RUNTIME_ASSET_COUNT_REMAINING = 4
RETIRED_RUNTIME_REFERENCE_COUNT_REMAINING = 31 direct references (17 Character + 11 AnimBP + 2 BPI + 1 BlendSpace)
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0 in canonical runtime closure
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 in canonical runtime closure
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 in canonical Character package closure
FUTSALPLAYERBASE_BROKEN_REFERENCES = 0 observed canonical package audit
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_ABP_COMPILE = PASS (last verified)
CONTROL_RIG_STATUS = PASS (localized ControlRig retained in canonical ABP)
COURT_RUNTIME_SMOKE_TEST = NOT RUN
SEQUENCER_SMOKE_TEST = NOT RUN
REDIRECTOR_COUNT = 0 affected Blueprint directory
BROKEN_REFERENCE_COUNT = 0 observed canonical package audit
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Final Court actor migration manifest (read-only)

All packages below are Asset Registry-confirmed references to both old Character and old AnimBP. Actor GUID, label, transform, component overrides, and sequence binding identity could not be extracted without resolving the owning World Partition actors in the map editor. No Court asset was modified.

| Actor | External Actor Package | Old Actor GUID | Label / current class | Current AnimClass | Sequence bindings | Classification | Required next action |
|---|---|---|---|---|---|---|---|
| ACTOR_01 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/0/WT/YMCVQZR2CN15LPLAV93VBG` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_02 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/2/MU/1O63YR0HRRXX7YKV8XB0CC` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_03 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/2/W9/HL0RUCKR68XNENXONPJKM7` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_04 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/4/0J/ALR3VDS47OIJN6AQCXWY1C` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_05 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/5/T1/HSACQ8GZHE74Z3SRSS1B3Y` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_06 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/7/JA/UDBW3WW3NVCOSCPQ0BEGQJ` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_07 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/9/J6/TU6OWM08YYO712ARHTKWJJ` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_08 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/A/US/4OIN0VNN4SXGU575IZFG8R` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_09 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/C/5W/DOL5WE0X6A12MTT1QXAB10` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |
| ACTOR_10 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/D/DY/2JF1A2CZZU5UJQLVP5DNPS` | Unknown | Unknown | Old ABP reference | Unknown | E | Resolve actor in Court editor; then determine replacement and Sequencer rebind |

### Final sequence binding migration table

| Sequence | Player bindings | Rebound | Possessed class | Broken bindings | Old Character dependency | Result |
|---|---:|---:|---|---|---|---|
| `LS_Cam_01` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred to Court actor resolution |
| `LS_Cam_02` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred to Court actor resolution |
| `LS_Cam_03` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred to Court actor resolution |
| `LS_Cam_04` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred to Court actor resolution |
| `LS_Cam_Main` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred; camera child binding must also be retained |
| `LS_Cam_P01` | 10 | 0 | Old Character | Not evaluated after rebind (none performed) | Yes | Deferred; camera child binding must also be retained |

### Final test level and retired deletion chain

| Item | Result |
|---|---|
| `L_FutsalCharacterBase_Test` | Loaded, actor enumeration unavailable, left unchanged |
| Test old Character reference | 1 remains |
| Test old AnimBP reference | 1 remains |
| Old Character | Retain until sequences, test map, and Court actors migrated |
| Old AnimBP | Retain until test map and Court actors migrated |
| Old BPI | Retain while referenced by old Character/AnimBP internal chain |
| Old BlendSpace | Retain while referenced by old AnimBP |
| Old IKR_Quinn | Deleted after zero direct referencers |

```text
Court actor migration + test map migration
    -> resolve/rebind six LevelSequence possessables
    -> remove old Character and AnimBP live consumers
    -> delete BP_FutsalCharacterBase and ABP_FutsalSource
    -> rescan internal chain
    -> delete BPI_FutsalAnimationSource and BS_Futsal_Locomotion when zero-reference
```

## BASE-1Y — RETIRED RUNTIME REFERENCER DRAIN AND COURT MIGRATION MANIFEST

- 日期：2026-09-25
- Git remained on `refactor/character-architecture` at HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`; zero staged files. `UNREAL_RIG` retained its pre-existing unstaged worktree modification and was not touched.
- Canonical `BP_FutsalPlayerBase` and `ABP_FutsalPlayerBase` exist and remain up to date. Canonical Character closure has zero old-character, old-interface, old-animation, Mannequin, ThirdPerson, and external project-content dependencies.
- The six `LS_Cam_*` sequences were loaded read-only. Each has zero spawnables and multiple possessable bindings named `Player_L*` / `Player_R*` whose `get_possessed_object_class()` resolves to `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase.BP_FutsalCharacterBase_C`; these bindings have transform tracks. Because they are possessables rather than independent spawnables and their owning-level actors are not resolvable without map inspection, no sequence was changed. Classify them as `COURT_ACTOR_BOUND_SEQUENCE_REFERENCE` pending actor/binding resolution.
- `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` loaded, but current Editor Actor Subsystem returned no actors and the World actor collections are protected by the Python wrapper. The map was not saved or modified. Test-map migration remains unresolved.
- Asset Registry identifies ten `L_FutsalCourt` external actor packages referencing both the old Character and old AnimBP. No Court actor or level package was loaded for mutation. `MANUAL_L_FUTSALCOURT_GATE_REQUIRED = YES`.
- No non-Court runtime referencer was migrated in this phase because sequence possessable ownership and test-map actor structure were not safely resolvable. Old Character, old AnimBP, old BPI, and old BlendSpace remain referenced and were retained.
- `IKR_Quinn` had zero direct referencers and its closure was isolated to Quinn mannequin/IKRig; it was hard-deleted. The protected `UNREAL_RIG` dependency island was not involved.
- Canonical FutsalPlayerBase dependency closure remains free of Mannequin, ThirdPerson, and old runtime dependencies. No affected Blueprint-path redirectors remain.

```text
PHASE_BASE_1Y = PARTIAL
SEQUENCE_TOTAL = 6
SEQUENCE_MIGRATED_COUNT = 0
SEQUENCE_DEFERRED_COURT_BOUND_COUNT = 6
SEQUENCE_UNRESOLVED_COUNT = 0 (possessable class and transform tracks verified; actor ownership requires map inspection)
LS_CAM_01_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
LS_CAM_02_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
LS_CAM_03_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
LS_CAM_04_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
LS_CAM_MAIN_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
LS_CAM_P01_RESULT = DEFERRED_COURT_ACTOR_BOUND_POSSESSABLES
TEST_LEVEL_MIGRATION = NOT_REQUIRED (actor enumeration unresolved; no mutation)
TEST_LEVEL_OLD_CHARACTER_REFERENCES = 1 package referencer
TEST_LEVEL_OLD_ABP_REFERENCES = 1 package referencer
POST_NONCOURT_OLD_CHARACTER_REFERENCER_COUNT = 7 (six sequences + test level)
POST_NONCOURT_OLD_ABP_REFERENCER_COUNT = 1 test level (plus Court actors)
POST_NONCOURT_OLD_INTERFACE_REFERENCER_COUNT = 2 internal retired chain references
POST_NONCOURT_OLD_BLENDSPACE_REFERENCER_COUNT = 1 old AnimBP internal reference
L_FUTSALCOURT_EXTERNAL_ACTOR_COUNT = 10
COURT_CLASS_REPLACEMENT_COUNT = 10 candidate old Character external actors; details not inspectable
COURT_ANIMCLASS_ONLY_REPLACEMENT_COUNT = 0 confirmed
COURT_SEQUENCE_BOUND_ACTOR_COUNT = 6 sequences, actor identity resolution deferred
COURT_UNKNOWN_ACTOR_COUNT = 10 until actor packages are resolved in map editor
COURT_MIGRATION_MANIFEST_READY = PARTIAL
MANUAL_L_FUTSALCOURT_GATE_REQUIRED = YES
OLD_RUNTIME_DELETION_BLOCKED_ONLY_BY_COURT = NO (six LevelSequence references and one test level also remain)
OLD_IKR_QUINN_DELETED = YES
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 in canonical Character/AnimBP closure
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 in canonical Character/AnimBP closure
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_ABP_COMPILE = PASS (last verified)
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Final sequence binding table

| Sequence | Old Character possessables | Spawnables | Binding track evidence | Result |
|---|---:|---:|---|---|
| `LS_Cam_01` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |
| `LS_Cam_02` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |
| `LS_Cam_03` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |
| `LS_Cam_04` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |
| `LS_Cam_Main` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |
| `LS_Cam_P01` | 10 | 0 | Player bindings expose transform tracks | Deferred; map actor ownership unresolved |

The Level Sequence API showed possessable bindings, not spawnables. Bindings' possessed class resolves to the old Character; binding GUIDs and display names were available, but actor resolution requires the owning map and is deferred.

### Final test-level migration table

| Asset | Evidence | Result |
|---|---|---|
| `L_FutsalCharacterBase_Test` | Asset Registry references old Character and old AnimBP; map loaded read-only; current Actor Subsystem returned zero actors and World actor arrays are protected | Not modified; migration unresolved |

### Post-non-Court retired referencer table

| Retired asset | Remaining referencers | Disposition |
|---|---|---|
| `BP_FutsalCharacterBase` | Six camera sequences, test level, ten Court external actor packages | Retained |
| `ABP_FutsalSource` | Test level and ten Court external actor packages | Retained |
| `BPI_FutsalAnimationSource` | Old Character and old AnimBP internal chain | Retained |
| `BS_Futsal_Locomotion` | Old AnimBP internal chain | Retained |
| `IKR_Quinn` | None | Hard-deleted |

### L_FutsalCourt external actor migration manifest

Asset Registry returned these ten external actor packages as references to both old Character and old AnimBP. Actor label, GUID, class component details, transform, instance overrides, and sequence bindings were not available without loading/inspecting `L_FutsalCourt`, which remains read-only in this phase.

| Actor | External package | Actor GUID/label/class/transform | Current AnimClass | Sequence bindings | Classification | Next operation | Target | Risk |
|---|---|---|---|---|---|---|---|---|
| ACTOR_01 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/0/WT/YMCVQZR2CN15LPLAV93VBG` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_02 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/2/MU/1O63YR0HRRXX7YKV8XB0CC` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_03 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/2/W9/HL0RUCKR68XNENXONPJKM7` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_04 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/4/0J/ALR3VDS47OIJN6AQCXWY1C` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_05 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/5/T1/HSACQ8GZHE74Z3SRSS1B3Y` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_06 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/7/JA/UDBW3WW3NVCOSCPQ0BEGQJ` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_07 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/9/J6/TU6OWM08YYO712ARHTKWJJ` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_08 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/A/US/4OIN0VNN4SXGU575IZFG8R` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_09 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/C/5W/DOL5WE0X6A12MTT1QXAB10` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |
| ACTOR_10 | `/Game/__ExternalActors__/FutsalMOT/Maps/L_FutsalCourt/D/DY/2JF1A2CZZU5UJQLVP5DNPS` | Unknown | Unknown | Unknown | E | Inspect in Court editor | Determine canonical Character vs AnimClass-only | High |

### Court sequence binding table

| Sequence | Possessable class | Spawnables | Court actor identity | Result |
|---|---|---:|---|---|
| `LS_Cam_01` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |
| `LS_Cam_02` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |
| `LS_Cam_03` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |
| `LS_Cam_04` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |
| `LS_Cam_Main` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |
| `LS_Cam_P01` | Old Character on `Player_*` bindings | 0 | Unknown until actor/map resolution | Defer to Court gate |

### Final retired-asset deletion chain

```text
L_FutsalCourt actor migration (manual gate; not executed)
    + LevelSequence possessable owner resolution (manual gate; not executed)
    + L_FutsalCharacterBase_Test actor inspection/migration (not executed)
        -> old BP_FutsalCharacterBase may become unreferenced
        -> old ABP_FutsalSource may become unreferenced
            -> old BPI_FutsalAnimationSource and BS_Futsal_Locomotion may become internal-only
        -> hard-delete only after fresh direct referencer checks
```

The old runtime deletion chain is not ready. No retired runtime asset other than unreferenced `IKR_Quinn` was deleted.

## BASE-1X — CHARACTER CANONICALIZATION AND RUNTIME REFERENCER MIGRATION

- 日期：2026-09-25
- The clean Character was revalidated, hard-deleted from the contaminated canonical package only after zero direct referencers, and renamed to `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`.
- Canonical generated class: `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C`. The promoted Blueprint compiled successfully and was saved. `_Clean` package no longer exists. No graph reconstruction occurred during promotion.
- Canonical Character package dependencies are the Futsal input actions, `BPI_FutsalTouchInterface`, and required Engine/Input modules. Old-character, old-animation-interface, old AnimBP, old BlendSpace, old IKR, Mannequin, and ThirdPerson dependencies are all zero on the canonical Character package.
- Project-wide referencer scan found six camera Level Sequences and the test map `/Game/FutsalMOT/Test/L_FutsalCharacterBase_Test` referencing the retired `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase`. The test map and `L_FutsalCourt` external actors also reference `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource`. The six sequence bindings and test map actor ownership were not migrated because direct semantic replacement could not be proven without inspecting/editing those assets.
- `L_FutsalCourt` has multiple external actor package referencers to the old Character and old AnimBP. The map was not opened or modified. `MANUAL_L_FUTSALCOURT_GATE_REQUIRED = YES`.
- Old `BPI_FutsalAnimationSource` remains referenced by old `BP_FutsalCharacterBase` and old `ABP_FutsalSource`; old `BS_Futsal_Locomotion` remains referenced by old `ABP_FutsalSource`. Those old packages were retained because they have legitimate remaining referencers.
- Old `IKR_Quinn` had zero referencers and depended only on the Quinn mannequin mesh and IKRig module. It was hard-deleted; the protected `UNREAL_RIG` island was not involved.
- No redirectors remain in the affected Blueprint directory. Full project closure still contains unrelated Mannequin assets through the retained retired animation assets; no broad cleanup was performed.
- `UNREAL_RIG` remains at its pre-existing unstaged worktree state. No Git staging, commit, tag, or push occurred.

```text
PHASE_BASE_1X = PARTIAL
CLEAN_CHARACTER_FINAL_VALIDATION = PASS
CONTAMINATED_CHARACTER_DELETED = YES
CLEAN_CHARACTER_RENAMED_TO_CANONICAL = YES
OLD_CLEAN_PACKAGE_EXISTS = NO
CANONICAL_CHARACTER_OBJECT_PATH = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase
CANONICAL_CHARACTER_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C
CANONICAL_CHARACTER_COMPILE = PASS
CANONICAL_CHARACTER_OLD_CHARACTER_DEPENDENCIES = 0
CANONICAL_CHARACTER_OLD_INTERFACE_DEPENDENCIES = 0
CANONICAL_CHARACTER_MANNEQUIN_DEPENDENCIES = 0
CANONICAL_CHARACTER_THIRDPERSON_DEPENDENCIES = 0
CANONICAL_CHARACTER_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
RUNTIME_REFERENCER_SCAN = PASS
RUNTIME_REFERENCES_MIGRATED_COUNT = 0
L_FUTSALCOURT_REFERENCES_OLD_CHARACTER = 10 external actor packages
L_FUTSALCOURT_REFERENCES_CANONICAL_CHARACTER = 0 observed
MANUAL_L_FUTSALCOURT_GATE_REQUIRED = YES
OLD_BP_FUTSALCHARACTERBASE_REFERENCER_COUNT = 17
OLD_ABP_FUTSALSOURCE_REFERENCER_COUNT = 11
OLD_BPI_FUTSALANIMATIONSOURCE_REFERENCER_COUNT = 2
OLD_BS_FUTSAL_LOCOMOTION_REFERENCER_COUNT = 1
OLD_IKR_QUINN_REFERENCER_COUNT = 0
OLD_BP_FUTSALCHARACTERBASE_DELETED = NO
OLD_ABP_FUTSALSOURCE_DELETED = NO
OLD_BPI_FUTSALANIMATIONSOURCE_DELETED = NO
OLD_BS_FUTSAL_LOCOMOTION_DELETED = NO
OLD_IKR_QUINN_DELETED = YES
FUTSALPLAYERBASE_MANNEQUIN_DEPENDENCIES = 0 (canonical Character/ABP closure)
FUTSALPLAYERBASE_THIRDPERSON_DEPENDENCIES = 0
FUTSALPLAYERBASE_OLD_RUNTIME_DEPENDENCIES = 0 (canonical Character package closure)
FUTSALPLAYERBASE_UNWANTED_PROJECT_ARCHITECTURE_DEPENDENCIES = 0 (canonical Character package)
BROKEN_REFERENCE_COUNT = 0 observed canonical Character/ABP; map actors not modified
REDIRECTOR_COUNT = 0 affected Blueprint directory
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Final runtime referencers and retained assets

| Retired asset | Remaining referencers | Disposition |
|---|---|---|
| `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase` | Six camera sequences, test level, ten `L_FutsalCourt` external actor packages | Retained |
| `/Game/FutsalMOT/Animation/Source/ABP_FutsalSource` | Test level and ten `L_FutsalCourt` external actor packages | Retained |
| `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource` | Old Character Blueprint and old AnimBP | Retained |
| `/Game/FutsalMOT/Animation/BS_Futsal_Locomotion` | Old AnimBP | Retained |
| `/Game/FutsalMOT/Animation/Retarget/IKR_Quinn` | None | Hard-deleted |

Canonicalization and Character promotion are complete, but old runtime cleanup is partial. Continue only after a dedicated runtime-reference migration gate addresses the test/sequence references and the manually protected `L_FutsalCourt` gate.

## BASE-1W Final Clean Character Purity Audit

- 日期：2026-09-25
- Read-only live audit; Asset Registry rescan completed. No Blueprint compile or asset save was performed during this audit.
- Clean asset `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean` exists, parent `/Script/Engine.Character`, generated class `BP_FutsalPlayerBase_Clean_C`, current status `BS_UP_TO_DATE`.
- The package dependency closure contains Engine/Input runtime modules, the four Futsal Enhanced Input actions, and `BPI_FutsalTouchInterface`. Counts for the old character, old animation interface, old AnimBP, old BlendSpace, old IKR, Mannequin, ThirdPerson, and external project-content dependencies are zero.
- `AnimationClassId` exists and its exported pin type is `int`; default and exposure flags were not readable from the current Python wrapper. `MotionSpeedMps` is absent from the exposed local variable list.
- Graph inventory includes `Move`, `Aim`, `EventGraph`, and `UserConstructionScript`, but `BlueprintTools.read_graph_dsl` returns empty bodies and Python marks `EdGraph.Nodes` protected. Function semantics, Enhanced Input links, actual interface-event ownership, custom-event substitutions, and graph-level errors remain unknown.
- Implemented interface metadata and SCS component templates are inaccessible through the current API. Touch interface is Asset Registry-confirmed as a dependency only; semantic interface implementation remains unknown. Camera and inherited Mesh settings remain GUI-verified but API-unresolved.
- Raw ASCII and UTF-16LE scans found none of the requested obsolete package/name strings in the clean package.
- Direct referencer queries returned zero referencers for clean and source Character Blueprints. No Blueprint-directory redirectors were detected. The Asset Registry direct lookup for `L_FutsalCourt` did not produce iterable data, so its direct-reference result remains unknown; the map was not opened or changed.
- `CLEAN_PACKAGE_PURITY = FAIL` because graph, interface, component, and complete broken-reference verification remains inaccessible. `READY_FOR_CANONICALIZATION = NO`.
- The canonical source Character Blueprint still exists. Protected `UNREAL_RIG` remains in the same pre-existing unstaged worktree state.

```text
PHASE_BASE_1W_FINAL_PURITY_AUDIT = COMPLETE
CLEAN_CHARACTER_EXISTS = YES
CLEAN_CHARACTER_PARENT_CLASS = /Script/Engine.Character
CLEAN_CHARACTER_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean.BP_FutsalPlayerBase_Clean_C
CLEAN_CHARACTER_COMPILE = BS_UP_TO_DATE
BPI_FUTSAL_TOUCH_INTERFACE_IMPLEMENTED = UNKNOWN (metadata API unavailable; dependency present)
OLD_BPI_FUTSAL_ANIMATION_SOURCE_IMPLEMENTED = UNKNOWN (metadata API unavailable; dependency absent)
ANIMATIONCLASSID_PRESENT = YES
ANIMATIONCLASSID_TYPE = int / Int32
ANIMATIONCLASSID_DEFAULT = UNKNOWN
MOTIONSPEEDMPS_PRESENT = NO (absent from exposed member-variable list)
MOVE_FUNCTION_PRESENT = YES (graph object present; body unreadable)
AIM_FUNCTION_PRESENT = YES (graph object present; body unreadable)
GETMOTIONSPEEDMPS_PRESENT = NO observed
TOUCH_INTERFACE_EVENT_COUNT = UNKNOWN
TOUCH_INTERFACE_EVENTS_ARE_REAL_INTERFACE_EVENTS = UNKNOWN
TOUCH_CUSTOM_EVENT_SUBSTITUTION_COUNT = UNKNOWN
CAMERA_BOOM_PRESENT = UNKNOWN (SCS unavailable)
FOLLOW_CAMERA_PRESENT = UNKNOWN (SCS unavailable)
FOLLOW_CAMERA_PARENT = UNKNOWN
CLEAN_MESH = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_ANIMATION_MODE = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_ANIM_CLASS = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_LOCATION = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_ROTATION = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_SCALE = GUI_VERIFIED_BUT_API_UNRESOLVED
OLD_BP_FUTSALCHARACTERBASE_DEPENDENCIES = 0
OLD_BPI_FUTSALANIMATIONSOURCE_DEPENDENCIES = 0
OLD_ABP_FUTSALSOURCE_DEPENDENCIES = 0
OLD_BS_FUTSAL_LOCOMOTION_DEPENDENCIES = 0
OLD_IKR_QUINN_DEPENDENCIES = 0
CLEAN_MANNEQUIN_DEPENDENCIES = 0
CLEAN_THIRDPERSON_DEPENDENCIES = 0
CLEAN_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
CLEAN_BROKEN_REFERENCES = UNKNOWN (complete K2 node enumeration inaccessible)
CLEAN_BINARY_OLD_CHARACTER_STRING_PRESENT = NO
CLEAN_BINARY_OLD_INTERFACE_STRING_PRESENT = NO
CLEAN_BINARY_GETMOTIONSPEEDMPS_STRING_PRESENT = NO
CLEAN_BINARY_MOTIONSPEEDMPS_STRING_PRESENT = NO
CLEAN_CHARACTER_REFERENCER_COUNT = 0
SOURCE_CHARACTER_REFERENCER_COUNT = 0
L_FUTSALCOURT_REFERENCES_CLEAN = UNKNOWN (direct AssetData lookup unavailable)
L_FUTSALCOURT_REFERENCES_SOURCE = UNKNOWN (direct AssetData lookup unavailable)
AFFECTED_PATH_REDIRECTOR_COUNT = 0
CLEAN_PACKAGE_PURITY = FAIL
READY_FOR_CANONICALIZATION = NO
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

Canonicalization blockers: verify the Touch interface implementation; inspect `Move`, `Aim`, EventGraph links, and interface-event ownership in Blueprint Editor; inspect CameraBoom/FollowCamera SCS hierarchy and Mesh binding; run an editor-level broken-node audit; and confirm direct `L_FutsalCourt` reference state without modifying the map.

## BASE-1W Final Clean Character Purity Audit

- 日期：2026-09-25
- Live branch `refactor/character-architecture`, HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`. Protected `UNREAL_RIG` remains in its pre-existing unstaged modified state; no staging or commit occurred.
- Read-only Asset Registry rescan completed. No Unreal assets were modified, compiled, saved, or repaired in this audit.
- `BP_FutsalPlayerBase_Clean` exists as a Blueprint with parent `/Script/Engine.Character`, generated class `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean.BP_FutsalPlayerBase_Clean_C`, compile status `BS_UP_TO_DATE`.
- Current package dependencies are `/Script/NavigationSystem`, `/Script/EnhancedInput`, the four Futsal input actions, `/Game/FutsalMOT/Input/Touch/BPI_FutsalTouchInterface`, and `/Script/InputBlueprintNodes`. All forbidden old character/interface/animation/retarget, Mannequin, ThirdPerson, and external project-content dependency counts are zero.
- Asset Registry reports zero direct referencers for the clean and source Character Blueprints. No redirectors were found under the affected Blueprint directory. A direct level AssetData query for `L_FutsalCourt` was unavailable; no level was opened or modified.
- `AnimationClassId` exists; its stored pin type exports as `PinCategory="int"`. The exposed API did not provide its default or instance-editable/cinematics flags. `MotionSpeedMps` is absent from the exposed local member list.
- Graph inventory lists `Move`, `Aim`, `EventGraph`, and `UserConstructionScript`, but native graph DSL returned empty graph bodies and the Python wrapper blocks access to `EdGraph.Nodes`. Thus function semantics, input bindings, interface event identity, CustomEvent substitutions, unexpected graph nodes, and graph-level broken references remain unknown.
- Implemented-interface metadata and SCS/component templates are inaccessible through the current API. Touch interface presence is Asset Registry-confirmed only; semantic implementation remains unknown. Camera components and mesh binding could not be re-read through API; those values remain GUI-verified but API-unresolved from the manual gate.
- ASCII and UTF-16LE scans found none of the requested obsolete strings in the clean package.
- Clean package purity is not certified because semantic graph/interface/component and broken-node inspection is incomplete. Canonicalization remains blocked.

```text
PHASE_BASE_1W_FINAL_PURITY_AUDIT = COMPLETE
CLEAN_CHARACTER_EXISTS = YES
CLEAN_CHARACTER_PARENT_CLASS = /Script/Engine.Character
CLEAN_CHARACTER_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean.BP_FutsalPlayerBase_Clean_C
CLEAN_CHARACTER_COMPILE = BS_UP_TO_DATE
BPI_FUTSAL_TOUCH_INTERFACE_IMPLEMENTED = UNKNOWN (Asset Registry only)
OLD_BPI_FUTSAL_ANIMATION_SOURCE_IMPLEMENTED = UNKNOWN (Asset Registry dependency absent; metadata API unavailable)
ANIMATIONCLASSID_PRESENT = YES
ANIMATIONCLASSID_TYPE = Integer (PinCategory=int)
ANIMATIONCLASSID_DEFAULT = UNKNOWN
MOTIONSPEEDMPS_PRESENT = NO (absent from exposed local variable list)
MOVE_FUNCTION_PRESENT = YES (graph exists; semantics unknown)
AIM_FUNCTION_PRESENT = YES (graph exists; semantics unknown)
GETMOTIONSPEEDMPS_PRESENT = NO observed
TOUCH_INTERFACE_EVENT_COUNT = UNKNOWN
TOUCH_INTERFACE_EVENTS_ARE_REAL_INTERFACE_EVENTS = UNKNOWN
TOUCH_CUSTOM_EVENT_SUBSTITUTION_COUNT = UNKNOWN
CAMERA_BOOM_PRESENT = UNKNOWN (SCS API unavailable)
FOLLOW_CAMERA_PRESENT = UNKNOWN (SCS API unavailable)
FOLLOW_CAMERA_PARENT = UNKNOWN
CLEAN_MESH = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_ANIMATION_MODE = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_ANIM_CLASS = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_LOCATION = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_ROTATION = GUI_VERIFIED_BUT_API_UNRESOLVED
CLEAN_MESH_RELATIVE_SCALE = GUI_VERIFIED_BUT_API_UNRESOLVED
OLD_BP_FUTSALCHARACTERBASE_DEPENDENCIES = 0
OLD_BPI_FUTSALANIMATIONSOURCE_DEPENDENCIES = 0
OLD_ABP_FUTSALSOURCE_DEPENDENCIES = 0
OLD_BS_FUTSAL_LOCOMOTION_DEPENDENCIES = 0
OLD_IKR_QUINN_DEPENDENCIES = 0
CLEAN_MANNEQUIN_DEPENDENCIES = 0
CLEAN_THIRDPERSON_DEPENDENCIES = 0
CLEAN_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
CLEAN_BROKEN_REFERENCES = UNKNOWN (node arrays inaccessible)
CLEAN_BINARY_OLD_CHARACTER_STRING_PRESENT = NO
CLEAN_BINARY_OLD_INTERFACE_STRING_PRESENT = NO
CLEAN_BINARY_GETMOTIONSPEEDMPS_STRING_PRESENT = NO
CLEAN_BINARY_MOTIONSPEEDMPS_STRING_PRESENT = NO
CLEAN_CHARACTER_REFERENCER_COUNT = 0
SOURCE_CHARACTER_REFERENCER_COUNT = 0
L_FUTSALCOURT_REFERENCES_CLEAN = UNKNOWN (direct level AssetData lookup unavailable)
L_FUTSALCOURT_REFERENCES_SOURCE = UNKNOWN (direct level AssetData lookup unavailable)
AFFECTED_PATH_REDIRECTOR_COUNT = 0
CLEAN_PACKAGE_PURITY = FAIL (semantic verification incomplete)
READY_FOR_CANONICALIZATION = NO
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

Canonicalization blockers: verify implemented interfaces, function semantics, all EventGraph nodes and links, real interface-event ownership, camera component hierarchy, and Blueprint graph errors in the Blueprint Editor; confirm whether `L_FutsalCourt` references either Character Blueprint before replacing the source package.

## Phase BASE-1W — Clean Character Rebuild

- 日期：2026-09-25
- A new blank Blueprint package was created at `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean` with parent `/Script/Engine.Character` using a Blueprint factory. The contaminated source package was not duplicated, modified, compiled, saved, renamed, or deleted.
- The new package compiled and saved successfully. Its initial and final dependency closure contains only `/Script/NavigationSystem`; no old character, old interface, old runtime animation, Mannequin, or ThirdPerson dependency was introduced.
- The clean package remains separate from canonicalization. `READY_FOR_CANONICALIZATION = NO`.
- Inherited Mesh/CharacterMovement component-template access is not exposed deterministically through the current UE 5.8 Python wrapper. Mesh binding, movement defaults, and transforms were not guessed or partially written.
- CameraBoom/FollowCamera source template inspection and deterministic subobject creation were not available through the supported API. No partial camera components were created.
- Interface implementation APIs were not available for the clean Blueprint. `BPI_FutsalTouchInterface` was not added automatically.
- `AnimationClassId` variable creation was attempted only through the supported BlueprintEditorLibrary path, but UE 5.8 rejected the constructed `EdGraphPinType` property access before mutation. No variable was added. `MotionSpeedMps` was not added.
- Move/Aim functions and EventGraph were not reconstructed. No speculative graph logic was written. Verified manual EventGraph inventory remains the known input-to-Move/Aim/Jump contract from the rebuild request.
- The clean package remains `BS_UP_TO_DATE`, has only inherited `UserConstructionScript` and `EventGraph` graphs, and remains free of forbidden dependencies.
- `UNREAL_RIG` retains its pre-existing external worktree modification and was not touched.

```text
PHASE_BASE_1W_CLEAN_CHARACTER_REBUILD = PARTIAL
CLEAN_CHARACTER_CREATED = YES
CLEAN_CHARACTER_CREATION_METHOD = NEW_BLANK_BLUEPRINT_FACTORY
CLEAN_CHARACTER_PATH = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean
CLEAN_CHARACTER_PARENT_CLASS = /Script/Engine.Character
CLEAN_CHARACTER_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase_Clean.BP_FutsalPlayerBase_Clean_C
CLEAN_CHARACTER_COMPILE = PASS
SOURCE_CHARACTER_UNCHANGED = YES
CLEAN_CHARACTER_USER_COMPONENTS = INHERITED_ONLY
CLEAN_CAMERA_BOOM_CREATED = NO
CLEAN_FOLLOW_CAMERA_CREATED = NO
CAMERA_COMPONENT_SETTINGS_TRANSFER = NOT_ATTEMPTED (manual gate)
CLEAN_MESH = NOT_SET (manual gate)
CLEAN_ANIMATION_MODE = NOT_SET (manual gate)
CLEAN_ANIM_CLASS = NOT_SET (manual gate)
CLEAN_MESH_RELATIVE_LOCATION = NOT_SET (manual gate)
CLEAN_MESH_RELATIVE_ROTATION = NOT_SET (manual gate)
CLEAN_MESH_RELATIVE_SCALE = NOT_SET (manual gate)
AI_CONTROLLER_CLASS = NOT_SET (manual gate)
AUTO_POSSESS_PLAYER = NOT_SET (manual gate)
AUTO_POSSESS_AI = NOT_SET (manual gate)
USE_CONTROLLER_ROTATION_PITCH = NOT_SET (manual gate)
USE_CONTROLLER_ROTATION_YAW = NOT_SET (manual gate)
USE_CONTROLLER_ROTATION_ROLL = NOT_SET (manual gate)
ORIENT_ROTATION_TO_MOVEMENT = NOT_SET (manual gate)
USE_CONTROLLER_DESIRED_ROTATION = NOT_SET (manual gate)
ROTATION_RATE = NOT_SET (manual gate)
MAX_WALK_SPEED = NOT_SET (manual gate)
MAX_WALK_SPEED_CROUCHED = NOT_SET (manual gate)
MAX_ACCELERATION = NOT_SET (manual gate)
BRAKING_DECELERATION_WALKING = NOT_SET (manual gate)
GRAVITY_SCALE = NOT_SET (manual gate)
JUMP_Z_VELOCITY = NOT_SET (manual gate)
AIR_CONTROL = NOT_SET (manual gate)
AIR_CONTROL_BOOST_MULTIPLIER = NOT_SET (manual gate)
AIR_CONTROL_BOOST_VELOCITY_THRESHOLD = NOT_SET (manual gate)
BPI_FUTSAL_TOUCH_INTERFACE_IMPLEMENTED = NO (manual gate)
OLD_BPI_FUTSAL_ANIMATION_SOURCE_IMPLEMENTED = NO
ANIMATIONCLASSID_PRESENT = NO (API construction gate)
ANIMATIONCLASSID_TYPE = NOT_CREATED
MOTIONSPEEDMPS_PRESENT = NO
MOVE_FUNCTION_CREATED = NO
AIM_FUNCTION_CREATED = NO
GETMOTIONSPEEDMPS_PRESENT = NO
EVENTGRAPH_RECONSTRUCTED = NO
MANUAL_MESH_GATE_REQUIRED = YES
MANUAL_CAMERA_COMPONENT_GATE_REQUIRED = YES
MANUAL_TOUCH_INTERFACE_GATE_REQUIRED = YES
MANUAL_FUNCTION_GRAPH_GATE_REQUIRED = YES
MANUAL_EVENTGRAPH_GATE_REQUIRED = YES
CLEAN_OLD_CHARACTER_DEPENDENCIES = 0
CLEAN_OLD_INTERFACE_DEPENDENCIES = 0
CLEAN_OLD_ABP_DEPENDENCIES = 0
CLEAN_OLD_BLENDSPACE_DEPENDENCIES = 0
CLEAN_OLD_IKR_DEPENDENCIES = 0
CLEAN_MANNEQUIN_DEPENDENCIES = 0
CLEAN_THIRDPERSON_DEPENDENCIES = 0
CLEAN_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
CLEAN_BROKEN_REFERENCES = 0 observed package-level
CLEAN_BINARY_OLD_CHARACTER_STRING_PRESENT = NO observed
CLEAN_BINARY_OLD_INTERFACE_STRING_PRESENT = NO observed
CLEAN_BINARY_GETMOTIONSPEEDMPS_STRING_PRESENT = NO observed
CLEAN_BINARY_MOTIONSPEEDMPS_STRING_PRESENT = NO observed
CLEAN_PACKAGE_PURITY = PASS
READY_FOR_MANUAL_GRAPH_MIGRATION = YES
READY_FOR_CANONICALIZATION = NO
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

### Final clean character dependency table

| Dependency | Result |
|---|---|
| `/Script/NavigationSystem` | Present as inherited Character module dependency |
| `BP_FutsalCharacterBase` | 0 |
| `BPI_FutsalAnimationSource` | 0 |
| `ABP_FutsalSource` | 0 |
| `BS_Futsal_Locomotion` | 0 |
| `IKR_Quinn` | 0 |
| Mannequin content | 0 |
| ThirdPerson content | 0 |
| External project content | 0 |

### Final clean character component table

| Component | Class | Parent | Creation source | Configuration state | Manual gate required |
|---|---|---|---|---|---|
| CapsuleComponent | Inherited Character component | Character | New blank Character Blueprint | Inherited default | No |
| ArrowComponent | Inherited Character component | Character | New blank Character Blueprint | Inherited default | No |
| Mesh / CharacterMesh0 | Inherited SkeletalMeshComponent | Character | New blank Character Blueprint | Not configured | Yes |
| CharacterMovement | Inherited CharacterMovementComponent | Character | New blank Character Blueprint | Not configured | Yes |
| CameraBoom | SpringArmComponent | Character | Not created | Absent | Yes |
| FollowCamera | CameraComponent | CameraBoom | Not created | Absent | Yes |

### Final clean character defaults table

| Default group | State |
|---|---|
| Character/Pawn defaults | Not configured; manual gate required |
| CharacterMovement defaults | Not configured; manual gate required |
| Mesh binding and transform | Not configured; manual gate required |
| Animation Class | Not configured; manual gate required |

### Manual reconstruction gates

- `MANUAL_MESH_GATE_REQUIRED`: Open `BP_FutsalPlayerBase_Clean`, select `Mesh (CharacterMesh0)`, set `SKM_FutsalPlayerBase`, Use Animation Blueprint, `ABP_FutsalPlayerBase_C`, Location `(0,0,-89)`, Rotation `(0,0,270)`, Scale `(1,1,1)`. Verify by screenshot or Details-panel inspection.
- `MANUAL_CAMERA_COMPONENT_GATE_REQUIRED`: Add `CameraBoom` as SpringArmComponent under the Character root, add `FollowCamera` as CameraComponent under `CameraBoom`, then inspect/copy source component settings from the source Blueprint without copying legacy references.
- `MANUAL_TOUCH_INTERFACE_GATE_REQUIRED`: Class Settings -> Implemented Interfaces -> add only `BPI_FutsalTouchInterface`; compile and save the clean package.
- `MANUAL_CHARACTER_DEFAULTS_GATE_REQUIRED`: Set the GUI-verified AI/Pawn/CharacterMovement values from the BASE-1W request in the clean Blueprint Details panel.
- `MANUAL_VARIABLE_GATE_REQUIRED`: Create Integer `AnimationClassId` only if the intended default/metadata is known; do not create `MotionSpeedMps`.
- `MANUAL_FUNCTION_GRAPH_GATE_REQUIRED`: Recreate exact `Move` and `Aim` functions from source semantics; do not recreate `GetMotionSpeedMps`.
- `MANUAL_EVENTGRAPH_GATE_REQUIRED`: Recreate only verified input links: Look/MouseLook/Secondary Thumbstick -> Aim; Move/Primary Thumbstick -> Move; Jump Started/Touch Jump Start -> Jump; Jump Completed/Touch Jump End -> Stop Jumping. Inspect the source editor for any additional nodes before saving.

### EventGraph migration inventory

Verified source contract supplied for manual migration:

```text
EnhancedInputAction IA_Futsal_Look -> Aim(X Axis, Y Axis)
Event Secondary Thumbstick -> Aim(Axis X, Axis Y)
EnhancedInputAction IA_Futsal_MouseLook -> Aim(X Axis, Y Axis)
EnhancedInputAction IA_Futsal_Move -> Move(X Axis, Y Axis)
Event Primary Thumbstick -> Move(Axis X, Axis Y)
EnhancedInputAction IA_Futsal_Jump Started -> Jump
EnhancedInputAction IA_Futsal_Jump Completed -> Stop Jumping
Event Touch Jump Start -> Jump
Event Touch Jump End -> Stop Jumping
```

No additional unseen nodes are claimed. The clean package is ready for manual graph migration but not for canonicalization.

## Phase BASE-1V-DEPENDENCY-FORENSICS — BP_FutsalPlayerBase Legacy Dependency Audit

- 日期：2026-09-25
- Read-only forensic audit. The Asset Registry was rescanned and Unreal garbage collection completed. No Unreal asset was modified, compiled, saved, or repaired.
- Live branch is `refactor/character-architecture` at HEAD `99a9b758bdb733eaa867fd4a9c6011eda28c8d3e`. `UNREAL_RIG` remains in its pre-existing unstaged worktree state; no files are staged.
- `BP_FutsalPlayerBase` exists, has parent `/Script/Engine.Character`, generated class `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C`, and reports `BS_UP_TO_DATE`.
- Asset Registry category probes report the old character package through Soft and Manage queries, and the old interface through Soft and SearchableName queries. These probes do not expose a unique single category because UE dependency options overlap in the current API surface.
- Parent metadata contradicts `BP_FutsalCharacterBase` as the Blueprint parent. The exposed Blueprint metadata APIs do not expose implemented-interface records, inherited component templates, or complete K2 node enumeration for this asset.
- `AnimationClassId` remains in the local member-variable listing. `MotionSpeedMps` is absent from that listing. The old `GetMotionSpeedMps` graph could not be conclusively enumerated through the current wrapper.
- Raw package scan found ASCII occurrences of both suspect package/name families and the obsolete function/variable names. No UTF-16LE occurrences were found. Serialized strings alone are not treated as semantic proof.
- Because reachable K2/component/interface semantics cannot be exhaustively inspected through the current API, both suspect dependencies remain `UNKNOWN`. No repair was attempted.
- A clean rebuild is not required by proven evidence yet; if contamination is confirmed, a new blank Blueprint rebuild would be required and would include a manual graph gate.

```text
PHASE_BASE_1V_DEPENDENCY_FORENSICS = COMPLETE
OLD_CHARACTER_DEPENDENCY_CATEGORY = SOFT + MANAGE (overlapping Asset Registry queries)
OLD_INTERFACE_DEPENDENCY_CATEGORY = SOFT + SEARCHABLENAME (overlapping Asset Registry queries)
PARENT_CLASS = /Script/Engine.Character
OLD_CHARACTER_IS_PARENT = NO
OLD_INTERFACE_IMPLEMENTED_BLUEPRINT_METADATA = UNKNOWN (API unavailable)
OLD_INTERFACE_IMPLEMENTED_GENERATED_CLASS_METADATA = UNKNOWN (API unavailable)
OLD_GETMOTIONSPEEDMPS_GRAPH_PRESENT = UNKNOWN
OLD_MOTIONSPEEDMPS_VARIABLE_PRESENT = NO (absent from exposed local variable listing)
OLD_CHARACTER_K2_REFERENCE_COUNT = UNKNOWN
OLD_INTERFACE_K2_REFERENCE_COUNT = UNKNOWN
OLD_CHARACTER_VARIABLE_REFERENCE_COUNT = 0 exposed
OLD_INTERFACE_VARIABLE_REFERENCE_COUNT = 0 exposed
OLD_CHARACTER_COMPONENT_TEMPLATE_REFERENCE_COUNT = UNKNOWN
OLD_INTERFACE_COMPONENT_TEMPLATE_REFERENCE_COUNT = UNKNOWN
OLD_CHARACTER_CDO_REFERENCE_COUNT = UNKNOWN
OLD_INTERFACE_CDO_REFERENCE_COUNT = UNKNOWN
OLD_CHARACTER_BINARY_STRING_PRESENT = YES (ASCII)
OLD_INTERFACE_BINARY_STRING_PRESENT = YES (ASCII)
GETMOTIONSPEEDMPS_BINARY_STRING_PRESENT = YES (ASCII)
MOTIONSPEEDMPS_BINARY_STRING_PRESENT = YES (ASCII)
OLD_CHARACTER_CLASSIFICATION = UNKNOWN
OLD_INTERFACE_CLASSIFICATION = UNKNOWN
PACKAGE_CONTAMINATION_CONFIRMED = UNKNOWN
CLEAN_REBUILD_REQUIRED = UNKNOWN
CLEAN_REBUILD_AUTOMATION_LEVEL = MANUAL_GRAPH_GATE_REQUIRED
TARGET_BP_COMPILE_STATE = BS_UP_TO_DATE
TARGET_BP_BROKEN_REFERENCES = UNKNOWN (complete node enumeration unavailable)
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

`MANUAL_GATE_REQUIRED = INSPECT_BLUEPRINT_EDITOR_CLASS_SETTINGS, MY_BLUEPRINT, COMPONENT_TEMPLATES, AND ALL_GRAPH_NODES_TO_RESOLVE_UNKNOWN_DEPENDENCIES`

Stop before any cleanup or clean rebuild.

## Phase BASE-1V-FINAL-AUDIT — Character Blueprint Binding Verification

- 日期：2026-09-25
- Read-only audit. Asset Registry was rescanned and Unreal garbage collection completed before querying the target. No Unreal asset was modified, compiled, or saved.
- `BP_FutsalPlayerBase` exists at `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase`, has parent `/Script/Engine.Character`, generated class `/Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C`, and reports `BS_UP_TO_DATE` with a valid generated class.
- The expected canonical mesh, Animation Mode, Anim Class, and mesh relative transform values are `GUI-VERIFIED_FROM_MANUAL_GATE`; inherited component-template reads are not exposed reliably through the current UE 5.8 Python wrapper. No values were inferred.
- Package closure still includes `/Game/FutsalMOT/Characters/Base/BP_FutsalCharacterBase` and `/Game/FutsalMOT/Animation/Interfaces/BPI_FutsalAnimationSource`, despite the reported manual cleanup. Classification for the old character dependency is `UNKNOWN`; no repair was attempted. Stop before the next binding gate.
- Expected retained project dependencies include input actions `IA_Futsal_Jump`, `IA_Futsal_Look`, `IA_Futsal_MouseLook`, `IA_Futsal_Move`, and `BPI_FutsalTouchInterface`.
- Target Blueprint has zero direct Asset Registry referencers. No redirectors were found under the affected character Blueprint directory. Graph-node broken-reference audit was limited because this Blueprint API wrapper does not provide `get_nodes_of_class`; compile status and valid generated class were observed.
- The canonical `BP_FutsalPlayerControllerBase` exists, parent `/Script/Engine.PlayerController`; it has zero direct referencers and depends on Enhanced Input and the two Futsal input mapping contexts. The target character's current assigned controller class could not be read through the exposed wrapper.
- `UNREAL_RIG` remains in its pre-existing unstaged worktree-modified state.

```text
PHASE_BASE_1V_FINAL_AUDIT = BLOCKED
TARGET_CHARACTER_PARENT_CLASS = /Script/Engine.Character
TARGET_CHARACTER_GENERATED_CLASS = /Game/FutsalMOT/Characters/FutsalPlayerBase/Blueprints/BP_FutsalPlayerBase.BP_FutsalPlayerBase_C
TARGET_CHARACTER_COMPILE = BS_UP_TO_DATE
CANONICAL_MESH_BINDING = GUI-VERIFIED_FROM_MANUAL_GATE
CANONICAL_ANIMATION_MODE = GUI-VERIFIED_FROM_MANUAL_GATE
CANONICAL_ANIM_CLASS = GUI-VERIFIED_FROM_MANUAL_GATE
MESH_TRANSFORM_PRESERVED = GUI-VERIFIED_FROM_MANUAL_GATE
OLD_BP_FUTSALCHARACTERBASE_DEPENDENCIES = 1 (UNKNOWN)
OLD_BPI_FUTSALANIMATIONSOURCE_DEPENDENCIES = 1
OLD_ABP_FUTSALSOURCE_DEPENDENCIES = 0
OLD_BS_FUTSAL_LOCOMOTION_DEPENDENCIES = 0
OLD_IKR_QUINN_DEPENDENCIES = 0
TARGET_CHARACTER_REFERENCER_COUNT = 0
AFFECTED_PATH_REDIRECTOR_COUNT = 0
OLD_GETMOTIONSPEEDMPS_PRESENT = UNKNOWN
OLD_MOTIONSPEEDMPS_VARIABLE_PRESENT = NO (name absent from local member-variable list)
BPI_FUTSAL_TOUCH_INTERFACE_PRESENT = YES (package dependency)
ANIMATIONCLASSID_PRESENT = YES
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```

`MANUAL_GATE_REQUIRED = INVESTIGATE_STALE_BP_FUTSALCHARACTERBASE_AND_OLD_BPI_DEPENDENCIES; VERIFY_MESH_BINDING_DETAILS_IN_BLUEPRINT_EDITOR`

Stop before binding changes. Re-audit after the stale package dependencies have been explained or removed in a separately authorized phase.
CANONICAL_SEQUENCE_COUNT = 20
CANONICAL_LOCOMOTION_COUNT = 17
CANONICAL_MAIN_STATE_COUNT = 3
FAILED_CANONICAL_SEQUENCE_COUNT = 0
CANONICAL_ANIMATION_LIBRARY_INTEGRITY = PASS
DIRECTIONAL_WALK_DISTINCT = YES
DIRECTIONAL_JOG_DISTINCT = YES
IDLE_TARGET = PASS
JUMP_TARGET = PASS
FALL_TARGET = PASS
LAND_TARGET = PASS
CANONICAL_BLENDSPACE_SAMPLE_COUNT = 27
CANONICAL_BLENDSPACE_INTERNAL_REFERENCE_COUNT = 27
CANONICAL_BLENDSPACE_EXTERNAL_REFERENCE_COUNT = 0
CANONICAL_BLENDSPACE_UNIQUE_ANIMATION_COUNT = 17
CANONICAL_BLENDSPACE_MAPPING = PASS
CANONICAL_ANIMATION_EXTERNAL_PROJECT_CONTENT_DEPENDENCIES = 0
DEFECTIVE_CANONICAL_SEQUENCE_COUNT_REMAINING = 0
DEFECTIVE_CANONICAL_BLENDSPACE_COUNT_REMAINING = 0
FAILED_ZERO_OPERATION_IKRETARGETER = DELETED
IKR_FUTSALPLAYERBASE_CLASS = IKRigDefinition
MIGRATION_REPAIR_ASSETS_REMAINING = 0
CLEAN_ABP_IDLE_REFERENCE_VALID = NOT_APPLICABLE (Idle node not yet migrated)
BROKEN_REMAINING_ASSET_REFERENCES = NOT_AUDITED_FOR FULL PROJECT
ANIMATION_MIGRATION_REDIRECTORS = NOT_AUDITED_FOR FULL PROJECT
UNREAL_RIG_STATUS = UNCHANGED_FROM_BASELINE
GIT_STAGED_FILES = 0
GIT_COMMIT_CREATED = NO
```
