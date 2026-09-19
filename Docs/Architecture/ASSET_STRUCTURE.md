# ASSET_STRUCTURE — 项目资产结构

- 更新时间：2026-09-19
- 基线：`de611502964937e16f92fa06d28f86be0c28a33c`
- 分类图例：`PRODUCTION` / `TEMPLATE_BASELINE` / `EXPERIMENTAL` / `ARCHIVE`

## /Game/FutsalMOT

```
/Game/FutsalMOT
├── Animation                              [PRODUCTION + EXPERIMENTAL]
│   ├── Source/                            [PRODUCTION]   ABP_FutsalSource（MASTER_ANIMBP）
│   ├── Interfaces/                        [PRODUCTION]   BPI_FutsalAnimationSource
│   ├── SoccerSource/                      [EXPERIMENTAL] LS_*_InPlace ×7（SK_Mannequin，未接线，未来动画库）
│   ├── Retarget/                          [EXPERIMENTAL] IKR_Quinn, IKR_SoccerPlayer, RTG_Quinn_To_SoccerPlayer
│   ├── SoccerPlayer/                      [EXPERIMENTAL] ABP_FutsalPlayer_Soccer, BS_Futsal_Locomotion_Soccer, *_Soccer ×20
│   ├── BS_Futsal_Locomotion              [PRODUCTION]   主动画 BlendSpace（SK_Mannequin）
│   └── ABP_FutsalPlayer                  [ARCHIVE]      遗留 AnimBP（仍留原位，见 cleanup 报告）
├── Characters
│   ├── Base/                              [PRODUCTION]   BP_FutsalCharacterBase（MASTER_CHARACTER）, BP_FutsalPlayerControllerBase
│   └── FutsalPlayer/                      [EXPERIMENTAL] UNREAL_RIG, UNREAL_RIG_Skeleton, ABP_SoccerPlayer, BP_SoccerPlayer, Materials/Textures
├── Input/                                 [PRODUCTION]   IA_Futsal_*, IMC_Futsal_*, BPI_FutsalTouchInterface
├── Maps/                                  [PRODUCTION]   L_FutsalCourt
├── Sequences/                             [PRODUCTION]   LS_Cam_01..04, LS_Cam_Main, LS_Cam_P01
├── Test/                                  [PRODUCTION]   L_FutsalCharacterBase_Test, GM_FutsalInputTest
├── Blueprints/                            [PRODUCTION]   BP_FutsalBall, BP_NoPawnGameMode, BP_FieldKeypoint, BP_Spline*, Pose/**
├── Football/ Materials/ Textures/         [PRODUCTION]   静态资源
└── _Archive/                              [ARCHIVE]
    └── AbandonedExperiments/              BP_PoseRecorder_Proto（本阶段归档）
```

## /Game/ThirdPerson  [TEMPLATE_BASELINE]

```
/Game/ThirdPerson
├── Blueprints/
│   ├── BP_ThirdPersonCharacter            Epic 模板角色类（默认 Mesh=SKM_Quinn_Simple, AnimClass=ABP_FutsalPlayer_C）
│   ├── BP_ThirdPersonCharacter_Soccer     Epic 子类（0 refs）
│   ├── BP_ThirdPersonGameMode / PlayerController
└── Lvl_ThirdPerson                        Epic 模板地图（+ __ExternalActors__）
```

## /Game/Input  [TEMPLATE_BASELINE]

```
/Game/Input
├── Actions/   IA_Move / IA_Look / IA_MouseLook / IA_Jump
├── IMC_Default / IMC_MouseLook
└── Touch/     BPI_TouchInterface, UI_TouchSimple, UI_Thumbstick
```

## /Game/Characters/Mannequins  [TEMPLATE_BASELINE（内含生产依赖）]

```
/Game/Characters/Mannequins
├── Meshes/    SK_Mannequin（MASTER_ANIMATION_SKELETON）, SKM_Quinn_Simple（MASTER_PREVIEW_MESH）, SKM_Manny_Simple
├── Rigs/      CR_Mannequin_FootIK（生产依赖）, CR_Mannequin_Procedural, CR_Mannequin_Body
├── Animations/ ABP_Unarmed, BS_Idle_Walk_Run
└── Anims/     Epic Unarmed / Pistol / Rifle / Death / HitReact 动画库
```

## Docs（仓库根，非 UE 资产）

```
Docs/
├── Architecture/
│   ├── PROJECT_ARCHITECTURE.md
│   ├── ASSET_STRUCTURE.md
│   └── PROJECT_CLEANUP_REPORT.md
└── History/
    ├── PhaseReports/   （Phase 1–4 历史报告 ×14）
    └── Diagnostics/    （预留：纯失败诊断/临时工具问题）
```

## 生产依赖图（核心）

```
L_FutsalCourt
  └─ 10× Player actor (BP_FutsalCharacterBase_C, Mesh=SKM_Quinn_Simple, Anim=ABP_FutsalSource_C)
       └─ BP_FutsalCharacterBase
            ├─ BPI_FutsalAnimationSource
            └─ /Game/FutsalMOT/Input/IA_Futsal_*
       └─ ABP_FutsalSource
            ├─ BPI_FutsalAnimationSource
            ├─ BS_Futsal_Locomotion → MM/MF (Epic Unarmed)
            ├─ SK_Mannequin
            └─ CR_Mannequin_FootIK
```
