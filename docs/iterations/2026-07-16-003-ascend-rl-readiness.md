# 迭代 003：Ascend 轨迹强化学习就绪验证

- 日期：2026-07-16
- 状态：完成
- 关联提交：本次迭代提交

## 迭代目标

围绕 Qwen3.5-9B 的轨迹强化学习，在不执行 SFT 的前提下完成一轮可复现的工程就绪验证：审计并转换现有轨迹数据、恢复每条任务对应的沙箱环境、建立安全的 Ascend 容器与算子检查工具，并尽可能跑通 slime 所需的 SGLang rollout 模型前向。

本迭代的边界是“数据与 rollout 最小链路”。完整 GRPO/DAPO 训练还需要当前 slime actor 的 NPU 适配和在线任务 verifier，不在本次已完成范围内。

## 变更内容

### 数据审计与转换

1. 新增 `scripts/audit_trajectory_jsonl.py`，审计 JSONL 完整性、角色分布、消息长度、工具定义和重复记录。
2. 新增 `scripts/summarize_tool_schemas.py`，汇总轨迹内的 bash、read、write、edit 工具 schema。
3. 新增 `scripts/build_environment_manifest.py`，根据上游 dataset plan 重建样本与沙箱 environment、版本、任务类型和质量层级的映射。
4. 新增 `scripts/prepare_rl_prompts.py`，将完整专家轨迹转换为只包含初始 prompt、tools 和环境元数据的 slime 输入，防止参考答案泄漏到 rollout。
5. 转换逻辑按 `prompt + tools + environment_id` 分组和去重，避免不同沙箱环境中相同文本被错误合并；训练集与评估集按稳定哈希切分，样本组不交叉。
6. 新增 `tests/test_prepare_rl_prompts.py`，覆盖环境感知去重与稳定切分。

### 运行与诊断工具

1. 新增 `scripts/start_npu_container.sh`：
   - 固定官方 ms-swift CANN 9 镜像 digest；
   - 非特权运行；
   - 显式映射 16 张 NPU 及必要驱动目录；
   - 模型目录只读挂载；
   - 使用 Docker `--init` 回收多进程 worker，避免 PID 1 不回收 zombie。
2. 新增 `scripts/smoke_npu_devices.py`，逐卡执行真实矩阵乘法，而不是只检查设备数量。
3. 新增 `scripts/smoke_slime_dataset.py`，以真实 slime Dataset 与 Qwen chat template 加载转换后样本。
4. 新增 `scripts/smoke_sglang_http.py`，使用 Python 标准库检查 OpenAI 兼容端点，便于识别代理或网络层问题。
5. 新增 `scripts/smoke_sglang_engine.py`，绕过 HTTP，以官方离线 `sglang.Engine` API 执行一次真实生成并主动关闭 worker。

### 服务器侧研究与运行产物

1. 在 `/data3/llin/slime_qwen3.5_9b_rl` 建立独立工作区；原始数据、处理后数据、日志、模型和参考源码不进入本 Git 仓库。
2. 固定 slime 源码 `fb42ae456fac8166afb604f13b30d22bb3c75053`，以及其锁定的 SGLang 源码 `5a15cde858ea09b77116212a39356f2fc51b8584`。
3. 使用官方 ms-swift CANN 9 镜像 `quay.io/ascend/ms-swift@sha256:0116ad4e0b2b440b3ff7353f24fca741a3173b1e9fcea595c99d358347f47952` 作为可工作的 Torch 2.9 基线。
4. 官方 SGLang CANN 8.5 镜像中的 Torch/torch-npu 二进制不匹配当前服务器；Torch 2.8 和 2.10 组合也无法识别当前 `26.0.rc1` 驱动。未修改宿主驱动，也未使用特权容器。
5. 从官方 `sgl-kernel-npu` 发布提交 `7a396def6d0d7ce85e940549a366351ce1d7821b` 源码，在目标 CANN 9/Torch 2.9 环境中编译并安装本机 ABI 匹配的 `sgl_kernel_npu` 与 `attentions` wheel。
6. 按 slime 自带 ARM64/GB10 兼容说明安装 PyPI `sglang-router==0.3.2` 的 ARM64 wheel；SHA-256 `40a10f3817b80377c2ceb326b625f24bd06eb97426e5044de722295ec7fa79c0` 与 PyPI 元数据一致。训练入口由缺少 router 推进到下一个可选依赖 `wandb`。

## 验证结果

### 数据证据

- 原始轨迹：2,028 条，全部为合法 JSON；无格式错误、无无效记录。
- 原始文件 SHA-256：`45bf5fef2ae19c3417370a4adebdec7251ba520cfa0102be1f3352e5d2660aa7`。
- 工具定义：2,028/2,028 均可解析，工具集合固定为 bash、read、write、edit。
- 环境映射：2,028/2,028 成功映射到 19 个沙箱环境；所需 `logistics.sqlite` 与 `documents` 均存在。
- 转换结果：2,019 个唯一样本组；同环境重复 9 条；跨环境碰撞 0；拒绝 0。
- train：1,817 条，SHA-256 `f37af00f3569932564178a5d9a6e6e66a6f37b4dca0c2710cf71cb5653770ee2`。
- eval：202 条，SHA-256 `663cc5c7d8c9c8d5a6419a2aec9d9d4f1d3d540cdea2c7dd1ae0ae1df4d64f5b`。
- slime Dataset + Qwen chat template：4 条真实样本加载成功，tools 保留，渲染后 token 数 768–773。

### NPU 与模型证据

- 设备：16 张 `Ascend910_9362`，健康状态正常。
- Torch `2.9.0+cpu`、torch-npu `2.9.0.post2` 基线下，16/16 张卡分别完成 256×256 矩阵乘法，观测值全部与期望值一致。
- 本机编译的 `sgl_kernel_npu` 和 `attentions` 可导入，且导入后仍能识别 16 张 NPU。
- Qwen3.5-9B 以 TP=2 加载成功，每个 rank 权重约占 9.08 GiB；混合 Mamba/GDN 与 KV cache 均完成分配。
- 离线 `sglang.Engine` 真实生成成功：prompt 10 tokens，completion 8 tokens，输出“1+1等于2。”，端到端延迟约 88.45 秒。
- 生成结束后 `npu-smi` 显示 16 张卡均无运行中 NPU 进程，显存已释放。
- 当前容器未用 `--init` 创建，因此 `Engine.shutdown()` 虽已 SIGKILL worker 并释放 NPU，仍因 PID 1 未回收 38 个 zombie 而返回非零；启动脚本已加入 `--init` 供下次重建验证。

### 本地检查

- `python -m pytest tests -q`：2 passed。
- 新增 Python 脚本 `py_compile`：通过。
- `bash -n scripts/start_npu_container.sh`：通过。

## 风险与兼容性

1. 当前 slime `main` 已有 Qwen3.5 代码，但官方 NPU 指南仍固定在 slime v0.2.2、CANN 8.5、Torch 2.8；该旧补丁无法直接应用到当前 Qwen3.5 主线。rollout 前向已跑通，不代表 Megatron actor 训练已经兼容。
2. 当前 slime 仍以 Megatron actor 为主，尚未验证 Qwen3.5-9B 在本机 CANN 9/Torch 2.9 下的反向、优化器、权重同步和长时间稳定性。
3. 现有轨迹任务需要执行 bash/read/write/edit，并基于数据库与文档判分；在线 sandbox runner 和 verifier 尚未实现。没有可信 verifier 时不应启动正式 GRPO/DAPO。
4. 服务器 loopback HTTP 被 SSHPiper 网络层接管，SGLang 内置 HTTP warmup 无法回连；本迭代使用离线 Engine API 验证模型前向。正式 slime rollout 仍需解决网络命名空间或路由配置。
5. 首次 8-token 生成约 88 秒，主要包含首次混合线性注意力初始化；尚未开展吞吐、并发、长上下文和稳定性基准。
6. 服务器侧数据、环境、wheel、日志和 checkpoint 均未纳入 Git；复现依赖迭代说明中的源码 commit、镜像 digest 和数据哈希。
7. slime 训练入口的 Python 依赖尚未完全收敛；安装 ARM64 router 后当前下一项为 `wandb`。应通过可复现镜像或锁文件整体解决，避免在长期容器中逐个临时安装。

## 回滚方式

1. 停止并删除仅属于本实验、名称以 `slime-qwen35-` 开头的测试容器；不得使用全局 `pkill`、`ray stop --force` 或影响其他用户容器的命令。
2. 删除 `/data3/llin/slime_qwen3.5_9b_rl` 可移除服务器侧本次数据副本、源码、编译 wheel 和日志，不影响原始轨迹目录及模型目录。
3. 回退本次 Git 提交可移除新增脚本、测试、README 摘要和本迭代说明。
4. 本迭代未修改宿主驱动、CANN、系统服务和其他用户任务，无需系统级回滚。

## 后续事项

1. 以 GRPO 作为第一阶段算法：先做 8–32 条 prompt 的在线 smoke，再逐步扩大；在 verifier 稳定前不引入 DAPO 的动态采样和过滤复杂度。
2. 从上游 `sql_result_verified` 的 27 条强验证样本开始，实现隔离 sandbox runner 与确定性 verifier；奖励至少包含任务正确性、工具执行有效性和格式约束，避免直接模仿旧轨迹文本。
3. 为当前 slime/Qwen3.5 主线移植并维护独立的 CANN 9 actor 补丁，依次验证单步 forward、backward、optimizer step、权重同步和断点恢复。
4. 重建带 Docker `--init` 的基线容器，复测 Engine shutdown，并解决 slime rollout 的 loopback/网络命名空间问题。
5. 完成 2 卡 rollout + 小规模 actor 的端到端单步后，再设计 16 卡资源拓扑和 GRPO 批量参数；之后才评估 DAPO 或 fully-async。
