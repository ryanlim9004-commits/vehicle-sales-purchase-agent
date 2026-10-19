# Assignment 全流程与当前进度

**2.0最新状态（2026-10-17）：当前优先阅读V2_GUIDE_ZH.md和V2_RESULTS.md。本批完成Formal Fuzzy Logic、安全与评论参考的来源／年款校验、英文聊天／表单／UI整合；184项离线测试与最终2轮真实Ollama验收通过。研究目录6车型7档案，挂牌库存仍17笔；真实可靠性数值与回归市场模型均未完成。Regression保留目标，但数据足够后才训练。历史趋势／品牌折旧曲线、车况／损伤校准、实际成交率提升证明与全部Vision已由用户取消。以下按日期保留早期阶段记录，不能用旧表覆盖本条最新范围。**

**阶段9最新进度（2026-10-16）：英文Streamlit UI基础版已完成，见STAGE9_GUIDE_ZH.md与STAGE9_RESULTS.md。152项离线回归通过，包含忙碌提交保留与明确重试／丢弃；真实浏览器完成买车聊天→表单→比较、Trade-In→来源／现金结果、手动导出。用户确认第一版固定15 Oct 2026快照，暂不加当天日期切换、实时搜索或市场校准；这些是不同的后续功能。当前下一步是扩大独立评估／组员复现与报告／视频，见REMAINING_WORK_ZH.md。以下旧阶段验收数量按其日期阅读。**

**最新进度（2026-10-15）：阶段1–7已复核并修复当前教学范围的缺口，阶段8完整受约束Agent Loop已接入英文多轮输入、记忆／修改、动态业务工具请求、实际执行／结果检查与停止限制。运行agent_cli.py，见STAGE8_GUIDE_ZH.md。134项单元测试、16个既有工具场景复核、最终8轮真实模型验收（含reset）通过；不是holdout准确率。下一步阶段9英文UI，以及更广系统评估、报告和视频。**

**阶段5/6历史验收记录（2026-10-15）：真实数据/Scoring与Valuation基础版复核通过，见STAGE5_STAGE6_REVIEW_ZH.md；当时67项回归与10个场景通过，现已继续完成阶段7/8。GitHub Private仓库已建立，阶段5–8的交付版本以Git提交记录为准。目标10/23核心可录制、10/24开始集中录制，以ACCELERATED_PLAN_ZH.md为准。**

状态日期：2026-10-15。用户已自行运行 Stage 2 并确认没有问题。5 人组，截止日期按 2026-11-02，具体提交时间待课程通知。Lecturer 已同意 Agent 计划。系统及代码使用英文，中文用于辅导。

## 项目目标与架构

目标：买家用自然语言说明生活方式和预算，系统筛选并解释适合的候选车辆；卖家提供车辆资料，系统计算有依据的参考价值；双方可查询议价和 Trade-In 取舍。只做 consultation，不代用户成交。

当前流程：英文Streamlit UI／CLI → Agent Controller ↔ Ollama LLM；聊天由模型提出fact patch，明确表单字段由typed adapter提出patch；两者共用grounding／记忆规则，模型通过Schema-constrained JSON请求tools，Python实际执行matching／valuation／negotiation／trade-in及独立checks。UI仅显示经检查的当前结果，不自行估价。

Ollama 是模型运行服务；qwen3:4b 是预训练模型；Python 程序负责业务工具和执行；Frames 是结构化知识表示；Agent Controller 负责目标、状态、工具选择、反馈和停止。Conversation memory 不会自动训练或更新模型。

## 已完成的内容

| 部分 | 状态／证据 |
|---|---|
| 课程与 requirements | 已读取整理，见 vehicle-agent-context/PROJECT_CONTEXT.md |
| Proposal/方案 | 已写，见 PROPOSAL_EN.md、BUILD_PLAN_ZH.md |
| 基础环境 | Python 3.13.15、项目 venv、Ollama 0.40.3、qwen3:4b、Pydantic、Ollama SDK |
| 买家 NLU/Frame | 英文 intent/slot 提取、schema validation、unknown slots |
| Rule reasoning | BUY_01–04与trace、缺少资料／矛盾追问；可澄清并非全家同行 |
| 车辆 Frame | 共同 slots、PassengerCarFrame 继承、defaults/ranges/provenance |
| 硬约束 filtering | budget/seats/excluded brand；各条拒绝原因、unknown 不直接合格、无匹配不放宽约束 |
| 真实来源数据与评分 | 17条挂牌快照、来源receipt与质量报告、Weighted Scoring、missing coverage与公式解释 |
| 估价工具 | SellerVehicleFrame、同条件近期comparables、reference_only、明确标注的教学调整 |
| 议价/Trade-In | 手写Decision Tree、预算/净底价、完整费用、贷款结清、独立replacement package、时间/投入；人工JSON与Agent英文输入；可关联旧车asking context |
| Agent Loop | typed memory、追问回答／修改、任务切换、工具参数与结果检查、timeout／有限重试／停止、facts/rules/tools/checks |
| 英文UI | 聊天／四类入口／辅助表单／候选比较／reference与现金明细／来源与trace；每tab临时记忆和手动导出 |
| 测试 | 当前184项unit tests；最终2轮真实Ollama V2验收；历史阶段8／9证据独立保留 |

当前保留8条虚构车辆records和17条真实来源快照。asking price不能保证库存或成交价；仅一个exact identity组满足当前估价minimum3政策。估价默认未校准里程／车况；UI明确显示未调整。main.py保留单次命令，agent_cli.py为多轮CLI，streamlit_app.py为浏览器入口。下文1–8是工作模块目录，不是用户阶段编号；前六项已完成当前基础范围，扩大评估与最终材料仍待制作。

## 后续阶段及验收

### 1. 数据设计与收集

先定义用于匹配与估价的 data dictionary，包括车型/variant/year、price、seats、mileage、condition，以及能核实的 fuel/space features。记录 source、date、单位、缺失和 asking/transaction price 标签。避免重复 listings。同样的车型不同 variant 不能随便混合。

已有 fixtures 留作 regression tests，真实来源资料分开保存。无证据的 fuel/condition 不补成事实。初始目标 30–50 条是建议，够不够做某车型估价取决于可比样本覆盖，不能仅看总数。任何模块在缺少资料时应明确无法充分判断。

验收：字段及单位一致、来源可查、重复与未知值可解释。

### 2. Lifestyle Matching / Weighted Scoring

先做已实现的硬筛选，再将 soft preferences 转为公开权重，对通过者评分。定义 feature normalization、unknown handling、ties、权重和为 1。省油偏好影响 fuel weight；家庭出游可影响 space weight，但只能使用有数据支持的指标。

验收：偏好变化可以影响排序，但不可突破硬约束。v1仍是transparent heuristic；v2已加入formal zero-order Sugeno Fuzzy Logic及公开的外层权重，详见V2_GUIDE_ZH.md。两者都尚未经过独立推荐相关性评估。

### 3. Rule-Based Valuation

新增 SellerVehicleFrame（exact variant/year/mileage/condition）。选 comparable records，计算 base，依据有来源/明确校准状态的规则调整，输出 reference estimate/range、comparables、adjustments、限制。不能让 LLM 自己猜价，也不把 listing asking price 当实际成交价。不重复扣除 base 已含的年份贬值。

验收：手算一致；不同 mileage/condition 影响符合规则；资料不足返回 insufficient evidence。只有 dated historical data 才声称处理历史趋势。规则价格区间不是自动成立的统计 confidence interval。

### 4. Negotiation / Trade-In

手写 Decision Tree：buyer/seller role、asking/offer price、valuation range、budget/reserve、用户目标决定建议。Calculator 明列 replacement price、trade-in offer、fees、private-sale net 与补差额。未知 fees 保持未知。

验收：各分支、边界和公式可手算；不越过预算/底价；清楚解释价格、时间和便利性取舍；不保证成交。

### 5. Agent Controller / Tool Calling

阶段8已连接模型与业务tools，记录goal、profile、missing slots、tool results、steps与complete状态。执行Sense → Plan → Act → Observe/Check → Continue/Finish。当前采用Schema-constrained JSON tool requests；Python校验并实际执行，再回传真实observation。本机native tool_calls尝试未通过，失败证据保留，不将它称为已验证的原生协议支持。

验收：可以回答追问、修改预算、保留其他条件、切换/重置任务；无结果时澄清而不编造；检查数字和 ID；timeout/limited retries/step limit 能停止；显示 facts/rules/tools/checks trace。

### 6. Streamlit UI

阶段9基础版已完成英文聊天、Buy／Sell／Negotiation／Trade-In入口、补充资料表单、Top3对比、reference与未调整说明、现金明细、来源和解释。浏览器访问本地服务；Ollama仍在本机运行。表单只跳过重复语言提取，保留同一Controller的grounding／记忆／实际模型planning／tools／checks。

已验证普通用户能在浏览器连续操作，PowerShell主要用于启动；显示与实际tool结果一致。每tab独立记忆，手动导出，无自动存档／恢复。后续仍需组员跨电脑复现与独立holdout；界面本身不等于市场正确性。

### 7. Evaluation 与修复

初始计划 30 个场景：buying 10、valuation 8、negotiation 6、exceptions 6。开发案例和未参与 prompt 调整的 holdout 分开。记录 input、expected、actual、pass/fail、latency、failure cause/fix。

NLU测slots；matching测hard constraints和relevance；valuation测规则正确与有真实labels时的市场误差；negotiation测分支/数字；Agent测tool selection/task success/恢复/停止。当前134项unit tests与开发验收不等于独立holdout evaluation，也不等于总体准确率。具体结果与限制见STAGE8_RESULTS.md。

### 8. Report、Video、Presentation、个人证据

报告五章：Introduction（目标需求范围）、Literature Review（existing solutions/理论/gaps）、Methodology（KR/算法/架构/数据/流程/评估）、Implementation（至少两项真实挑战及解决结果）、Conclusion（实际成果/impact/limits/future/reflection）。从现在同步写，不等系统全部完成。

交付还包括 operational system、video、final demonstration、每人 presentation/Q&A、Individual Contribution justification、Workload Matrix。APA/格式/Turnitin 等按已保存 official guide 执行，不自行新增 word limit 或视频时长。rubric 总权重为 system30/report30/video10/presentation10/Q&A10/contribution10，report 章节标注歧义保留于项目背景。

2.0已加入小型formal Fuzzy Logic；Regression训练流程已准备，但合适价格资料未取得，尚未训练／启用。Vision已取消。现有环境无需新增软件；未来若更换实现，先更新依赖与复现记录。

## 软件检查（2026-10-15）

- 确认：Python、VS Code（C:/Program Files/Microsoft VS Code）、Ollama 程序；项目依赖 Pydantic 2.14.1、Ollama SDK 0.6.3；项目 Python 可 import sqlite3（3.50.4）。qwen3:4b 先前已下载并实际通过测试。
- 2026-10-16已将Streamlit 1.66.0安装到现有.venv，pip check通过，requirements-lock已更新；不需换Python或购买服务。
- pytest 尚未安装，但现有测试用 Python unittest 已足够，只有需要时才添加。
- Git命令来自Codex bundled runtime。vehicle-agent已初始化Git并建立Private仓库：https://github.com/ryanlim9004-commits/vehicle-sales-purchase-agent 。阶段5–8交付版本以Git提交记录为准；GitHub不是运行应用的必要条件。
- 报告/幻灯片/录屏使用组员已有工具，尚未核实安装情况，不强制某品牌软件。
- 无需为当前路线另装大型数据库服务；SQLite 模块已可用。无需为了当前方案购买 API、租云 GPU、训练 LLM 或额外部署 React/Node/Docker。

技术来源：
- Streamlit installation: https://docs.streamlit.io/get-started/installation
- Python SQLite: https://docs.python.org/3/library/sqlite3.html
- pytest: https://docs.pytest.org/en/stable/getting-started.html

## 工作目标安排

当前交付目标统一见ACCELERATED_PLAN_ZH.md。截至10/15，议价/Trade-In及Agent Loop已完成当前基础范围，原先为这些模块预留的时间可用于英文UI与扩大评估。保留10/21–10/23测试与核心冻结、10/24–10/28集中视频，随后材料review与提交检查，11/02按课程指定时间提交。目标核心冻结时间不因提前完成部分功能而推迟。

这是协作目标，不是已经完成的进度或保证。若数据或核心功能延误，首先取消 optional extensions，保留报告和验证时间。五人各自负责明确模块，同时交叉测试并了解完整流程。
