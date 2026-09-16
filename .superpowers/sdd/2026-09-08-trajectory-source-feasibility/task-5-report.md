# Task 5：P3-3 有限可行性实验报告

## 范围与约束

- 实验场景：`5_vs_5`。
- 每个候选：`300` 帧，`10 FPS`，seeds `42, 43, 44, 45`。
- 未修改 `grf_runner.py`、seed derivation、Motion Quality 阈值、生产默认值或下游契约。
- 未运行 Camera、UE、MRQ、P01、训练、checkpoint 下载或外部仓库修改。
- 未执行 retry、seed filtering、invalid-seed hiding、人工速度注入或事后帧修复。
- 所有结果均来自本次运行生成的 `.futsalmot/p3_3_feasibility/` 输出。

## GRF-native 可运行性门禁

本次 inventory 输出由 `inventory_grf_sources()` 生成。当前环境中没有可运行的 GRF-native 替代源：

| Source | API/source evidence | Runtime | Disposition |
| --- | --- | ---: | --- |
| `builtin_ai` | `action_set_v2_index_19` | yes | `BASELINE` |
| `bot` | `sample_bot_player` | yes | `NOT_A_COMPLETE_POLICY_SOURCE` |
| `replay` | `replay_player_requires_trace` | yes | `REPLAY_ONLY` |
| `ppo_checkpoint` | `ppo2_cnn_player_requires_checkpoint` | no | `INFEASIBLE_IN_CURRENT_ENVIRONMENT` |
| `grf_marl_policy` | `ippo_mappo_happo_policy_rollout_framework` | no | `INFEASIBLE_IN_CURRENT_ENVIRONMENT` |

具体不可行性证据：仓库内 pinned Google Research Football 目录没有可探测的 `.pkl`、`.ckpt`、`.index` 或 `.data-*` checkpoint 文件；GRF_MARL 只有 rollout framework，当前环境没有可直接运行的 policy/runtime。`bot` 没有完整 5v5 policy 语义，`replay` 没有现成 trace。因此没有执行 GRF-native alternative probe，也没有为不可运行候选制造结果。

## 实验命令

基线命令按任务 brief 原样执行（诊断 runner 增加了显式 `--candidate grf_builtin_ai` 参数）：

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.tools.p3_3_trajectory_source_feasibility baseline --candidate grf_builtin_ai --out-root .futsalmot/p3_3_feasibility/grf_builtin_ai --seeds 42 43 44 45 --frames 300 --fps 10
```

项目原型命令：

```powershell
.venv\Scripts\python.exe -m grf_ue_bridge.tools.p3_3_trajectory_source_feasibility baseline --candidate project_owned_prototype --out-root .futsalmot/p3_3_feasibility/project_owned_prototype_fresh --seeds 42 43 44 45 --frames 300 --fps 10
```

重复命令分别使用了 baseline 的 `repeats/` 和 prototype 的 `prototype_repeats/` 输出根目录，对 seeds `42`、`44` 各运行一次。重复只对实际 runnable candidate 执行；不可运行的 GRF-native candidate 没有 repeat。

## 新鲜结果

### `grf_builtin_ai`

结果文件：`.futsalmot/p3_3_feasibility/grf_builtin_ai/candidate_results.json`

| Seed | Frames | Contract | Global mean speed | Team coverage | Longest low-motion plateau | Strict valid | Generation seconds | Frames SHA-256 |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 42 | 300 | compatible | 0.597 | 0.390 | 15.3s | no | 1.424803 | `9aef1323c3866beac9dcc4bde41dfe01345d2f96c0089db58feef547dd59afe3` |
| 43 | 300 | compatible | 1.361 | 0.760 | 1.3s | no | 0.730064 | `00479967d1b42d3e58d419487f4a291fa7796d3ce7f418c7e3ccbc854586823e` |
| 44 | 300 | compatible | 1.544 | 0.913 | 0.7s | yes | 0.824744 | `62e0703cb78e2a572d47088d330911d7c31be92761c6f7f05774929226484f57` |
| 45 | 300 | compatible | 1.511 | 0.890 | 0.8s | no | 1.102679 | `5f63421194651c0035b59b9027df091a80e3efbabb0e2df68ec61017beb15601` |

Strict-valid count: `1/4`.

Failure summary from the unchanged gate: seed `42` failed `outfield_active_ratio`, `outfield_stationary_streak`, and `team_active_coverage`; seed `43` and `45` were invalid under the existing strict semantics; seed `44` was valid. GK stationary streak remained diagnostic only.

### `project_owned_prototype`

结果文件：`.futsalmot/p3_3_feasibility/project_owned_prototype_fresh/candidate_results.json`

| Seed | Frames | Contract | Global mean speed | Team coverage | Longest low-motion plateau | Strict valid | Generation seconds | Frames SHA-256 |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 42 | 300 | compatible | 1.043 | 0.940 | 0.6s | yes | 0.040381 | `5adb80f23056b0fcec6975efe84973cffba1a5711a68825c75e947de04843ea1` |
| 43 | 300 | compatible | 1.113 | 0.937 | 0.7s | yes | 0.037085 | `ccf0e9da213d0f1134b85c415f09b629f7fe6c768364fae8f02c9cbd2476cf91` |
| 44 | 300 | compatible | 1.106 | 0.947 | 0.7s | yes | 0.037985 | `a4ecb1b75066abf0fa56d273d9b733d64cc9aa542a3226a84547976552c271c2` |
| 45 | 300 | compatible | 1.078 | 0.953 | 0.4s | yes | 0.038518 | `65f761c89aa6d147f3363b2412993e4fe7ddf8b08bed7faaf1931af30861505b` |

Strict-valid count: `4/4`.

该候选是诊断 prototype，不是生产 generator。它使用 seeded phase/role 参数、固定 10 名球员、双方场地侧分离、确定性空间持球交接和球员/球位置输出；没有使用独立随机游走、retry 或事后速度修复。

## Determinism repeats

### GRF baseline

重复结果：

- `.futsalmot/p3_3_feasibility/repeats/grf_builtin_ai/seed_42_repeat.json`
- `.futsalmot/p3_3_feasibility/repeats/grf_builtin_ai/seed_44_repeat.json`

| Seed | First SHA-256 | Repeat SHA-256 | Byte-identical |
| ---: | --- | --- | --- |
| 42 | `9aef1323c3866beac9dcc4bde41dfe01345d2f96c0089db58feef547dd59afe3` | `9aef1323c3866beac9dcc4bde41dfe01345d2f96c0089db58feef547dd59afe3` | yes |
| 44 | `62e0703cb78e2a572d47088d330911d7c31be92761c6f7f05774929226484f57` | `62e0703cb78e2a572d47088d330911d7c31be92761c6f7f05774929226484f57` | yes |

### Project-owned prototype

重复结果：

- `.futsalmot/p3_3_feasibility/prototype_repeats/project_owned_prototype/seed_42_repeat.json`
- `.futsalmot/p3_3_feasibility/prototype_repeats/project_owned_prototype/seed_44_repeat.json`

| Seed | First SHA-256 | Repeat SHA-256 | Byte-identical |
| ---: | --- | --- | --- |
| 42 | `5adb80f23056b0fcec6975efe84973cffba1a5711a68825c75e947de04843ea1` | `5adb80f23056b0fcec6975efe84973cffba1a5711a68825c75e947de04843ea1` | yes |
| 44 | `a4ecb1b75066abf0fa56d273d9b733d64cc9aa542a3226a84547976552c271c2` | `a4ecb1b75066abf0fa56d273d9b733d64cc9aa542a3226a84547976552c271c2` | yes |

## Contract and scope verification

- 两个 runnable candidate 的所有 8 组主结果均为 `frame_count=300`，固定球员 ID 和球位置契约均 `compatible=true`、`errors=[]`。
- 所有候选均只通过 `evaluate_frames_candidate()` 调用现有 `motion_quality.analyze_frames()` 和现有 `assess_motion_quality()`；没有复制或修改 Motion Quality gate。
- 未修改受保护文件：`src/grf_ue_bridge/grf_runner.py`、`src/grf_ue_bridge/seeds.py`、`src/grf_ue_bridge/motion_quality.py`、`pyproject.toml`。
- 首次 prototype 命令曾错误地把 `baseline` 子命令硬编码为 GRF candidate，因此生成了路径 `.futsalmot/p3_3_feasibility/project_owned_prototype/` 下的误标记文件。该输出不纳入证据；修复 runner 后使用 `project_owned_prototype_fresh/` 重新生成并以后的结果作为唯一 prototype 证据。没有依赖该误标记结果进行判断。

## Verification commands

Focused tests after the runner correction:

```text
27 passed in 0.17s
```

Syntax check:

```powershell
python -m py_compile src/grf_ue_bridge/tools/p3_3_trajectory_source_feasibility.py tests/test_p3_3_trajectory_source_feasibility.py
```

Result: exit code `0`.

Whitespace/protected diff check:

```powershell
```

Result: no whitespace errors and no protected production diff. The inner worktree already contained unrelated uncommitted P3 files; none were reverted or included in this Task 5 report.

## Task 5 conclusion

- Current GRF `builtin_ai` baseline is runnable, deterministic and contract-compatible, but only `1/4` bounded seeds are strict-valid and seed `42` exhibits a `15.3s` global low-motion plateau.
- No GRF-native alternative is runnable in the current environment under the no-download/no-install/no-training constraint.
- The project-owned prototype is runnable, deterministic, contract-compatible and `4/4` strict-valid in this bounded diagnostic, but this is insufficient by itself to establish futsal realism or production readiness.
- Task 5 stops here. No production default change, UE integration, Camera/MRQ run, migration, commit or push was performed.
