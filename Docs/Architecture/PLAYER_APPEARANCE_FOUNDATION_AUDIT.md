# PLAYER_APPEARANCE_FOUNDATION_AUDIT — Player Appearance System 资产基础审计

- 执行时间：2026-09-19
- 基线：branch `refactor/character-architecture` @ `c5d1b42f833f7969c77aed15022b6e6f396fc656`（tag `phase5-project-cleanup`）
- 性质：**READ-ONLY APPEARANCE AUDIT**。未修改任何资产；未 stage / commit / tag / push。唯一写入：本报告。
- 目标：为 Player Appearance System（换模型 / 肤色 / 球衣配色 / 号码）建立准确资产基础与参数化设计。动画逻辑继续统一为 `BP_FutsalCharacterBase` + `ABP_FutsalSource` + `SK_Mannequin`。

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| Quinn Mesh | `SKM_Quinn_Simple`：Skeleton `SK_Mannequin`，3 LOD，2 个 Material Slot（`Quinn_01`、`Quinn_02`），PhysicsAsset `PA_Mannequin`，无 Morph Target |
| 槽位材质 | `Quinn_01` → `MI_Quinn_01`（parent `M_Mannequin`）；`Quinn_02` → `MI_Quinn_02`（parent `MI_Quinn_01`） |
| Master 可用参数 | `Paint Tint`（vector，唯一整体染色）、`LogoTint`/`Logo?`/`LogoPosX/Y`/`LogoScale`（单一 UV Logo 贴花）、`Head Cutout`、`EmissivePower`、`MetalPaint*`、`Scale`、`Blend Offset`；贴图参数 `Base Texture`/`BNormal`/`MRA` |
| 是否有专用 Skin/Cloth 颜色参数 | **否**（无 SkinTint / ClothColor / Primary-Secondary Color） |
| 是否可直接 DMI 换色 | **部分**：球衣可用 `Paint Tint`（若有 paint mask）；肤色**无法**直接用现有参数区分 |
| 号码系统 | Epic `Logo` 仅支持**单一**烘焙 Logo（静态开关），**不能**参数化 0–99 |
| 槽位命名 | 非语义（`Quinn_01`/`Quinn_02`）→ 需标准化 |

---

## 1. STEP 1 — Quinn Material Slot Matrix

| Slot | Material | Parent | Body Region（判定） | Skin? | Clothing? | Can Independently Override? |
|---|---|---|---|---|---|---|
| `Quinn_01` | `MI_Quinn_01` | `M_Mannequin` | 主体（皮肤 + 头部） | 是（含） | 否（或基础层） | 是（独立 Slot） |
| `Quinn_02` | `MI_Quinn_02` | `MI_Quinn_01` | 服饰/第二层（上衣/短裤等） | 否 | 是 | 是（独立 Slot） |

- 结论：**A. 独立 Material Slot**（2 个槽可分别覆盖），但槽名无语义；`Quinn_02` 材质是 `Quinn_01` 的**子实例**（共享 master 参数体系）。
- 由于 Quinn 是“Simple/低模”版本，Epic 将其压缩为 2 槽：**不能**把 Skin / Shirt / Shorts / Shoes / Hair 各自独立成槽。要精细分区（肤色 vs 球衣 vs 短裤 vs 袜 vs 鞋），需要**新的分区 Mesh 或 mask 材质**。

> Head/Body/Shirt/Shorts/Shoes/Hair 细分：**当前不满足 A（独立 Slot）**，属于 **B（多区域共享材质）**。参数化必须依赖 **mask + 参数**，而不是槽。

---

## 2. STEP 2 — Material Dependency Audit

### 2.1 材质树

```
M_Mannequin（Master Material，/Game/Characters/Mannequins/Materials/）
   ├─ MI_Quinn_01 (MaterialInstanceConstant；贴图 = T_Quinn_01_{D,N,MRA})
   │     └─ MI_Quinn_02 (MaterialInstanceConstant；贴图 = T_Quinn_02_{D,N,MRA})
   └─（默认贴图 = T_Manny_01_{D,BN,MRA}）
```

### 2.2 参数清单（`M_Mannequin` / 两个 Quinn MI）

| 类型 | 参数 |
|---|---|
| Scalar | `EmissivePower`, `Head Cutout`, `LogoPosX`, `LogoPosY`, `LogoScale`, `MetalPaintMetallic`, `MetalPaintRoughness`, `Scale` |
| Vector | `Blend Offset`, `LogoTint`, **`Paint Tint`** |
| Texture | `Base Texture`, `BNormal`, `MRA` |
| Static Switch | `Logo?` |

### 2.3 是否存在可直接利用的换色参数

| 目标参数 | 是否存在 | 说明 |
|---|---|---|
| BaseColor Tint / Color Tint | 部分 | `Paint Tint`（作用于 paint 区域；默认白=中性） |
| Skin Tint | **否** | master 无肤色专用参数 |
| Cloth Color / Primary / Secondary Color | **否** | 只有单一 `Paint Tint` |
| Pattern / Mask | 间接 | paint/logo 依赖贴图内置 mask（`Base Texture` 通道）；非独立参数 |
| Material Layer | 否 | master 走单一材质栈，无 Material Layer 参数 |

### 2.4 判断：能否用 DMI 实现肤色/球衣颜色

| 目标 | 结论 |
|---|---|
| 球衣颜色 | **可（受限）**：`Paint Tint` 经 DMI 可调，但**只有一种** paint 区颜色，无法 Primary/Secondary/Accent 分离；且 paint mask 是否存在需在材质图确认（本审计未读图内连线） |
| 肤色 | **不可**：无 SkinTint 参数，`Paint Tint` 若作用于服装区则不影响皮肤；直接改 `Base Texture` 需替换贴图 |
| Logo/号码 | `Logo?`+`LogoTint`+`LogoPosX/Y`+`LogoScale` 是**单一 UV 贴花**，Logo 纹理烘焙在 master，不能参数化号码 |

> **未修改材质。**

---

## 3. STEP 3 — Texture / Mask Audit

| Slot | BaseColor | Normal | Mask (MRA) | Opacity/其它 |
|---|---|---|---|---|
| `Quinn_01` | `T_Quinn_01_D` | `T_Quinn_01_N` | `T_Quinn_01_MRA` | `Head Cutout`（scalar）→ 头部遮罩（masked 材质） |
| `Quinn_02` | `T_Quinn_02_D` | `T_Quinn_02_N` | `T_Quinn_02_MRA` | 同上 |
| Master 默认 | `T_Manny_01_D` | `T_Manny_01_BN` | `T_Manny_01_MRA` | — |

- 是否存在区分 Skin / Shirt / Shorts / Shoes / Logo 的独立 mask：**未发现独立 mask 参数**；分区信息若存在，位于 `Base Texture`/`MRA` 的通道中，且无参数暴露。
- ⇒ 要实现 Skin / Kit / Shorts / Socks / Shoes 参数化换色：

```
CUSTOM_MASK_REQUIRED
```

- **本阶段不创建任何 mask / 贴图。**

---

## 4. STEP 4 — UV Audit

| 项 | 结果 |
|---|---|
| UV Channel 数量 | **通过 Python/MCP 无法直接读取**（UE 5.8 未暴露 SkeletalMesh UV channel 计数 API）→ `UV_CHANNEL_COUNT = UNKNOWN（需 UE 编辑器内核查）` |
| UV0 用途 | 由 `Base Texture`/`BNormal`/`MRA` 采样 ⇒ UV0 用于基础材质 |
| 额外 UV channel | UNKNOWN（需编辑器核查） |
| 球衣胸前 / 背部区域是否明确分离 | UNKNOWN |
| 背部是否左右镜像 | UNKNOWN；Epic Mannequin 常以镜像 UV 节省空间 |

- 判定策略（保守）：
  - 由于**无法证明**背部 UV 非镜像，且号码需要正确方向，
    ```
    BACK_NUMBER_ATLAS_DIRECT_UV = UNSUITABLE
    ```
  - 直接在被镜像的背部 UV 上贴“数字 atlas 区域”会导致 12/17 等数字镜像。
- ⇒ 号码系统不应依赖 Quinn 现有背部 UV；需 **dedicated jersey mesh UV** 或 **additional UV channel** 或 **贴花/独立号码面片**（见 STEP 7）。
- **未修改 UV。**

---

## 5. STEP 5 — Skin Tone Implementation Analysis

| 方案 | 视觉质量 | 数据集可重复性 | 资产数量 | 运行期切换 | 保留 Normal/Roughness |
|---|---|---|---|---|---|
| A. 原 Skin Texture + Vector Tint | 中（乘法染色，暗部保留） | 高 | 0 新增 | 极低（1 次 DMI 设参） | ✅ |
| B. Skin Tone LUT / parameter | 高（可控肤色曲线） | 高 | 1 LUT + master | 低 | ✅ |
| C. 每肤色一个 Material Instance | 高 | 中（组合爆炸） | N（0..N） | 低（换 MI） | ✅ |
| D. 完全替换 BaseColor | 高但丢细节 | 低 | N 贴图 | 低 | ❌（丢细节） |

**RECOMMENDED_SKIN_SYSTEM = A + B（`M_FutsalSkin_Master` + `SkinToneId` → `SkinTint`(vector) / 可选 LUT）**

- 使用 **一个** 新 master（未来创建），参数 `SkinTint`（vector）/ `SkinToneId`（用于 LUT 采样），运行期经 DMI 设参。
- 保留 `BNormal` / `MRA`，不复制完整材质、不生成 N 张肤色贴图。
- 与 metadata 的 `SkinToneId` 一一对应（见 STEP 11）。
- 现有 `M_Mannequin` 无 SkinTint，故**未来需新增 master**（本阶段不创建）。

---

## 6. STEP 6 — Kit Color Implementation Analysis

| 方案 | 说明 | 评价 |
|---|---|---|
| Dynamic Material Instance | 一个 `M_FutsalKit_Master` + 每实例 DMI，设 Primary/Secondary/Accent/Shorts/Sock | **推荐**（运行期切换、无资产爆炸） |
| Material Instance presets | 每套球衣一个 MI | 组合多时资产膨胀 |
| Mask-based Master Material | master 用 mask 区分 shirt/shorts/socks/shoes，参数着色 | **推荐基础** |

**RECOMMENDED_KIT_SYSTEM = Mask-based `M_FutsalKit_Master` + Dynamic Material Instance**
- 参数建议：`PrimaryColor`、`SecondaryColor`、`AccentColor`、`ShortsColor`、`SockColor`（vector）+ 可选 `PatternId`。
- 依赖 `CUSTOM_MASK_REQUIRED`（区分 shirt/shorts/socks/shoes 区域）。
- **本阶段不创建** `M_FutsalKit_Master`。

---

## 7. STEP 7 — Jersey Number Architecture（重点）

目标：`JerseyNumber = 0..99`，且**不**创建 100 个材质 / 100 张贴图。

| 方案 | 性能 | 批量实例化 | Sequencer/数据集稳定性 | LOD | 遮挡 | 背部弯曲 | 动画跟随 | front+back | 评价 |
|---|---|---|---|---|---|---|---|---|---|
| A. Number Texture Atlas（TensDigit/OnesDigit 选 UV cell） | 高 | 极好（DMI 2 个标量） | 高（纯参数） | 好（随材质） | 好 | 需 UV 展开 | 材质随骨骼 ✅ | 支持（两个面片/槽） | **推荐**（但依赖合适 UV/面片） |
| B. Decal Component | 中（每 Decal 一个 DrawCall） | 差（每球员一个 Decal 组件） | 中（Deferred Decal 在 MRQ 下需注意） | 一般 | 好 | 贴花随骨骼需 DBuffer 设置 | 需 Skeletal Decal | 支持 | 次选 |
| C. Separate Number Mesh / Plane | 高 | 好（可合批） | 高 | 需自管 LOD | 需偏移防 Z-fight | 需蒙皮绑定脊柱/胸腔 | 蒙皮随骨骼 ✅ | 支持 | **推荐（作为 A 的载体）** |
| D. Runtime RenderTarget / Text | 低（RT 开销、每实例一张） | 差 | 低（RT 生命周期/多线程风险） | 差 | 好 | 好 | 好 | 支持 | 不推荐 |

**RECOMMENDED_JERSEY_NUMBER_SYSTEM = A（Number Atlas）+ C（Dedicated Number Plane）**

- 用一张 `T_NumberAtlas`（10 个数字 cell，或十位/个位两张 atlas），通过 master 的 `TensDigit`/`OnesDigit`（scalar 0–9）在 UV 上选择 cell；每个号码 = DMI 参数，不生成新资产。
- 载体：**独立的号码面片 / dedicated jersey mesh**（蒙皮到 spine/chest 骨骼），因为：
  - Quinn 背部 UV **可能镜像** ⇒ `BACK_NUMBER_ATLAS_DIRECT_UV = UNSUITABLE`；
  - 独立面片可用**专用 UV（0–1 直线展开）**，支持 front + back，且能蒙皮随动。
- 若无法新增网格，退化为 **B. Decal**（见次选）。
- **本阶段不创建号码资产**（`T_NumberAtlas` / number plane / master 均为未来 Phase 5B.2+）。

---

## 8. STEP 8 — Material Slot Consistency Requirement

**RECOMMENDED_MATERIAL_SLOT_STANDARD**

统一语义槽名（新导入模型必须采用；Appearance 系统按**槽名**而非索引匹配）：

| 语义槽名 | 用途 |
|---|---|
| `M_Skin` | 皮肤（含头部） |
| `M_Hair` | 头发（可选） |
| `M_Shirt` | 球衣上衣 |
| `M_Shorts` | 短裤 |
| `M_Socks` | 袜 |
| `M_Shoes` | 鞋 |
| `M_Accessory` | 可选附件 |

- Appearance 系统**不得依赖 Slot Index 0/1/2**，应通过 `get_material_slot_names` 语义匹配；缺失槽降级为整体 Kit 材质。
- 现有 Quinn 槽名 `Quinn_01/Quinn_02` 不符合标准（保留不动；Quinn 作为“简单预览”特例）。

---

## 9. STEP 9 — Appearance Data Model Design

建议结构体（未来在 UE 中定义为 `FPlayerAppearanceConfig`，或写入 JSON 由内层管线生成）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `AppearanceId` | Name/String | 外观配置唯一 ID |
| `BodyVariantId` | Name/String | 体型/模型变体 ID |
| `SkeletalMesh` | SoftObject<SkeletalMesh> | 目标 Mesh（需 `SK_Mannequin` 兼容或走 Retarget） |
| `AppearanceType` | Enum | `Preview` / `Kit` / `Pro` … |
| `SkinToneId` | int32 | 肤色档位 0..N |
| `SkinTint` | LinearColor | 可选覆盖 |
| `KitId` | Name/String | 球衣方案 ID |
| `PrimaryKitColor` | LinearColor | 主色 |
| `SecondaryKitColor` | LinearColor | 副色 |
| `AccentKitColor` | LinearColor | 点缀色 |
| `ShortsColor` | LinearColor | 短裤色 |
| `SockColor` | LinearColor | 袜色 |
| `JerseyNumber` | **int32（0–99）** | 号码；**不得写入材质资产名** |
| `NumberColor` | LinearColor | 号码颜色 |
| `MaterialOverrides` | Array<MaterialInterface> | 可选覆盖材质 |

- `JerseyNumber` 校验：`0 <= n <= 99`；非法值由应用层 clamp / 拒绝。

---

## 10. STEP 10 — Runtime Material Strategy

建议 `BP_FutsalCharacterBase` 应用流程：

```
BeginPlay / ApplyAppearance(AppearanceConfig)
   ↓ 读取 AppearanceConfig
   ↓ SetSkeletalMesh(Mesh)
   ↓ 首次：CreateDynamicMaterialInstance(每个语义槽)
   ↓ 缓存 SkinMID / KitMID / NumberMID（Component→MID 映射）
   ↓ Set Skin Parameters (SkinTint / SkinToneId)
   ↓ Set Kit Parameters (Primary/Secondary/Accent/Shorts/Sock)
   ↓ Set Jersey Number (TensDigit / OnesDigit / NumberColor)
```

- **必须缓存** `SkinMID` / `KitMID` / `NumberMID`，**禁止每 Tick 创建 Material**（CreateDynamicMaterialInstance 很贵）。
- 换外观（号码/颜色）时只 `set_*_parameter_value` 到已缓存的 MID。
- 所有参数变更使用与 metadata 相同的 `AppearanceConfig`（见 STEP 11）。
- 本阶段只设计。

---

## 11. STEP 11 — Dataset Metadata

建议写入 ground truth 的 appearance 元数据（与视觉参数同源）：

```json
{
  "actor_id": "L0",
  "appearance_id": "kit_red_07",
  "body_variant_id": "quinn",
  "skin_tone_id": 2,
  "kit_id": "red_home",
  "jersey_number": 7
}
```

- **视觉参数与 metadata 必须来自同一个 `AppearanceConfig`**，不得从材质资产名/贴图名反推。
- `jersey_number` 为 int（0–99），与视觉渲染使用相同数值。

---

## 12. STEP 12 — Directory Architecture

建议（**本阶段不创建目录**）：

```
/Game/FutsalMOT/Appearance/
├── Data/
│   ├── Players/     FPlayerAppearanceConfig 资产（或 DataAsset）
│   ├── Kits/        Kit 定义
│   └── SkinTones/   肤色定义
├── Materials/
│   ├── Skin/
│   ├── Kits/        M_FutsalKit_Master 等
│   └── Numbers/
├── Textures/
│   ├── Skin/
│   ├── Kits/
│   └── Numbers/     T_NumberAtlas
├── Meshes/
│   ├── Bodies/
│   └── Clothing/
└── Retarget/        外观 Mesh 的重定向链
```

---

## 13. STEP 13 — Quinn Prototype Plan（Phase 5B.2，仅规划）

- 只用 `SKM_Quinn_Simple` 证明三件事：SkinTone switching / Kit color switching / JerseyNumber switching。
- 建议最小测试矩阵：

| 维度 | 取值 |
|---|---|
| SkinTone | 3 个（Light / Medium / Dark） |
| Kit | Red / Blue |
| Number | 7 / 10 / 23 |

- 组合验证（建议覆盖每个维度单变量 + 若干交叉），例如：
  - SkinTone × {Red, Blue} × 7
  - {Light, Medium, Dark} × Blue × 10
  - Red × 23 与 Blue × 23（验证十位/个位 atlas）
- 通过标准：视觉正确、无 T-pose、号码不镜像、参数与 metadata 一致。
- **禁止在本阶段进入实现。**

---

## 14. STEP 14 — PLAYER_MODEL_IMPORT_REQUIREMENTS

| 项 | 要求 |
|---|---|
| Skeleton compatibility | **TYPE A：`SK_Mannequin` 兼容骨骼**（优先）；TYPE B：外部骨骼需建立 IKRig + Retargeter |
| Scale | 1 uu = 1 cm；身高与 Mannequin 参考一致（根高 0，站姿约 170–190cm） |
| Orientation | +X 前向、+Z 上；root 位于双脚间地面 |
| Root bone | 命名 `root`，与 `SK_Mannequin` 层级一致 |
| Material slot semantics | 采用 STEP 8 语义槽名（`M_Skin`/`M_Shirt`/…） |
| Skin material separation | 皮肤与服装必须**分区**（独立槽或 mask） |
| Clothing separation | Shirt/Shorts/Socks/Shoes 尽量分区（或至少 mask 可区分） |
| UV requirements | UV0 供基础材质；号码需**独立 UV/专用面片**（背部不得镜像） |
| LOD | 至少 LOD0–2（Quinn 为 3）；LOD 不得丢失禁用骨骼/材质槽 |
| Physics Asset | 提供与骨骼兼容的 PhysicsAsset（Quinn = `PA_Mannequin`） |
| Retarget requirements | TYPE B 必须提供 IKRig + IKRetargeter，且目标骨架与动画链匹配 |

**TYPE A（SK_Mannequin-compatible）为优先标准**；TYPE B 需完整 Retarget 支持。

---

## 15. STEP 15 — 输出

```
PLAYER_APPEARANCE_FOUNDATION_AUDIT = COMPLETE
SKIN_CUSTOMIZATION = M_FutsalSkin_Master + SkinToneId → SkinTint (DMI)，保留 Normal/MRA（方案 A+B）
KIT_CUSTOMIZATION = Mask-based M_FutsalKit_Master + DMI（Primary/Secondary/Accent/Shorts/Sock）
JERSEY_NUMBER_SYSTEM = Number Atlas (TensDigit/OnesDigit) on dedicated number plane/jersey UV（方案 A+C）；现 Quinn UV 背部镜像 ⇒ BACK_NUMBER_ATLAS_DIRECT_UV = UNSUITABLE
MATERIAL_SLOT_STANDARD = 语义槽名 M_Skin/M_Hair/M_Shirt/M_Shorts/M_Socks/M_Shoes/M_Accessory（不依赖 Slot Index）
APPEARANCE_DATA_MODEL = FPlayerAppearanceConfig（含 JerseyNumber int32 0–99；不写入材质名）
NEW_PLAYER_MODEL_STANDARD = DEFINED（TYPE A 优先）
ASSET_MODIFICATION = NONE
```

### 关键证据

| 事实 | 值 |
|---|---|
| `SKM_Quinn_Simple` Skeleton | `SK_Mannequin` |
| LOD | 3 |
| Material Slots | `Quinn_01`, `Quinn_02` |
| Slot → Material | `MI_Quinn_01`（→`M_Mannequin`）、`MI_Quinn_02`（→`MI_Quinn_01`） |
| Master 换色参数 | 仅 `Paint Tint`（+ `LogoTint` 单一 Logo） |
| Skin 专用参数 | 不存在 |
| Physics Asset | `PA_Mannequin` |
| Morph Targets | 无 |
| UV channel / 背部镜像 | UNKNOWN（API 不可读）→ 保守判 `BACK_NUMBER_ATLAS_DIRECT_UV = UNSUITABLE` |
| CUSTOM_MASK_REQUIRED | 是（区分 Skin/Shirt/Shorts/Socks/Shoes） |

### 未做（自查）

- 未修改 `SKM_Quinn_Simple` / `SK_Mannequin` / 任何 Epic Material / Texture / `BP_FutsalCharacterBase` / `ABP_FutsalSource` / `L_FutsalCourt` / `LS_Cam_*` / Input / Skeleton / AnimSequence / IK / Retarget / ControlRig ✅
- 未创建任何 Material / Texture / Mask / 目录 / 号码资产 ✅
- 未 stage / commit / tag / push；未触碰 `UNREAL_RIG.uasset` ✅
