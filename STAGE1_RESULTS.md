# Stage 1 验证记录

日期：2026-10-13。模型：qwen3:4b；Ollama 0.40.3；Python 3.13.15；Pydantic 2.14.1；Ollama Python SDK 0.6.3。

硬件：RTX 3050 Laptop GPU 4 GB VRAM；系统可见 RAM 约 13.9 GiB。未测量本次实际 GPU/CPU 分配比例。

## 已验证

5 项独立测试通过：家庭 seats 规则链；未知资料不猜测；座位矛盾追问；负数/错误类型/额外字段拒绝；排除品牌和 ambiguity behavior。

4 项本地模型测试通过预设字段对照：

| 案例 | 重点 | 秒数 |
|---|---|---:|
| 中文六人家庭 | budget/family_size/usage/fuel_priority 正确，seats 留给规则推导 | 18.13 |
| 资料不足 | 不编造 budget/seats/usage | 4.74 |
| 英文排除品牌 | Toyota 属于 excluded_brands，非 preferred_brands | 5.88 |
| 仅月供 | budget_myr 保持未知 | 5.54 |

逐项 input、expected、actual、trace 与 latency 保存在 evaluation-results.json。第一个 case 含首次请求开销，未将 loading 与 inference 时间单独分离。

## 证据限制

这是 4 个开发案例，不能据此宣称总体 100% accuracy。后续需要未参与 prompt 调整的独立 holdout、更多同义表达、冲突/金额/单位/多轮测试。Schema validation 不保证内容语义正确。

当前产物是 single-turn extraction demonstration，并未实现完整 Agent Loop、真实车辆推荐或估价。人工 fixture 和真实 LLM evaluation 分别记录。
