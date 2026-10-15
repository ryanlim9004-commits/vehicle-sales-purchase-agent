# 制作计划：Python + Ollama 车辆咨询 Agent

**2026-10-15 提速更新：以下早期日程已被 `../ACCELERATED_PLAN_ZH.md` 替代。目标10/23核心可录制版本，10/24起集中视频制作；不要再沿用10/30才开始视频的安排。**

更新：2026-10-13。Lecturer 已同意计划；组员 5 人；截止日期按 2026-11-02 安排。

状态更新（2026-10-15）：Stage 1/2 已完成且用户运行成功。下文环境与模型段落中“未找到/未安装”为初次规划时的历史状态；现在 Python venv、Ollama、qwen3:4b 已安装并通过本地验证。当前进度与软件清单以 `../ASSIGNMENT_ROADMAP_ZH.md` 为准。

## 1. 工具选择与学习顺序

| 工具 | 角色 | 初学者需要掌握 |
|---|---|---|
| Python + venv + pip | Agent Controller、规则与计算；隔离项目依赖 | variables、dict/list、functions、modules、exceptions、JSON、基本 tests |
| VS Code（建议） | 编写、运行、调试 | 开项目目录、选 Python interpreter、terminal、breakpoints |
| Ollama + Python SDK | 本地运行并调用 LLM | model 与服务区别；chat/messages；structured output；tool calls |
| Streamlit | 聊天界面、输入表单、候选比较、session state | chat_input/chat_message、forms、session state、tables |
| Pydantic | 验证用户 slots 和工具参数 | types、required/optional、范围、validation errors |
| CSV/JSON | 初期车辆数据、规则配置、测试 fixtures | 字段、单位、唯一 ID、source/date、unknown values |
| SQLite（需要时） | 本地记录与查询 | Python 内置 sqlite3；参数化查询。首版文件已足够时不强制迁移 |
| pytest（建议） | 有意义的规则、数值与行为测试 | input/expected、边界条件、错误场景；先独立于 LLM 测工具 |
| Git（建议） | 五人协作与变更记录 | commit、branch、review、合并；配合实际 work log，不以 commit 数代替贡献 |
| 录屏工具 + PowerPoint/Word | video、presentation、report | 画面/声音清楚、符合 rubric；按现有软件选择，无需购买 |

推荐先创建一个清晰的 Python 项目；不需要同时学习 web frontend/backend、multi-agent framework 或 vector database。

Ollama 当前未在 PATH 检测中找到；先检查已有安装再决定是否安装。Python 命令返回 3.13.15，后续先检查实际 dependency compatibility，不因已有版本而自动升级。

## 2. 模型试验

已确认 RTX 3050 Laptop GPU，4096 MiB VRAM；系统可见 RAM 约 13.9 GiB。

首选候选 qwen3:4b（官方模型页约 2.5 GB，Q4_K_M），较小备用 qwen3:1.7b（约 1.4 GB）。模型文件大小不等于全部 runtime VRAM；context/KV cache、程序与桌面显存也影响运行。4b 是否合适必须实测，不承诺全部 GPU 加载或固定速度。

先用短上下文、低随机性、非 thinking 模式试验业务任务（版本支持时）；分别检查简单中英文 slot extraction、否定偏好、tool selection、malformed response、response latency。保存 model tag/digest、Ollama/package versions 与 configuration。4b 慢时先缩减无关上下文，随后比较 1.7b 的质量；不要仅按速度选择。

下载模型、安装依赖与构建应用是下一制作阶段；本次文件是设计产物。

## 3. 模块设计

| 模块 | 职责 |
|---|---|
| UI | 聊天、买卖选择、补充资料、结果比较、清楚的限制提示 |
| Schemas/Frames | 车辆/买家/卖家 slots、type/range/unknown、selected inheritance |
| Knowledge Base | 车辆 facts、domain rules、source/date/version |
| Inference Engine | pattern matching、derived facts、rule firing、优先级、trace |
| Matching Tool | 硬约束筛选、normalize、weighted scores、Top 3、ties |
| Valuation Tool | comparable selection、base、独立调整、范围依据、insufficient evidence |
| Negotiation Tool | 买卖角色的 decision tree、底价/预算、Trade-In/private-sale 净额 |
| Ollama Client | messages、schema/tool descriptions、timeouts、response parsing |
| Agent Controller | goal/state、clarification、tool allowlist、observe/check、retry/stop |
| Evaluation | 固定案例、预期结果、实际结果、失败分析、latency |

每个工具返回结构化结果：status、data、source_ids、rule_ids、assumptions、warnings。业务金额由 Python 算，LLM 只能解释已有结果。

## 4. 三条核心任务及规则

### 买车

必填/关键 slots：budget_myr、required_seats、usage；可选 brand preference、fuel_priority、space_priority、transmission、最大 mileage。

示例规则 R_BUY_01：family_size ≥ 6 → required_seats ≥ 6。
示例规则 R_BUY_02：city_commute AND high_fuel_priority → economical_city_profile。
先应用预算/seats 等 hard constraints，再评分 soft preferences。用户未说明 soft weights 时，可用公开的 baseline weights 并说明其为设计假设；用户有明确偏好时调整，sum(weights)=1。

结果：Top 3、匹配原因、主要 trade-offs、来源及未满足偏好。无结果时请求用户选择调整软偏好；不能擅自提高预算。

### 卖车

关键 slots：brand/model/variant/year、mileage_km、condition；condition 不确定时记录 unknown 并追问。

可比数据先决定 base，规则决定 mileage/condition adjustment。避免 comparables 已经反映年份后再次扣同一 depreciation。所有调整比例先标 calibration-needed，不能凭空当成行业标准。

结果：估计参考价格/范围、comparables、adjustments、依据与限制。历史趋势需 dated records，缺少数据则不宣称实现。

### 议价/Trade-In

关键 slots：buyer/seller role、asking/offer price、valuation evidence、budget 或 reserve price、replacement price、trade-in offer、fees。

建议 branch：缺少估价依据 → 补资料；买方报价超预算 → 重新评估；卖方 offer 低于底价 → 根据用户目标提供 counter-offer；可接受范围 → 解释取舍而非保证成交。

Trade-In 的补差额 = replacement_price − trade_in_offer + known_fees。Private-sale 情况另算净收入与补差额；未知 fees 明示，时间/便利性作为非价格取舍。

## 5. Agent loop 的工程边界

状态包括 goal、profile、missing_slots、last_tool_result、steps、completed。五次工具调用上限为初始设计值；timeout/retry 数也需可配置。

Controller 检查 tools allowlist、参数类型/范围、预算、seat、record IDs、数值来源、重复请求和停止条件。失败时说明原因并采取有限恢复。Rules/vehicle descriptions 都是 data，不允许它们替换 agent instructions。多轮更新 profile 时保留明确约束，纠正旧值，重置时清空任务。

展示的 decision trace 是 facts/rules/tools/checks，不是隐藏 chain-of-thought。

## 6. 2026-10-13 至 2026-11-02 工作安排

| 日期 | 阶段 | 验收产物 |
|---|---|---|
| 10/13–10/15 | 定稿与环境准备 | proposal、schemas、rule outline、硬件模型试验、分工 |
| 10/16–10/19 | 数据与三个工具 | curated data、source log、rule traces、手算对照测试 |
| 10/20–10/23 | Ollama 与 Agent loop | extraction、tool calls、memory、clarification、observe/check |
| 10/24–10/26 | Streamlit 与集成评估 | 三任务贯通、异常恢复、30 cases、actual metrics |
| 10/27–10/29 | 修复与报告 | bug fixes、五章 report draft、references、个人记录 |
| 10/30–11/01 | 冻结功能与交付准备 | final checks、video、presentation/Q&A rehearsal、forms、Turnitin |
| 11/02 | 提交 | 按实际指定时间提交；提前保留可演示版本 |

优先规则：核心出现问题就不加入图片模块。论文相关资料与贡献记录从第一天同步积累；后期不补编不存在的挑战。正式 submission 时间尚未知，不安排最后一刻才交。

## 7. 五人分工建议

| 成员 | 主要 ownership | 配套证据 |
|---|---|---|
| A（可由 Ryan 担任） | integration/Agent Controller、架构与演示统筹 | architecture、goal/state/tool loop、integration results |
| B | 数据、Frames、lifestyle matching | source log、dictionary、rules/scoring、matching evaluation |
| C | valuation expert system | comparables、调整依据、rule trace、numeric tests |
| D | negotiation/Trade-In、decision tree | flowchart、calculator、branches、scenario tests |
| E | Streamlit、test coordination、video production | UI、test log、UX feedback、recording |

这是建议 ownership，不是已发生的贡献；名单待填。每人都参与 report 的自己负责部分、共同测试和 Q&A。工作量不必强行等于 20%，按实际投入填官方 matrix。

## 8. 第一阶段学习任务

1. 用自己的话区分 LLM、Ollama、Agent Controller、Tool、Knowledge Base。
2. 为一个 six-person buyer 手工填写 BuyerProfileFrame，推导 seats requirement。
3. 为三辆示例车手算 filtering 与 ranking，记录为什么选/不选。
4. 为一辆待售车手算示范估价，明确哪些因子只是教学假设。
5. 画一条 negotiation decision tree，然后再把它变成 Python。

后续教学每次交付：这一阶段的目标 → 原理 → 最小代码/配置 → 如何运行 → 预期结果 → 检查与解释。先完成一个可理解的小步骤，再扩展。

## 官方技术资料

- https://docs.ollama.com/capabilities/tool-calling
- https://docs.ollama.com/capabilities/structured-outputs
- https://ollama.com/library/qwen3:4b
- https://ollama.com/library/qwen3:1.7b
- https://docs.streamlit.io/develop/api-reference/chat
- https://docs.python.org/3/library/sqlite3.html
- https://docs.pydantic.dev/latest/
