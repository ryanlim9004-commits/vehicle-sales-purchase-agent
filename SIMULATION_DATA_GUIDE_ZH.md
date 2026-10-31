# 历史模拟车辆资料接入（2026-10-31）

**最新显示调整：**按用户要求，聊天回复和主推荐卡片只显示排名、车型、参考价格、座位、变速箱、里程及已知油耗参考。技术编号移至可展开的Vehicle details and sources及Evidence & checks；聊天／主卡片不再重复模拟资料与评分过程说明。数据本身的模拟标记及本文件／英文报告中的用途说明继续保留，价格资料性质和估价规则不因显示调整而改变。下面涉及SIMULATION聊天标签的验收描述是调整前的历史记录。

Agent／Streamlit 默认读取两份资料：原有 `data/vehicles_real.json` 的17条挂牌广告快照，加上 `data/vehicles_simulation.json` 的97条历史模拟记录，共114条。默认读取函数是 `vehicle_frame.load_agent_vehicles()`，`main.py --rank`也使用同一份组合资料。两份文件分别保存，运行时合并，方便识别来源和复现。

## 这次采用的资料与年份规则

用户提供最新版 `historical-used-vehicles-specifications-completed.json`，项目内保留同内容副本 `data/historical_simulation_source.json`。这份文件只有97条双年份广告，不是原始CSV全部974条，也不是82条缺失Model记录全部完成的证明。它涵盖21个品牌、62组品牌＋车型；座位数2–11个，情境价格RM21,999–RM638,800。

最新版文件明确规定：描述开头的2013/2014，在模拟中以2013为制造年、2014为注册年，一条原广告只保留一条记录。这个最新规则覆盖之前拆成两条互斥年份候选的审核方案。程序核对原文双年份和这两个字段一致，并拒绝重复的原始记录分组。制造年、座位和油耗仍是模拟输入；确认格式正确不等于核实了真实车辆。

用户已明确本次不核实外部来源、用于模拟并在报告说明。程序保留资料集链接、原始行号、原文、规格链接、油耗标准和估计程度；没有把下载／整理日期填成每条广告的观察日期。

## 实际应用在哪些功能

| 功能 | 本次应用 |
| --- | --- |
| Buy | 模拟价格参与预算筛选，模拟座位数参与最少座位筛选，品牌参与排除和偏好。所有模拟候选显示SIMULATION、历史情境价格和库存未知。 |
| Lifestyle scoring | 保留100÷L/100km转换成km/L的数值。不同油耗测试标准、未明确标准、近似或估计规格会禁用本次候选集的油耗比较。具备相同明确标准的direct模拟值可用于带标识的模糊评分演示，仍不代表实车节油效果。没有补行李厢、车长、舒适、安全或可靠性数据。 |
| Sell | 读取到组合资料，但97条模拟记录被明确排除于市场挂牌价证据。原有至少3条近期准确身份可比广告的规则保留。新增97条的最大准确身份组只有2条，本次不解决更多车型的真实卖车估价覆盖。 |
| Negotiation | 仍按用户当前报价、完整费用、预算／净收入底线计算。选中模拟车型可带入车型身份，但模拟价格不自动变成对方当前报价。没有市场参考时只给有限预算／底线建议。 |
| Trade-In | 继续比较用户提供的两套购买／处置报价及贷款；模拟挂牌价不替代车商收车价或私售收入。 |
| Regression | 未加入训练清单，也没有训练或启用市场模型。 |

## 怎样查看和启动

1. 在VS Code打开 `data/vehicles_simulation.json`，搜索 `SIM-MRC-V1-0934`，可以看到Ford Fiesta的情境资料。其挂牌金额保留为情境价格，`observed_on`是null，`availability`是unknown，`simulation`保留假设。
2. 查看 `docs/simulation-data-audit.json` 的数量、分组、单位和文件指纹。`build_simulation_data.py`负责可重复转换，并验证资料格式。
3. 在原来运行Streamlit的PowerShell按Ctrl+C，随后运行：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

4. 在浏览器打开启动时显示的网址。旧会话可能持有旧资料，刷新后在聊天输入 `/reset`，再开始新的Buy咨询。
5. 输入：

```text
I want to buy a car. My budget is RM30000. I need 5 seats for family travel. Save fuel.
```

在固定教学快照下，硬条件应留下5条模拟候选：Ford Fiesta、Kia Rio、Honda City、Peugeot 5008、Volkswagen Jetta。Results前三张卡片不代表全部5条。油耗标准混合，因此本场景不能给出省油优胜结论。

6. 再输入 `I now need at least 6 seats.`，应只剩Peugeot 5008一条。预算RM20,000仍没有匹配，因为新增资料最低情境价格RM21,999；系统不自动提高预算。

可以先不启动Ollama，运行离线工具检查：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/simulation_family_buyer.json --rank
```

重新生成派生资料（覆盖生成文件；先保存任何手动改动）：

```powershell
.\.venv\Scripts\python.exe build_simulation_data.py
```

无需安装SQL Server、SSMS或新Python套件。资料继续使用JSON，Ollama负责理解消息，Python负责实际筛选、评分和检查。

## Documentation怎么写

英文报告素材放在 `docs/SIMULATION_DATA_REPORT_NOTES.md`。必须同时说明真实挂牌快照和模拟扩充的数量与用途；不能将114条写成114辆当前有货的实车，也不能将这次接入写成已经完成市场校准或回归训练。

## 本次实际检查结果

2026-10-31完整离线258项测试通过，耗时19.368秒。包括8项新整合检查及原有功能；离线模型回复使用脚本，不代表真实Ollama语言准确率。首次4项失败是原17条资料的写死数量／排序及固定9条模糊规则预期，已保留原失败记录并分别保留历史资料测试、加入114条默认资料检查和实际激活维度的规则验收。

随后真实本机qwen3:4b运行上面的RM30,000／5座英文消息，完成inspect_requirements→rank_vehicles→check_result→finish，5条匹配，所有结果检查通过。前三条是Ford Fiesta、Kia Rio、Honda City，聊天明确标注SIMULATION及油耗不可比较。界面本轮使用Streamlit AppTest检查，不声称已进行一次新的真实浏览器验收。摘要见 [本次验收记录](docs/simulation-integration-20261031.json)。
