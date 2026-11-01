# 2.0 本批功能与运行说明

**2026-10-31最新：**现已另外训练并接入历史教学Ridge模型，111组资料、Alphard／Harrier限定范围可用；市场批准清单依然为0。本文的“未训练回归”描述保留为17Oct历史状态；当前操作和限制请看 [历史Regression手把手说明](HISTORICAL_REGRESSION_GUIDE_ZH.md)。

更新：2026-10-17，马来西亚时间。应用、提示词和代码使用英文；本文件用于中文辅导。

## 已确认的范围

保留：扩充有来源的车辆资料、简单 Regression（从数据学习价格关系）、Formal Fuzzy Logic（用渐变的低／中／高处理需求）、安全资料、长途舒适和可靠性口碑参考。Q5 已同意评论只是有来源的参考，资料不足显示 Unknown；Q6 已同意先完成可独立制作的模块，价格资料足够后才训练和启用回归。

取消：多年历史趋势／品牌折旧曲线、市场校准的车况／损伤扣价、证明提高真实成交率，以及全部照片功能。取消项目不再列作本版必做任务。当天证据检查与实时搜索仍是两个不同功能，当前都没有加入浏览器咨询。

Lecturer 原先允许 Regression **或** Rule-Based Expert System，照片是 optional。正式 guide 的报告／视频／presentation／Q&A／contribution 要求仍须交付。Formal Fuzzy Logic 是这次主动增加的技术深度；算法多不保证满分。原 guide 与 lecturer 的 Agent adaptation 继续分开说明，见原项目 context 和课程记录。

## 现在系统怎样运作

英文聊天 → Ollama 提取新的需求 → BuyerProfileFrame 保存已确认事实 → Python 检查证据、保留多轮记忆 → 硬筛选 → 模糊推理和资料评分 → 检查结果 → 英文 UI 展示。

Frame 就是有固定字段的资料表。新增 safety_priority、comfort_priority、reliability_priority，可填 high／medium／low，未说明则保持未知。表单仍进入同一个 Controller（控制咨询步骤的程序），不会另走一套不检查的计算流程。

先检查预算、座位、排除品牌、挂牌状态和价格依据。任何软评分都不能把被硬条件排除的车重新加回来。符合条件不代表广告仍在售，也不代表价格已包含全部费用。

### 模糊逻辑实际计算什么

`fuzzy_lifestyle.py` 实现小型 zero-order Sugeno 系统：规则输出一个常数，再根据规则触发程度求平均。这里没有训练神经网络，也不需要另外安装 scikit-fuzzy。

1. 省油输入：`clip((km/L - 10) / 15)`；行李输入：`clip(boot_litres / 600)`。clip 表示限制到 0–1。锚点是公开的课程设计，不是市场测量结论。只比较相同 fuel claim basis；行李容量只接受 all seats up。
2. 每个输入同时具有 low／medium／high 的隶属程度，例如 0.8 是 medium=0.4、high=0.6。隶属程度表示“有多接近这个描述”，不是概率。
3. 两个输入都有资料时执行九条组合规则，AND 使用两个隶属程度相乘。规则常数是 `0.8 × 偏好加权等级 + 0.2 × 较低等级`，让两方面较均衡的车得到一些支持。
4. 把各条“触发程度 × 常数”相加，再除以触发程度总和。一项偏好未启用时只有三条规则；已启用的必要输入未知时，结果 Unknown，不填中间值。
5. 模糊结果取代旧版各自的 fuel／luggage 分数，避免重复计分，再与预算、品牌、城市车长及有证据的参考项加权。

例：22 km/L → 0.8；360 L → 0.6；fuel 重要性 4、luggage 3，模糊结果约 0.68343。若该组最终权重为 40%，贡献约 27.34 分。这个例子解释算法，不代表这组油耗／容积来自某一辆真实车。

权重公开：budget=1；fuel 为 low=.5、medium=2、high=4；luggage 为 .5／2／3，未填写且 family_travel 时为2；品牌偏好=2；city_commute 的紧凑程度=1；安全／舒适／可靠性为 .5／2／3。未填写 comfort 且 long_distance 时按规则启用2，未填写安全／可靠性则不评分。fuel+luggage 合并为一个模糊组。最后用同一组总权重除法归一化，所有候选共用，不为缺资料的车重新分配权重。

### 安全与评论的分数代表什么

安全只按已证实的 ESC（车身稳定控制）、AEB（自动紧急制动）、curtain airbags（侧气帘）三项装备各占三分之一。未知装备仍保留未知并扩大分数上限。例如两项已证实存在、一项未知：支持分数66.7、资料覆盖66.7%，上限100。不是说该车只有66.7%的安全性。NCAP 星级保留报告、测试版本与适用范围，不跨协议直接平均。

舒适参考分为座椅支撑、行驶舒适、噪音、后排空间四项；有来源的 positive=1、mixed=.5、negative=0。先对同一来源家族求平均，防止一篇文章和它的配套视频算两份独立证据。至少两个独立来源家族、两项可用观察，才给数值；仍用固定四项分母，未知部分扩大上限。当前 Myvi AV 的31.25/100是这些评论的编码参考，不能写成车辆舒适度的客观测量。

可靠性需要明确车主使用期和至少两个独立来源家族，才给口碑参考值。当前没有车型满足资料政策，故全部 Unknown。代码已支持来源、使用期、分歧与评分，但**真实可靠性数值覆盖尚未完成**。试驾没有故障、CVT噪音或“品牌听起来可靠”都不足以填入故障率。

### 资料与年款边界

价格仍是原17条 asking-price snapshots（挂牌价快照），不是 transaction price（成交价）。新增的是6种车型、7个版本研究档案：Alza、Myvi H／AV、Vios、Persona、Iriz、X50。这不等于新增7辆可购买库存。

`data/model_evidence_v2.json` 记录作者、网址、发布日期或月份、适用年款／版本、评论情境及限制；`vehicle_evidence.py` 负责校验与关联。2022 Alza AV 资料不套入2020 SE。Persona 评测发表于2021年4月，无法仅凭2021年版本名称排除后来MC2改款，因此仅供研究浏览，关闭自动匹配。不同生产年不自动继承资料。

价格演示仍固定15 Oct 2026；安全／评论研究于16 Oct检查。目录显示不同的检查日期，不会刷新价格或库存。未知价格、费用、里程及可用性不补零。详见 `v2-data-audit.json` 和 `docs/V2_SOURCE_AUDIT.md`。

## 回归目前到哪里

`price_regression.py` 已准备：资料格式与使用条件检查、重复车辆分组、按车型保留测试组、只在训练资料上学习标准化参数、Ridge 回归、同车型价格中位数基线、MAE／RMSE、资料哈希和分组记录。Ridge 是限制系数过大的线性回归；NumPy 负责矩阵计算，已在现有环境和 lock 内，不需要新装 sklearn。

MAE 是平均差多少 MYR；RMSE 对较大误差更敏感。它们不是“95%置信区间”。测试组不参与系数学习，也不用于自动反复挑选参数。相同车辆跨网站或多次刊登必须放在同一个组。

本批使用的最低资料门槛是100辆已去重车辆、至少两个准确车型身份、每个身份至少15辆、90天内来源和可核对的使用依据。这是保守的课程实验门槛，**不是达到100条就证明模型可靠**。实验必须优于训练组车型中位数基线，并检查误差；即使通过，也只产生未启用的候选实验。

目前 manifest 有0条已满足训练要求的记录。原17条广告仍存在，但没有足够车型覆盖、精确里程和跨站去重／使用依据供此实验，不能把它们宣称为已训练市场模型。当前 sell／negotiation／trade-in 继续使用已校验的 rule-based asking-price context。下一步仍须取得可用价格数据、训练评估、审查车型／日期／数值适用范围，再接入价格工具、结果检查器和UI。

## 怎样运行

在 PowerShell 输入；不要复制 `PS ...>` 提示符。已有 `.venv` 不用重装软件：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

打开显示的本机网址，通常为 `http://127.0.0.1:8501`。如果8501已有此项目服务，直接使用；更新底层类／模块后建议先在原终端按 Ctrl+C，再重启，避免旧模块残留。重启前手动导出需要保存的咨询；浏览器会话本来就不自动存盘。

英文测试输入：

```text
I want to buy a car. My vehicle-price budget is RM60000. I need 5 seats for city commuting. Safety priority is high. Comfort priority is medium. Reliability priority is high. Fuel priority is high.
```

第二轮：`Change my vehicle-price budget to RM55000. Luggage-space priority is high. Exclude Toyota.` 查看 Results & comparison 的分数、覆盖与 Fuzzy rules／sources；Vehicle research 页只浏览研究资料，不会成为新的库存或执行模型调用。

离线查看和复现：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_buyer.json --rank
.\.venv\Scripts\python.exe main.py --fixture examples/family_buyer.json --rank --ranking-policy v1
.\.venv\Scripts\python.exe audit_v2.py --output v2-data-audit.json
.\.venv\Scripts\python.exe price_regression.py
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent test_streamlit_ui test_v2 test_price_regression
```

第一条默认v2；第二条保留v1基线。资料审计、回归关口和离线测试不需要Ollama；真实聊天需要本机Ollama服务与qwen3:4b。首次跨电脑安装仍按requirements-lock.txt，不把本机测试通过写成已完成组员复现。

## 接下来合理的顺序

先补可用价格资料和准确版本资料；同时收集有明确使用期的车主评论，扩大舒适／安全覆盖；再训练并评估价格模型，合格后才更新估价、议价、Controller及UI。独立推荐相关性、人工财务核算和跨电脑复现使用 `evaluation/README.md`；现有开发用例不冒充组员独立案例。最后完成报告、视频、presentation、Q&A和贡献记录。验收现况见V2_RESULTS.md。
