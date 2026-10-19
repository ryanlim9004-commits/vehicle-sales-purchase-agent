# 第 1 课：把买车需求转换为 BuyerProfileFrame

**组员首次安装／启动／测试（2026-10-19）：请先看[GitHub到实际测试手把手指南](TEAM_GUIDE_ZH.md)，启动入口是`streamlit_app.py`，用指南中的Streamlit命令运行。另有[测试记录表](TEAM_TEST_RECORD_TEMPLATE_ZH.md)、[独立案例说明](evaluation/INDEPENDENT_CASES_GUIDE_ZH.md)和[交接验收现况](TEAM_HANDOFF_RESULTS.md)。**

**2.0更新（2026-10-17）：先阅读[V2制作与运行指南](V2_GUIDE_ZH.md)和[验收现况](V2_RESULTS.md)。当前184项离线测试通过；最终2轮真实Ollama输入与一次最终浏览器表单验收通过。默认买车排名已接入Formal Fuzzy Logic和适用的安全／评论资料，价格库存仍17笔；回归尚未训练，真实可靠性资料尚不足。本机无需安装新软件。下文是保留的历史课次。**

最新（2026-10-16）：阶段9英文Streamlit界面完成基础版，运行`.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py`，浏览器打开http://127.0.0.1:8501。见[阶段9运行教学](STAGE9_GUIDE_ZH.md)、[验证记录](STAGE9_RESULTS.md)。152项离线回归通过，真实浏览器买车多轮／Trade-In及导出已验证；模型忙碌时保留提交供Retry／Discard。第一版固定15 Oct 2026快照，无当天日期切换／实时搜索；里程／车况校准暂缓。后续见[剩余交付清单](REMAINING_WORK_ZH.md)。下文保留历史课次，不代表当前缺少UI。

2026-10-16学习入口：34个Python文件、275个类／函数已补英文解释，并在关键规则、公式及Agent步骤加入注释。阅读[全项目代码指南](CODE_GUIDE_ZH.md)、[PowerShell命令解释](COMMANDS_ZH.md)、[JSON资料解释](docs/JSON_FILES_GUIDE_ZH.md)。本轮只补comments和说明，AST／配置／既有JSON未改变，134项回归再次通过。

最新（2026-10-15）：阶段1–7复核与修复、阶段8多轮Agent Loop基础版已完成。运行`agent_cli.py --as-of 2026-10-15`，支持英文追问回答、修改条件、任务切换、实际工具执行与结果检查。见[阶段8运行教学](STAGE8_GUIDE_ZH.md)、[阶段1–7核对](STAGES1_7_AUDIT_ZH.md)及[验证记录](STAGE8_RESULTS.md)。134项单元测试、16个既有工具场景复核、最终8轮真实模型验收（含一次reset）通过；不是总体准确率或市场验证。下一步英文UI与更广评估、报告和视频。

阶段7历史记录：Negotiation/Trade-In独立tools及`main.py --negotiate`／`--trade-in`入口已完成，详见 `STAGE7_GUIDE_ZH.md`。当时94项回归、8个阶段7场景通过；本课以下内容是第一课的历史教学范围，完整多轮入口以最新阶段8说明为准。

阶段5/6历史验收：真实数据/Scoring及Valuation基础版已核对与修复；当时67项回归、10个场景通过。见 `STAGE5_STAGE6_REVIEW_ZH.md`。本文件及LESSON2–4为历史教学课次，不能按编号判断当前进度。

2026-10-15 输入错误修复：新增 Python 原文核对层，修正 m／miles／km、预算币种及相关边界。复测命令、结果与报告证据见 `INPUT_VALIDATION_FIX_ZH.md`。旧阶段记录保留为当时的进度。

Stage 4 估价tool已完成基础版：见 `LESSON4_ZH.md`，运行 `--value`。默认返回可核查挂牌reference；`--illustrative-adjustments`仅为明确标注的教学假设模式。

Stage 3 已加入真实来源快照与 Lifestyle Scoring：见 `LESSON3_ZH.md`，运行参数 `--rank`。新的提前交付目标见 `ACCELERATED_PLAN_ZH.md`，旧日期安排以新文件为准。

Stage 2 已完成：VehicleFrame + 预算/座位/排除品牌筛选。运行与原理见 `LESSON2_ZH.md`；新功能使用 `--match`，不加该参数仍是本课的输出。

2026-10-14 更新：应用输入、输出、Prompt、追问及错误信息统一使用英文；这份教学说明保留中文。旧中文示例用于解释概念，运行时请使用下方英文命令。

本课当时实现 **NLU/Slot Extraction + Frame + 小型 Forward Chaining**。以下按第一课的范围讲解；当前完整功能及运行入口见页首最新记录。

环境已在本机完成：项目 venv、Python 依赖、Ollama 和 qwen3:4b。5 项规则测试及 4 项 live model cases 已通过，见 STAGE1_RESULTS.md 与 evaluation-results.json。

## 理解数据如何流动

用户说：“预算 RM60,000，家里六个人，平时城市通勤，想省油。”

1. Ollama 提取用户明确表达的资料：budget_myr=60000、family_size=6、usage=[city_commute]、fuel_priority=high。
2. Pydantic 检查 JSON 是否符合 Frame：预算为正数、人数为整数、用途属于允许类型。
3. Python 规则 BUY_01：family_size → required_seats。
4. Python 规则 BUY_02：required_seats → minimum_vehicle_seats。
5. Python 规则 BUY_03：city_commute AND fuel_priority=high → economical_city_commuter。

第 3 步假设所有家庭成员一起乘车，trace 中明确标出；如用户明确要求的 seats 比 family_size 小，则追问，不覆盖用户事实。现已增加BUY_04与household_travels_together，用户可澄清并非全家同行，系统保留家庭人数、使用明确的座位需求。

`null` 表示未知；空的 preferred_brands 表示尚无明确品牌偏好。Validation 只能检查类型/范围，无法保证 LLM 正确理解原文，因此还需要自然语言案例评估。

## 文件职责

- `buyer_profile.py`：Frame 的 slots 与 Python 推理规则。
- `main.py`：连接本地 Ollama、解析结果、显示 facts/trace/追问。
- `examples/family_buyer.json`：人工填写的示范资料；这不是 LLM 提取结果。
- `test_profile.py`：独立验证规则、缺失、矛盾、非法字段；不需要 Ollama。
- `requirements.txt`：依赖范围；`requirements-lock.txt`（生成后）记录本次实际安装版本。

## 运行方式

在 VS Code 中打开 `vehicle-agent` 目录，打开 PowerShell terminal。以下命令都在该目录内执行。

首次配置（如果环境已完成，可跳过）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

先运行不需要模型的示范：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_buyer.json
.\.venv\Scripts\python.exe -m unittest -v test_profile
```

示范应该出现 minimum_vehicle_seats=6、lifestyle_profile=economical_city_commuter、三条 fired_rules 和 ready_for_matching=true。这里只说明数据足够进入匹配阶段，不表示已经匹配到车辆。

Ollama 安装后，打开新的 terminal，确认版本并下载模型：

```powershell
ollama --version
ollama pull qwen3:4b
```

保持 Ollama 服务运行，然后测试真实语言提取：

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM60000, six-person family, mainly city commuting, save fuel."
```

比较小模型时，用 `--model qwen3:1.7b`，需先下载该模型。

## 检查三个重点

1. **明确事实**：extracted_profile 与原句是否一致？required_seats 应保留 null，因为原句只说 family_size。
2. **推导事实**：derived_facts 是否显示至少六座？fired_rules 是否解释来源？
3. **未知资料**：输入“想买省油车”时，是否追问 budget、seats 和主要 usage？不能随意补预算。

再测试：“预算五万令吉，至少五座，不要Toyota，城市通勤。”预期 Toyota 在 excluded_brands，而非 preferred_brands。

再测试：“每月只能付RM800。”预期不把 800 当成购车总预算，并提出澄清。

## 当前边界与下一课

本课的main.py命令演示单轮extraction；后续课次已加入VehicleFrame、来源快照、排名、估价与议价。当前多轮memory及Agent Loop请从页首的阶段8入口运行。

Stage 1 的代码主要用于展示 Frame slots/ranges/unknown、Production Rules 与 rule trace。Class inheritance 和完整 Knowledge Base 会在下一阶段展开。

官方实现依据：
- https://docs.ollama.com/capabilities/structured-outputs
- https://docs.ollama.com/windows
