# 迭代 002：建立本地 slime 参考源码研究区

- 日期：2026-07-16
- 状态：完成
- 关联提交：本次迭代提交

## 迭代目标

在项目根目录建立不上传 GitHub 的 `reference/` 研究区，下载官方 THUDM/slime 源码，并固定一份可复现的 Qwen3.5-9B 研究基线。

## 变更内容

1. 在 `.gitignore` 中加入根目录级规则 `/reference/`，确保参考源码和本地研究笔记整体不进入父仓库。
2. 将 `https://github.com/THUDM/slime.git` 的 `main` 分支浅克隆到 `reference/slime/`。
3. 固定研究基线 commit：`fb42ae456fac8166afb604f13b30d22bb3c75053`。
4. 新建本地 `reference/README.md`，记录来源、版本、关键入口和运行安全提醒；该文件同样被忽略。
5. 初步定位与本项目最相关的官方实现：
   - `examples/fully_async/run-qwen3.5-9B-fully_async.sh`
   - `scripts/models/qwen3.5-9B.sh`
   - `slime_plugins/models/qwen3_5.py`
   - `slime_plugins/mbridge/qwen3_5.py`
   - `examples/fully_async/README.md`

## 初步研究结论

- 上游 README 明确列出对 Qwen3.5 的支持。
- 官方 Qwen3.5-9B fully-async 示例采用单机 8 GPU，将 actor 与 rollout 分配到不同 GPU，默认 actor 4 卡、rollout 4 卡。
- 示例使用 GRPO、dapo-math-17k、3 次 rollout、每个 prompt 采样 4 条、全局 batch size 32。
- 示例通过 `train_async.py` 和 `slime.rollout.fully_async_rollout.generate_rollout_fully_async` 启用 fully-async 路径。
- 官方启动脚本会强制终止 `sglang`、Ray 和所有匹配的 Python 进程，不能在共享机器上未经修改直接执行。

## 验证结果

- 克隆分支：`main`。
- HEAD：`fb42ae456fac8166afb604f13b30d22bb3c75053`。
- HEAD 提交时间：2026-07-15 11:34:23 +08:00。
- 上游地址：`https://github.com/THUDM/slime.git`。
- Git 跟踪文件数：594。
- 本地占用约 15.62 MiB。
- 上游没有 `.gitmodules`，不存在待初始化子模块。
- 父仓库状态将整个目录显示为 `!! reference/`，确认不会纳入提交。

## 风险与兼容性

- 当前使用 `--depth 1` 浅克隆，不包含完整历史；需要追溯演进时必须额外 fetch。
- `main` 会持续变化，研究与实验必须引用精确 commit，不能只写分支名。
- 官方 Qwen3.5-9B 示例假定 Linux、CUDA、8 GPU、Ray、SGLang、Megatron-LM、模型权重和数据集均已就绪。
- 官方脚本的全局进程清理命令存在误杀其他任务的风险，运行前必须安全改造。

## 回滚方式

删除本地 `reference/` 目录即可移除参考源码；如还需撤销仓库规则，则回退本次提交中对 `.gitignore`、README 和本文件的变更。不得影响 `.ssh` 中的服务器密钥。

## 后续事项

1. 结合 0 号机和 5 号机的 GPU、CUDA、驱动、存储及容器环境，判断更适合在哪台机器部署。
2. 梳理 Qwen3.5-9B 示例的依赖、数据流、进程拓扑和显存预算。
3. 复制官方启动脚本到项目代码区并移除危险的全局 `pkill` 行为，再开展最小 smoke test。
