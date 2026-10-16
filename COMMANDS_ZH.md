# PowerShell运行命令解释

更新：2026-10-16。应用输入使用英文。现有电脑已装好Python、项目venv、Ollama和qwen3:4b，本轮不需要重新安装。

## 1. 先进入项目目录

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
```

`cd`改变当前目录；双引号把完整路径作为一个参数。以下命令都在此目录执行，不要复制PowerShell显示的`PS C:\...>`提示符。

```powershell
ollama list
```

列出已下载模型；确认存在`qwen3:4b`。它不启动车辆系统。Ollama服务须运行，Python才能通过`127.0.0.1:11434`访问本机模型。

## 2. 最常用：启动多轮Agent

```powershell
.\.venv\Scripts\python.exe agent_cli.py --as-of 2026-10-15
```

从左到右：

| 部分 | 意思 |
|---|---|
| `.\` | 从当前目录开始找 |
| `.venv\Scripts\python.exe` | 使用本项目安装了依赖的Python，不必先activate |
| `agent_cli.py` | 启动多轮交互入口 |
| `--as-of` | 给本次consultation一个可复现的证据判断日期 |
| `2026-10-15` | 保存快照的复现日期；不是今天自动抓到的数据 |

不传`--as-of`则按马来西亚当天日期检查估价证据；真实来源日期过旧时可能不满足freshness要求。不要为了呈现“最新市场”而把旧日期当作新数据。

出现`You:`后，依次输入并等待回复：

```text
I want to buy a car. Save fuel.
```

```text
My vehicle budget is RM60000, a six-person family, mainly city commuting. Exclude Toyota.
```

```text
Change my budget to RM35000.
```

第1轮追问缺失资料；第2轮合并并执行筛选／评分；第3轮只修改预算、保留其他facts。状态`complete`可能是找到候选，也可能是经检查的`no_matches`，不表示已成交。

| 会话指令 | 作用 |
|---|---|
| `/reset` | 清空会话facts和goal，重新开始 |
| `/stop` | 停止本次咨询，保留已确认facts |
| `/quit` | 退出CLI程序 |

## 3. Agent的其他运行方式

保存／恢复本机会话：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --session sessions/demo.json --as-of 2026-10-15
```

`--session`指定本地JSON文件；每轮后保存，下一次同路径可恢复typed facts。历史tool observations不会直接当新鲜结果使用。该目录已被Git忽略。

用文件依次输入三轮示例：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --script examples/agent_buy_dialogue.json --as-of 2026-10-15
```

`--script`读取JSON string list；它仍会调用真实模型，不是直接输出预存答案。

单轮执行并查看结构化记录：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --message "I want to buy a car. Budget RM50000, at least five seats, mainly city commuting." --as-of 2026-10-15 --json
```

`--message`提供一条消息；`--json`显示facts、rules、tools、checks等。`--message`可以配`--session`续接事实，但不能与`--script`一起使用。脚本配`--json`时逐轮输出JSON对象。

```powershell
.\.venv\Scripts\python.exe agent_cli.py --help
```

`--help`只显示可用flags，不发起模型咨询。`--model`可指定另一个已经安装的兼容模型；当前验收使用`qwen3:4b`。

## 4. 单独运行业务tools：main.py

`main.py`每次执行一个明确动作，适合学习与排查；它不是交互聊天窗口。`--fixture`读取人工JSON，不调用Ollama；`--text`先调用真实模型提取。

只看Frame和规则：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_buyer.json
```

自然语言提取buyer facts：

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM60000, six-person family, mainly city commuting, save fuel."
```

硬筛选虚构教学车辆：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_no_toyota.json --match
```

筛选真实来源快照，再Lifestyle Scoring：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/city_buyer.json --rank
```

卖车asking reference：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15
```

`--value`默认只给reference。额外加`--illustrative-adjustments`会启用未校准的教学假设，不是更准确的市场估价。

议价，实际关联valuation tool：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_buyer.json --negotiate --valuation-seller examples/seller_alza.json --as-of 2026-10-15
```

`--valuation-seller`是被估价车辆的seller fixture；程序实际执行估价并检查identity/date关联，不让模型自行填写median。将第一个fixture换成`examples/negotiation_seller.json`可查看卖方场景。

Trade-In现金比较：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in
```

同时附旧车网站挂牌背景：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in --valuation-seller examples/seller_alza.json --as-of 2026-10-15
```

费用缺失示例：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in_unknown_fees.json --trade-in
```

应追问而非把未知费用当0。`--vehicles`可以覆盖默认dataset，但文件仍必须通过Frame验证。`--match`默认demo data，`--rank`／`--value`默认real-source snapshots。

`--text`和`--fixture`必须二选一；`--match`／`--rank`／`--value`／`--negotiate`／`--trade-in`最多选择一个。单独main.py的议价／Trade-In使用fixture；自然语言请用agent_cli.py。

## 5. 运行程序测试

完整离线回归：

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent
```

`-m unittest`运行Python内置测试模块；`-q`减少输出；后面是文件模块名，不带`.py`。当前共134项test methods，部分有多个subTests。此命令不需要模型；它不会证明所有英文提取或市场判断准确。

只详细看一个算法模块的测试：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_scoring
```

`-v`逐项显示测试名。测试可能创建临时文件／子进程，但不应修改业务数据。

## 6. 开发评估与数据脚本

下面不是启动系统的必需步骤。部分脚本会重写其结果文件；历史记录如需保留，优先使用支持的`--output`另存。

```powershell
.\.venv\Scripts\python.exe evaluate_stage5_stage6.py --output stages5-6-rerun.json
.\.venv\Scripts\python.exe evaluate_agent.py --output stage8-rerun.json
```

第一条默认运行八个固定tool案例；加`--live`再增加两个模型案例。第二条运行实际Ollama Agent验收；`--case buy`／`sell`／`negotiate`／`trade_in`可只跑一组。

| 脚本 | 模型／会写入什么 |
|---|---|
| `evaluate_extraction.py` | 真实Ollama；重写evaluation-results-english.json，可选`--model` |
| `evaluate_ranking.py` | 真实Ollama；重写stage3-live-results.json |
| `evaluate_valuation.py` | 真实Ollama；重写stage4-live-result.json |
| `evaluate_negotiation.py` | 不调用模型；重写stage7-results.json |
| `audit_input_cases.py --output input-audit-rerun.json` | 真实Ollama；写入指定输出文件，不会自动切回旧代码 |
| `evaluate_input_fix.py` | 部分真实Ollama；读取before/after文件，重写input-fix-verification.json |
| `check_data_quality.py` | 不调用模型／网站；重写data/quality_report.json并显示报告 |
| `data/build_curated_snapshot.py` | 不联网；用保存的人工事实重建data/vehicles_real.json和source_receipts.json |

例如运行质量检查：

```powershell
.\.venv\Scripts\python.exe check_data_quality.py
```

这不会确认今天网站库存，也不会扩充车型。不要把“脚本成功”理解成全部来源已在线重新核实。

## 7. 怎样阅读退出状态和结果

- PowerShell命令结束后回到提示符，表示该进程结束；Agent交互窗口则会继续显示`You:`。
- `main.py`成功执行返回exit code 0，输入／资料验证错误为2，模型提取错误为1；返回no_matches也可以是一次成功执行。
- Agent CLI的`complete`／`needs_clarification`／`reset`／`cancelled`是正常咨询状态；timeout／protocol_error／step_limit等不能当成功完成。
- 结果中的`checks`是程序核对证据；`tools[].executed`表示请求是否实际成功执行，不能只看模型文字声称已完成。
- 没有加入实时网站搜索、交易执行、Streamlit UI或新的模型训练；comments不会增加这些能力。
