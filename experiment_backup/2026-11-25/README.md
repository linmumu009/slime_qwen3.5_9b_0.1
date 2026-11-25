# slime / Qwen3.5-9B 实验备份（2026-11-25）

本快照按用户确认的范围，仅备份当前仓库对应的实验。已检查 0、5、6 号机；5、6 号机的项目数据、日志、报告及脚本逐路径、大小、SHA-256 一致，保留一份主快照，并单独保留 0 号机的早期差异版本。

## 内容

三份压缩包共 49,427,160 字节（约 47.14 MiB），包含 1,449 个文件，展开约 234.27 MiB。

| 文件 | 用途 |
| --- | --- |
| `project_snapshot.tar.gz` | 主快照：2,028 条原始轨迹、prompt v2/v3、强验证 prompt 27/26 版本、环境与 verifier 映射、拒绝记录、奖励审计、诊断日志、服务器脚本快照，共 47 个文件 |
| `machine00_earlier_variants.tar.gz` | 0 号机早期 prompt v1、不同版本的 manifest / audit / 转换脚本及镜像诊断日志，共 8 个文件；与主快照完全相同的文件不重复存储 |
| `sandbox_and_provenance.tar.gz` | 19 个实际引用环境的 `logistics.sqlite`、`documents/`、任务定义，以及上游筛选计划、摘要和生成脚本，共 1,394 个文件 |
| `backup_manifest.json` | 每个归档成员的路径、大小、SHA-256 和恢复位置 |
| `source_inventory.json` | 三台源服务器的项目文件清单；保留原始哈希，说明去重及 PID 排除规则 |
| `dependencies_inventory.json` | 沙箱、上游计划的原始路径与哈希；26 条 verifier 的数据库哈希均已匹配 |
| `runtime_metadata.json` | 6 个实验容器的镜像引用、镜像 ID、运行配置摘要，以及 20 个依赖安装包的哈希；不含安装包本体 |
| `redactions.json` | 两份诊断日志的 API 认证字段脱敏记录，含原始及存储哈希，不保存认证值 |
| `verification_report.json` | 实际恢复、数据格式、数据库完整性与奖励审计的验证结果 |
| `SHA256SUMS` / `verify_backup.py` | 包级和逐成员完整性验证；支持恢复到新目录 |

未保存模型/LoRA 权重、优化器状态、checkpoint、容器镜像、第三方源码树、wheel、本机编译运行库、内核缓存、PID、SSH 连接说明、私钥、环境凭据，以及其他项目的训练和评测产物。沙箱只保留本实验依赖的主数据库、文档和任务定义，不复制后来产生的分析输出、数据库备份、`node_modules` 或虚拟环境。

## 验证与恢复

需要 Python 3.11 或以上版本，仅使用标准库。从仓库根目录执行：

```powershell
python experiment_backup/2026-11-25/verify_backup.py
python experiment_backup/2026-11-25/verify_backup.py --restore D:/restore/slime-qwen35-20261125
```

恢复目标必须不存在。先验证全部包级校验和、成员列表及逐文件哈希，再创建目标目录；不执行归档中的脚本，不提取软链接，不覆盖已有目录。

恢复布局：

```text
<目标>/project/                      # 服务器实验根目录的必要文件
<目标>/earlier/machine00/             # 0 号机早期差异；不覆盖主快照
<目标>/dependencies/sandboxes/sft/    # 19 个环境版本
<目标>/dependencies/upstream/        # 数据计划、来源摘要和生成脚本
```

原始 manifest 内的 `/workspace/...` 或服务器绝对路径保留用于追溯。使用恢复文件时，将实验根目录指向 `<目标>/project`，将 `--sandbox-root` 指向 `<目标>/dependencies/sandboxes`；按新环境重新指定路径，不能直接依赖旧服务器路径。

原始轨迹 SHA-256 为 `45bf5fef2ae19c3417370a4adebdec7251ba520cfa0102be1f3352e5d2660aa7`；v3 train/eval 分别为 1,817 / 202 条，与迭代 003 记录一致。两份诊断日志经过认证字段脱敏，其余归档成员保持源文件字节不变。校验和用于发现损坏，不替代可信仓库来源。

此备份支持检查历史数据、审计与实验配置，不包含可直接恢复训练的模型状态。将来重新运行仍需下载模型、重建 Ascend 软件环境，并遵循源码与镜像版本约束。未实际执行完整训练或 NPU 推理。
