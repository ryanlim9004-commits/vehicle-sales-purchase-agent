# 组员从 GitHub 到实际测试：手把手指南

**2026-10-31后续更新：**历史Regression已经训练并连接到Sell／Negotiation／Trade-In的限定车型范围，无须新装套件；更新代码后重启Streamlit，在新咨询测试。模型文件随项目保存，启动时不必重训。示例、误差、失败组和重训命令见[历史Regression说明](HISTORICAL_REGRESSION_GUIDE_ZH.md)。下文原始安装流程仍可使用，旧日期的测试数量保留为历史记录。

更新：2026-10-26。适用：Windows 10 22H2／Windows 11、普通64-bit Python 3.13、PowerShell。本次先验证 Windows x64；其他系统的实际结果需要另外记录。最新重复追问修复见[说明](BUY_FOLLOWUP_FIX_20261026_ZH.md)，数据接入方式见[说明](DATA_IMPORT_PLAN_ZH.md)；本机改动是否已推送以实际Git版本为准。

**组员先看本文件。网页启动入口是 `streamlit_app.py`。** GitHub 保存代码；每个人下载到自己的电脑，启动自己的 Ollama 和网页服务，再用浏览器测试。Ryan 电脑上的 `127.0.0.1` 地址在另一台电脑上不会连接到 Ryan。

## 1. 先弄清楚每个东西负责什么

| 名称／文件 | 用途 | 什么时候使用 |
|---|---|---|
| Python 3.13 | 执行项目代码 | 首次安装 |
| Git | 从 GitHub 下载、更新代码 | 首次下载与后续更新 |
| Ollama 程序 | 在本机运行语言模型的服务 | 实际聊天期间保持运行 |
| qwen3:4b | Ollama 使用的模型，需要另行下载 | 首次安装模型 |
| `.venv` | 本项目独立的 Python 依赖环境 | 每人自己建立，GitHub 不附带 |
| `requirements-lock.txt` | 已验证的依赖版本清单 | 安装 Python 依赖 |
| `team_check.py` | 检查 Python、依赖、资料及可选的本机模型 | 安装后先运行 |
| `run_team_tests.py` | 一次运行全部离线测试并保存结果 | 环境检查后运行 |
| `streamlit_app.py` | 英文浏览器界面 | 日常操作入口 |
| `agent_cli.py` | 在终端里进行英文多轮咨询 | 可选；排查聊天问题 |
| `main.py` | 独立运行一个业务工具 | 可选；不经过模型检查计算 |
| `evaluate_v2_live.py` | 自动执行两轮真实模型开发测试 | 需要 Ollama；会保存独立的新报告 |

VS Code 可用于阅读代码、填写测试记录，是可选编辑器。当前路线无需另装 Node、Docker、大型数据库、scikit-learn 或 scikit-fuzzy。浏览器用自己正常使用的 Edge／Chrome 即可。

## 2. 当前可以测试什么，还有什么未完成

已实现：需求提取与记忆、Frames／生产规则、硬筛选、Formal Fuzzy Logic（低／中／高渐变评分）、有范围限制的安全和舒适评论参考、Rule-Based Valuation（按规则选挂牌可比资料）、议价／Trade-In、Agent Loop 与英文 UI。

仍未完成：更多可用的马来西亚价格资料、真实价格回归训练与启用、足够的可靠性评论数值覆盖、组员独立推荐评估、另一台电脑实际复现，以及最终报告／视频／presentation／Q&A／贡献材料。详细状态见 [V2_RESULTS.md](V2_RESULTS.md) 和 [TEAM_HANDOFF_RESULTS.md](TEAM_HANDOFF_RESULTS.md)。

测试时必须保留这些真实边界：

- 价格仍是 **15 Oct 2026** 的17条 asking-price snapshots（挂牌价快照），不是实时库存或成交价；其中11条listed、5条sold、1条reserved。
- 6种车型／7个研究档案不代表7辆可购买库存。只有部分Myvi候选具备本批可关联的安全／舒适资料。
- 可靠性目前显示 **Unknown** 是正确结果；不能编造故障率。回归资料检查显示 `blocked_by_data` 也符合现况，不表示安装失败。
- 估价默认没有市场校准的里程／车况扣价；照片、损伤识别、多年趋势／品牌折旧曲线已取消。
- 网站 asking price、用户输入的 dealer offer 与实际 transaction price 是不同资料。测试报价只是教学输入，不是平台保证的交易收入。

## 3. 第一次：取得仓库访问权限

1. 用组员自己的 GitHub 账号登录浏览器。
2. 打开 [项目仓库](https://github.com/ryanlim9004-commits/vehicle-sales-purchase-agent)。
3. 如果看到404，先检查是否登录了自己的正确账号；私人仓库需要 Ryan 邀请该账号，并由组员接受邀请。获得访问后再继续。
4. 能看到 `README.md`、`requirements-lock.txt`、`streamlit_app.py` 才是正确仓库。

测试不需要把仓库设成Public，也不用使用Ryan的登录资料。

## 4. 第一次：安装基础软件

### 4.1 安装 Python

从 [Python 官方 Windows 下载页](https://www.python.org/downloads/windows/) 选择普通 **Python 3.13.x、64-bit** 安装。选择包含pip和Python launcher的安装方式；安装器若提供 `Add python.exe to PATH`，勾选它。使用普通版本，暂不选free-threaded实验版本。

安装完成后，关闭旧终端，从Windows开始菜单搜索 **PowerShell**，打开一个新窗口，输入：

```powershell
py -3.13 --version
```

预期显示 `Python 3.13.x`。Ryan先前记录的测试版本是3.13.15；其他3.13补丁版本也要把实际版本记入测试报告。若没有 `py` 但 `python --version` 明确是3.13，后面的建立环境命令可以用 `python -m venv .venv`。

### 4.2 安装 Git

从 [Git 官方 Windows 下载页](https://git-scm.com/downloads/win) 安装。完成后重新打开PowerShell，输入：

```powershell
git --version
```

预期显示 `git version ...`。不需要为了测试先设置自己的commit姓名，也不需要向仓库提交代码。

### 4.3 安装 Ollama

从 [Ollama 官方下载页](https://ollama.com/download/windows) 安装并打开Ollama程序。官方Windows版会在后台提供本机服务，默认地址为 `http://localhost:11434`，见 [官方Windows说明](https://docs.ollama.com/windows)。

在新PowerShell窗口输入：

```powershell
ollama --version
```

预期能识别指令。若提示无法连接服务，先从开始菜单打开Ollama应用，再进行第7步。模型还没下载是正常的。

## 5. 下载 GitHub 代码

以下命令在PowerShell逐行执行。`$env:USERPROFILE` 会自动指向**组员自己的用户文件夹**，不需要改成Ryan的路径。复制命令本身即可，不复制 `PS C:\...>` 提示符。

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projects" | Out-Null
Set-Location "$env:USERPROFILE\Projects"
git clone https://github.com/ryanlim9004-commits/vehicle-sales-purchase-agent.git
Set-Location .\vehicle-sales-purchase-agent
```

首次clone若弹出GitHub登录，在浏览器用已获仓库权限的账号登录。下载完成后，检查：

```powershell
Get-Location
Test-Path .\streamlit_app.py
Test-Path .\requirements-lock.txt
git rev-parse HEAD
```

两个 `Test-Path` 都应为 `True`。最后一行是一长串commit编号，把它记下来，表示本次测试的代码版本。

如果已经下载过，不要在同一文件夹重复clone，按第14步更新。

**ZIP备选方法：** 在GitHub绿色 `Code` → `Download ZIP`，解压后进入实际包含 `streamlit_app.py` 的内层文件夹，再在该文件夹打开PowerShell。ZIP没有Git历史，`git rev-parse HEAD`不可用；`team_check.py`仍会保存代码与资料哈希，帮助核对版本。后续更新须重新下载并解压到新文件夹，不覆盖旧测试记录。

哈希按实际文件字节计算；Git的LF／Windows的CRLF换行差异也可能改变哈希。有Git时优先同时记录commit和是否修改过代码；ZIP哈希不同须逐文件核对，不能只据此断言程序逻辑已改变。

## 6. 建立自己的 Python 环境并安装依赖

确保当前目录中有 `streamlit_app.py`。输入：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

成功标准：安装指令没有以 `ERROR` 结束，`pip check` 显示 `No broken requirements found.`。

后续每条 `.\.venv\Scripts\python.exe` 都是在调用这个项目的Python。这样无需执行 `Activate.ps1`，也无需更改PowerShell执行政策。Python套件与模型都是每个组员自行安装；GitHub不附带Ryan电脑的 `.venv` 或模型文件。

然后先做不需要模型的检查：

```powershell
.\.venv\Scripts\python.exe team_check.py --output team_results\setup-offline.json
```

应看到各项 `[PASS]` 和 `Setup result: passed`。它会明确说明还没有检查Ollama。输出文件保存在当前项目的 `team_results` 中；文件名已存在时会要求换新名字，避免覆盖旧证据。

## 7. 下载并检查本机模型

保持Ollama应用运行，输入：

```powershell
ollama pull qwen3:4b
ollama list
```

等待下载完成，在列表中确认有 `qwen3:4b`。[官方模型页](https://ollama.com/library/qwen3:4b) 当前标示该模型约2.5GB；安装程序与Python依赖还会另占空间。下载需要网络，之后本项目的模型推理和已保存资料查询在本机执行。

记录实际RAM／显卡。Ryan的RTX3050 Laptop 4GB已跑过现有案例；组员自己的硬件能否在时间限制内完成，必须用实际运行验证，不能把Ryan的速度当保证。

检查服务与指定模型：

```powershell
.\.venv\Scripts\python.exe team_check.py --ollama --output team_results\setup-with-ollama.json
```

预期 `ollama_service_and_model` 为PASS。脚本只查看服务／模型信息，不做推理，不自动下载模型。模型ID若和原记录不同会给warning，保存实际ID并报告，不把另一个模型冒充同版本。

如果11434没有服务，打开**另一个PowerShell窗口**，输入：

```powershell
ollama serve
```

这个窗口保持运行。若提示端口已经被使用，通常已有Ollama服务，回到原窗口运行环境检查即可，不要为了重复开服务而结束未知进程。

## 8. 先运行全部离线测试

在项目PowerShell输入：

```powershell
.\.venv\Scripts\python.exe run_team_tests.py --tester YOUR_NAME
```

把 `YOUR_NAME` 换成实际测试者名称。这个指令自动找出全部 `test_*.py`，不需要自己逐个打开。离线测试不用Ollama；其中Agent／UI测试使用预设模型回复，但Python业务工具实际执行。

成功标准：末尾显示 `OK`，报告中 `passed` 为 `true`，`failures` 和 `errors` 都为空。26Oct菜单／停止更新后预期250项（此前242项加8项取消与导航测试）；日后新增测试可能改变数量，必须同时记录commit和本机是否修改过代码。

最后会打印 `Offline report: ...`，例如 `team_results\offline-日期时间.json`。把实际路径记下来。若出现FAIL或ERROR，保留报告和终端输出，不修改预期值来凑通过。

## 9. 启动英文浏览器 Agent

保持Ollama服务运行，在**项目目录的PowerShell**输入：

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

看到 `URL: http://127.0.0.1:8501` 后，在Edge／Chrome地址栏输入：

```text
http://127.0.0.1:8501
```

这就是主要使用入口。PowerShell里的Streamlit进程必须保持运行。Ollama是11434的模型服务，8501是本项目网页；两个服务各有工作。

四个常用页面：

| 页面／位置 | 怎样使用 |
|---|---|
| Sidebar → Consultation area | 选择Buy、Sell、Negotiation、Trade-In；提交资料才执行咨询 |
| Consultation | 输入英文；也可以打开 `Add or update details with a form` 补资料 |
| Message the Agent | 砖红色边框内是主要聊天框，填写后按Enter发送；辅助表单默认收起 |
| View confirmed details | 侧栏按钮展开当前会话已经记住的资料；会自动更新，点击查看不执行模型或工具 |
| 表单 → Driving use | 多选City commuting／Family travel／Long-distance driving。非空选择替换旧用途；留空保留，Unknown单独清空，无需输入逗号 |
| 右侧Menu → Results & comparison | 查看当前经过工具检查的候选／计算结果 |
| Menu → Evidence & checks | 查看Facts、Rules、实际Tools和Checks；保留通过及失败记录 |
| Menu → Vehicle research | 浏览有来源的研究资料；价格、费用、库存未知，不会因此变成可购买候选 |
| Back to consultation | 从其他页面返回英文聊天 |
| 右侧Stop | 正在计算时取消当前任务，保留之前确认的资料；空闲时按钮不可用 |
| 聊天输入 `/reset` | 开始独立新案例前清空之前的记忆；原Reset侧栏按钮已移除 |
| 测试证据 | 保存输入、结果及Evidence截图；原咨询下载按钮已移除 |

每次提交后等到出现结果、追问或错误再进行下一步。原设置模型请求有90秒限制、整轮240秒限制；超时应记录。多开tab不会共享客户事实，但同一台电脑的模型仍共用。出现忙碌提示时，草稿会保留，稍后明确点Retry；不再需要则Discard。

停止检查：先完成一轮咨询，再发送修改预算等新消息；计算期间点击右侧Stop。应显示cancelled、输入框恢复、之前的已确认资料保留，本轮未完成结果不发布。之后再发新消息，应能正常继续；这不是关闭整个Streamlit或Ollama服务。详见[实测说明](STOP_MENU_20261026_ZH.md)。

金额例子：聊天用 `My maximum budget is RM1 million.`，表单MYR金额栏可用 `1million`、`1,000,000` 或 `1000k`，均代表1000000。聊天缺货币时会提示补RM／MYR；不支持的格式会给具体写法。高预算不受当前挂牌价格上限限制。详情见[输入与需求查看说明](INPUT_GUIDANCE_20261026_ZH.md)。

## 10. 四类业务的操作检查

以下是**公开的开发／操作检查例子**。它们帮助检查安装和功能，不能当作组员独立设计的测试案例。如果要提交独立案例，先按 [独立案例说明](evaluation/INDEPENDENT_CASES_GUIDE_ZH.md) 写好自己的输入和预期，再看下面示例。

### A. 买车、多轮修改与模糊评分

1. 在聊天框发送 `/reset`，再选择Buy。下文Reset也指发送此命令。
2. 在英文聊天框输入：

```text
I want to buy a car. Save fuel.
```

应追问预算、座位／用途等缺资料，不应直接编造需求。

3. 回复：

```text
My vehicle-price budget is RM60000. I need 5 seats for city commuting. Safety priority is high. Comfort priority is medium. Reliability priority is high.
```

如果模型另有合理追问，把原本明确想要的资料补清楚，同时记录这次追问；不要删除失败／重复追问记录。完成后查看Confirmed facts，fuel_priority应保留为high。

4. 再输入：

```text
Change my vehicle-price budget to RM55000. Luggage-space priority is high. Exclude Toyota.
```

核对：预算已改，其他偏好保留；候选价格不超过55000，座位至少5，不含Toyota；Results显示分数、资料覆盖和未知项。展开Fuzzy rules，可查看资料足够时的九条规则、权重和来源。缺必要输入时不编造中等值。可靠性目前应为Unknown。

5. 辅助表单也要检查一次：只把Budget改为50000，其他字段留空／Keep，点击Submit details to Agent。Confirmed facts中未修改的条件应保留；实际工具和Checks仍应有记录。

6. 另开一个新咨询，逐句发送以下三行，检查26Oct修复的重复追问：

```text
I want to buy a car. i want a car with 4 seat, for travel use, comfortable, safe fuel
family travel, maximum purchase rm20000
I mean save fuel: fuel economy is important. I have no safety preference.
```

第一句的 `travel` 没有说明是哪类用途，应显示待确认的原词，并询问用途与预算；`safe fuel` 可能指 `save fuel`（省油）或安全，应该询问。第二句应保存 `family_travel` 和20000，不应再次询问用途。第三句后应保留至少4座／舒适／省油，不凭空加安全偏好；现有快照没有符合RM20000的车，应显示 `no_matches`，不能提高预算。至少4座也允许5座或7座，不要求汽车恰好4座。

若刚更新了Python模块，先保存需要保留的输入和结果截图，在启动网页的PowerShell窗口按 `Ctrl+C`，再重新运行本指南的Streamlit启动命令；随后刷新网页并开始新咨询。仅刷新浏览器可能仍使用旧进程里已导入的代码。

### B. 卖车与里程单位

先Reset，选择Sell，输入：

```text
I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, odometer 900 m, fair condition. No major accident and no flood damage.
```

检查Facts中的 `mileage_km` 应为 **0.9**，不能是900；必要时展开Evidence中的Facts。快照政策下，符合条件的asking median应为 **44800 MYR**，范围35888–45000，状态为未按里程／车况校准的reference。里程被记录不代表已经用它扣价。

再Reset，用表单填同一身份，Odometer=50000、单位=m，Condition=fair，事故／泡水分别选No（此处是明确的教学假设）。应显示 **50 km**。若不清楚单位或历史，填Unknown并检查追问，不能靠猜。

### C. 买方议价

Reset，选择Negotiation，输入：

```text
I want to negotiate as a buyer for a Perodua Alza 1.5 SE, manufactured in 2020, automatic. The seller currently quotes RM46000 excluding fees. My total purchase budget including fees is RM46000. All fees total RM1500 and are confirmed complete.
```

核对反报价 **44500 MYR**；44500+1500=46000，不超总预算。网站挂牌参考44800与用户给出的当前报价分开显示。系统只提供建议，不接受交易。

卖方分支也应检查：在新案例中输入卖方身份、另一方出价42000、完整费用1000、旧贷款10000、最低NET收入35000。净收入计算为42000−1000−10000=31000；反报价不得低于35000+1000+10000=46000。若系统追问asking price，明确填写48000；asking price低于净底价所需金额时应要求澄清。

### D. Trade-In 两条现金路径

Reset，选择Trade-In，分两轮输入。

第一轮：

```text
I want to compare trade-in with private sale. My current car is a Perodua Alza 1.5 SE, manufactured in 2020, automatic. The trade-in gross offer is RM35000 and trade-in disposal fees are RM500. The old loan settlement is RM10000.
```

应追问缺少的replacement、private-sale或完整费用；没有给出的费用不能自动填0。

第二轮：

```text
The replacement price using trade-in is RM65000, with replacement fees RM1000. The replacement price after private sale is RM65000, with replacement fees RM1000. Private-sale gross proceeds are RM40000, and private-sale disposal fees are RM1000. All fees for both replacement quotes and both disposal quotes are confirmed complete. Available cash is RM50000. Lowest net cost is my priority.
```

手算并对照：

| 路径 | 计算 | 补差额 |
|---|---|---:|
| Trade-In | 65000+1000−(35000−500−10000) | 41500 MYR |
| Private sale | 65000+1000−(40000−1000−10000) | 37000 MYR |
| 私售在本例的现金优势 | 41500−37000 | 4500 MYR |

这些是本例假设报价，不是平台实际收车或私售承诺。缺少完成时间／投入小时就保持未知，不能断言哪条实际更快。

### E. 另外必须检查的边界

| 操作 | 正确现象 |
|---|---|
| 六人同行、预算35000、至少六座 | 当前快照应无匹配；系统不偷偷降低座位或提高预算 |
| USD预算或只有月供 | 要求MYR总购车预算，不直接按RM解释 |
| 未填／只填部分费用 | 追问或保留不完整状态，不能补成已知0 |
| 已知重大事故／泡水 | 要求独立inspection，停止普通数值估价／议价 |
| 研究页选择Persona2021 | 显示该评测范围未能区分同年改款，关闭自动广告关联 |
| Reset之后开始新案例 | 不应沿用上一位用户的旧预算、车型、费用或贷款 |

## 11. 自动真实模型检查（与离线测试分开）

确认没有另一项本机模型测试正在运行，再在项目PowerShell输入：

```powershell
.\.venv\Scripts\python.exe evaluate_v2_live.py --tester YOUR_NAME
```

它会实际调用Ollama，运行两轮英文买车／条件修改案例。需要等待；每轮打印PASS或FAIL，最后打印新的 `Live report: team_results\live-v2-日期时间.json`。

报告应有 `completed_turns: 2`、`passed: true`。只完成第一轮不算全套通过。失败／超时也保留报告，再与手动案例一起交回。脚本不会覆盖GitHub内的 `v2-live-results.json` 历史证据。

四类业务仍要按第10步手动检查。该自动脚本只覆盖指定两轮，不代表四类所有情况都通过。

## 12. 保存并交回什么

先复制 [TEAM_TEST_RECORD_TEMPLATE_ZH.md](TEAM_TEST_RECORD_TEMPLATE_ZH.md) 的记录表到自己的本机文件中。填真实姓名／日期／系统、RAM／显卡、Python／Ollama版本、模型ID、commit和各步骤实际结果。

至少保留：

1. `setup-offline.json` 和 `setup-with-ollama.json`。
2. 一份 `offline-日期时间.json`；实际模型测试的 `live-v2-日期时间.json`。
3. Buy、Sell、Negotiation、Trade-In各一份通过或失败的操作记录，以及输入、关键结果／错误和Evidence截图。
4. 自己预先写好并冻结的独立案例／哈希、实际结果和评语；与上述公开检查例子分开。

26Oct的界面设计已移除咨询下载按钮。每个案例请记录原始输入、预期、实际结果和状态，并保存Confirmed facts、Results及Evidence & checks截图；文件按自己的案例编号命名。保留实际失败现象，不把截图或手写记录称为系统导出的JSON。

刷新、Reset、关闭tab或重启服务前先保存需要保留的输入和截图。网页会话只在当前tab临时保留，截图不能用来自动恢复会话。

`team_results/` 默认被Git忽略。把需要的文件用组内既定方式交给Ryan检查；工具不会替你自动上传或通知别人。提交到Git仓库的正式验收证据由团队确认后另行整理，原始案例不随意塞进数据集。

## 13. 常见问题：按现象处理

| 现象 | 处理 |
|---|---|
| `py`／`git`／`ollama` not recognized | 确认已安装，关闭旧PowerShell后新开一个；Python可先试`python --version`，必须确认是3.13 |
| `.venv\Scripts\python.exe` 找不到 | 当前目录或环境不对；先`Test-Path .\streamlit_app.py`，再执行建立venv步骤 |
| `Activate.ps1 cannot be loaded` | 本指南使用完整Python路径，不需运行Activate或更改执行政策 |
| `ModuleNotFoundError`／依赖版本不匹配 | 用`.venv`那份Python安装lock；运行`team_check.py`，不要只在另一份全局Python装套件 |
| `No matching distribution found` | 检查普通Python3.13 x64、网络和完整错误；重新按lock安装，保留日志；不要自行删除版本限制冒充复现 |
| `model not found` | `ollama pull qwen3:4b`，再`ollama list`确认 |
| 11434 connection refused | 打开Ollama应用，或在另一个窗口`ollama serve`，再运行`team_check.py --ollama` |
| 8501 port already in use | 确认是否已运行本项目，直接打开原地址；若需要第二个实例，用`--server.port 8502`并打开8502；8502也占用时选另一个空闲端口，例如8503，不结束未知进程。模型仍是同一个 |
| 页面无法打开 | 确认Streamlit窗口仍在运行，地址、端口正确；`streamlit_app.py`通过启动命令执行 |
| 页面可开但聊天timeout | 保留错误；确认模型服务、硬件与其他模型任务，等上一项结束后重新测试。服务可开不等于推理已通过 |
| 页面运行旧模块或新类导入失败 | 先保存报告，在原Streamlit窗口Ctrl+C，更新代码后重新启动；页面刷新会建立新临时会话 |
| `blocked_by_data`／reliability Unknown | 本版已记录的资料限制，不是缺少一个安装包；见第2步 |
| 测试终端看到Streamlit `missing ScriptRunContext` warning | 离线AppTest可能出现该warning；以实际FAIL／ERROR、最终OK和JSON结果判断，应用报错另行记录 |

## 14. 第二天怎样启动、更新与结束

已经安装过，不必每天clone、建立环境或重新下载相同模型。

```powershell
Set-Location "$env:USERPROFILE\Projects\vehicle-sales-purchase-agent"
git status --short
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple -r requirements-lock.txt
.\.venv\Scripts\python.exe team_check.py --ollama
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Git提示本机有代码修改或无法快进时先记录并交Ryan确认，不用强制reset或删除文件。更新依赖后需要重新跑离线测试；拿旧commit的结果不能证明新commit通过。

测试结束：先保存报告，在Streamlit窗口按Ctrl+C。若Ollama由自己另开的 `ollama serve` 窗口启动，也在那个窗口Ctrl+C；若使用后台Ollama应用，则按正常应用方式结束。服务器停止后网页无法继续咨询是正常现象。

## 15. 可选：不用网页，直接检查工具

模型关闭时，下列命令仍能核对业务计算：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/city_buyer.json --rank
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_buyer.json --negotiate --valuation-seller examples/seller_alza.json --as-of 2026-10-15
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in
.\.venv\Scripts\python.exe price_regression.py
```

它们直接测试工具；实际Agent多轮过程则运行：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --as-of 2026-10-15
```

看到 `You:` 后才输入英文，`/reset`清空、`/stop`停止咨询、`/quit`退出。固定日期只是复现保存资料，不能把旧价格当当天行情。

## 完成检查

安装检查通过 → 离线测试通过 → 真模型推理与修改条件完成 → 四类浏览器场景、错误边界与操作证据保存 → 独立案例、硬件版本和失败情况交回。只有组员在自己电脑实际做完，才登记该组员的跨电脑复现；Ryan本机新建环境仍只算本机隔离安装检查。
