# 第 1 课：把买车需求转换为 BuyerProfileFrame

2026-10-15 输入错误修复：新增 Python 原文核对层，修正 m／miles／km、预算币种及相关边界。复测命令、结果与报告证据见 `INPUT_VALIDATION_FIX_ZH.md`。旧阶段记录保留为当时的进度。

Stage 4 估价tool已完成基础版：见 `LESSON4_ZH.md`，运行 `--value`。默认返回可核查挂牌reference；`--illustrative-adjustments`仅为明确标注的教学假设模式。

Stage 3 已加入真实来源快照与 Lifestyle Scoring：见 `LESSON3_ZH.md`，运行参数 `--rank`。新的提前交付目标见 `ACCELERATED_PLAN_ZH.md`，旧日期安排以新文件为准。

Stage 2 已完成：VehicleFrame + 预算/座位/排除品牌筛选。运行与原理见 `LESSON2_ZH.md`；新功能使用 `--match`，不加该参数仍是本课的输出。

2026-10-14 更新：应用输入、输出、Prompt、追问及错误信息统一使用英文；这份教学说明保留中文。旧中文示例用于解释概念，运行时请使用下方英文命令。

这一阶段实现 **NLU/Slot Extraction + Frame + 小型 Forward Chaining**。暂时不会推荐真实车辆，也没有完整 Agent Loop；后续阶段会加入三个工具和任务循环。

环境已在本机完成：项目 venv、Python 依赖、Ollama 和 qwen3:4b。5 项规则测试及 4 项 live model cases 已通过，见 STAGE1_RESULTS.md 与 evaluation-results.json。

## 理解数据如何流动

用户说：“预算 RM60,000，家里六个人，平时城市通勤，想省油。”

1. Ollama 提取用户明确表达的资料：budget_myr=60000、family_size=6、usage=[city_commute]、fuel_priority=high。
2. Pydantic 检查 JSON 是否符合 Frame：预算为正数、人数为整数、用途属于允许类型。
3. Python 规则 BUY_01：family_size → required_seats。
4. Python 规则 BUY_02：required_seats → minimum_vehicle_seats。
5. Python 规则 BUY_03：city_commute AND fuel_priority=high → economical_city_commuter。

第 3 步假设所有家庭成员一起乘车，trace 中明确标出；如用户明确要求的 seats 比 family_size 小，则追问，不覆盖用户事实。实际推荐前用户可纠正该假设。

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

这是单轮 extraction demonstration。它还没有 conversation memory、正式车辆 dataset、匹配排名、估价、议价或完整 Agent Loop。下一课先定义 VehicleFrame、数据来源和硬约束筛选；不要跳过独立工具验证。

Stage 1 的代码主要用于展示 Frame slots/ranges/unknown、Production Rules 与 rule trace。Class inheritance 和完整 Knowledge Base 会在下一阶段展开。

官方实现依据：
- https://docs.ollama.com/capabilities/structured-outputs
- https://docs.ollama.com/windows
