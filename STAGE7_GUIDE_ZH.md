# 阶段7：Negotiation / Trade-In — Decision Tree + Calculator

日期：2026-10-15。应用字段、命令、提示和输出保持英文。无新增依赖。

本页记录阶段7的独立Python tools及人工JSON CLI入口；这些命令不需要Ollama，也不需要访问互联网。最新阶段8已加入英文自然语言、记忆与动态工具请求，运行agent_cli.py，见[阶段8说明](STAGE8_GUIDE_ZH.md)。不要将下面的历史测试数量当作当前总量。

最新参考价支持：议价与Trade-In均可关联实际valuation结果；独立Trade-In命令可加`--valuation-seller examples/seller_alza.json --as-of 2026-10-15`。Agent知道旧车identity时可取得identity-only asking reference，无需虚构里程／车况。它是保存的网站挂牌背景，不能替代用户实际gross trade-in offer；详见[阶段1–7核对](STAGES1_7_AUDIT_ZH.md)。

## 1. 先理解四个概念

- `NegotiationFrame`：买家／卖家、对方当前报价、费用、自己的预算／净底价，以及可关联的车辆identity。
- `TradeInFrame`：Trade-In与private sale两条路径的独立报价、费用、旧贷款结清额，以及用户预计的时间／投入。
- `negotiation.py`：手写IF–THEN Decision Tree，不是训练出来的ML tree，不保证最优还价或成交。
- `trade_in.py`：Decimal货币计算与偏好决策；未知金额不填零，不推测真实费用、时间或私人出售价格。

每项MYR输入最多两位小数。费用、贷款结清额可以明确为0，缺失则是null。`fees_confirmed_complete=true`表示已经确认该栏是完整费用总额；只有部分费用时填false并追问。

## 2. 议价金额的定义

`current_offer_myr`始终是**对方当前提出的裸车金额**：自己是buyer时是seller报价，自己是seller时是buyer出价。它不包括另外列出的fees。

买家的`buyer_total_budget_myr`是包括费用的总现金预算：

```text
offered_total_cost = current_offer + fees
maximum_vehicle_price = buyer_total_budget - fees
```

卖家的`seller_minimum_net_myr`是扣除费用与当前车辆贷款结清额后，至少要拿到的净收入：

```text
offered_net_proceeds = current_offer - fees - loan_settlement
minimum_vehicle_price = seller_minimum_net + fees + loan_settlement
```

这里尚未计算购入新车贷款的月供、利息或长期持有成本。若seller的底价是裸车价，先按实际费用／结清额转换成对应净收入，不能把两种底价定义混用。

## 3. 手写Decision Tree

| 规则 | 条件与结果 |
|---|---|
| NEG_EVIDENCE_LINK | 提供的估价车型identity／日期不匹配，或reference算术不一致→先澄清 |
| NEG_DAMAGE | 关联估价要求事故／泡水检查→暂停普通议价建议 |
| NEG_REQUIRED | 角色、对方报价、完整费用、自己的预算／净底价／结清额缺失→追问 |
| NEG_BUY_FEES | 费用已用完buyer总预算→要求调整预算／费用，不生成负数车价 |
| NEG_BUY_BUDGET | current offer + fees超过预算→还价不超过预算减费用 |
| NEG_BUY_REFERENCE | 总金额在预算内，但裸车报价高于可比asking range→使用asking median作为可讨论anchor |
| NEG_BUY_LOW_REFERENCE | 报价低于observed asking range→要求核对规格／车况／费用差异，不自动说划算 |
| NEG_BUY_WITHIN_LIMIT | 总额符合预算→review_offer；不会自动接受交易 |
| NEG_SELL_CONFLICT | 自己asking price不足覆盖净底价、费用和结清额→要求确认矛盾 |
| NEG_SELL_RESERVE | 当前出价扣费／贷款后的净收入低于底价→counter至少覆盖净底价 |
| NEG_SELL_REFERENCE | 虽达到净底价但低于asking range，且存在更高的合适anchor→提出counter |
| NEG_SELL_WITHIN_LIMIT | 达到净底价→review_offer；不会自动卖出 |

Counter anchor优先使用未调整asking median，再限制在自己的预算／底价及已声明asking price范围内。没有估价依据时返回`limited_advice`，只能检查用户给的限制，`price_position=not_assessed`，不能宣称判断了市场合理价。

只有通过CLI的`--valuation-seller`运行实际valuation tool后，才关联该结果。工具核对brand/model/variant/year/transmission、as_of及reference中位数／range／数量一致性。后续Controller也应传真实tool observation，不能让LLM自己填一个估价范围。比较的始终是原始asking reference，教学调整43092不会变成真实市场议价anchor。

## 4. 运行买方示例

以下在vehicle-agent目录运行。首次需要时：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
```

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_buyer.json --negotiate --valuation-seller examples/seller_alza.json --as-of 2026-10-15
```

人工示例：对方当前报价46000，费用1500，总预算46000。总成本47500超过预算，裸车上限44500。asking median为44800，但预算约束优先，所以suggested_counter_price_myr=44500；status=advice_ready，rule=NEG_BUY_BUDGET。

不传`--valuation-seller`也能运行，但status=limited_advice，只能按预算给出上限，不评估市场价格。车辆identity、as_of及来源链接保留在valuation_evidence中。固定as_of用于复现保存快照，不表示网页实时库存。

## 5. 运行卖方示例

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_seller.json --negotiate --valuation-seller examples/seller_alza.json --as-of 2026-10-15
```

人工示例：买家出价40000，卖出费用1000，旧贷款结清5000，希望至少净得38000。当前净收入34000不足；最低裸车价44000，关联asking median44800，因此counter=44800，对应净收入38800。不会自动接受或向买家发送消息。

## 6. Trade-In与自行出售的计算

每条路径分别计算：

```text
Net proceeds = Gross offer - Disposal fees - Current loan settlement
Cash difference = Replacement price + Replacement fees - Net proceeds
```

展开后就是用户原公式加上已明确的卖出费用与旧贷款结清额：

```text
Cash difference = Replacement price - Gross offer
                  + Replacement fees + Disposal fees + Loan settlement
```

两条路径的replacement price／fees分开输入，允许dealer package折扣不同。同一费用不能在两个栏位重复计入；若报价已扣除贷款或费用，先转换成这里要求的gross offer，不能重复扣除。

| 示例项目 | Trade-In | Private sale |
|---|---:|---:|
| Replacement price | 65000 | 65000 |
| Replacement fees | 1000 | 1000 |
| Gross offer | 35000 | 40000 |
| Disposal fees | 500 | 1000 |
| Old loan settlement | 10000 | 10000 |
| Net proceeds | 24500 | 29000 |
| Cash difference | **41500** | **37000** |

自行出售后换车在本人工场景下少补4500。若dealer的trade-in replacement price改成60000，trade-in补36500，反而比private sale少补500。不能只比较35000和40000两个收车价格。

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in
```

检查paths里的net_proceeds_myr、cash_difference_myr、within_available_cash，以及comparison和fired_rules。正cash difference是需补现金，负数是现金盈余。负净收入也保留，例如旧贷款大于净卖价时，不会把负资产截成0。

## 7. 时间、便利性与未知值

Convenience目前只用用户提供的`estimated_completion_days`和`estimated_effort_hours`两个proxy，不声称涵盖全部便利性。示例2天／2小时和21天／12小时都是人工假设，不是真实dealer保证。

`priority=net_cost/speed/effort`决定偏好的比较方向。若available_cash已知，先排除超过现金上限的路径，再按偏好选择；没说偏好、对应估计缺失或平分时，不强选总体赢家。available_cash未知时，仅给条件性建议并明确未验证affordability。

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in_unknown_fees.json --trade-in
```

预期status=needs_clarification；private_sale的cash_difference_myr=null；comparison=null；suggested_path=null。已知完整的另一条路径仍可计算，但不能以未知费用为0来宣布两条路径的赢家。

## 8. 验证与报告证据

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation
.\.venv\Scripts\python.exe evaluate_negotiation.py
```

阶段7当时完整94项tests通过，其中新增27项，含预算／净底价边界、费用未知／部分、关联错误、旧贷款、negative equity、cash surplus、不同package、时间偏好、cash约束、MYR精度及CLI错误路径。stage7-results.json保存8个验收场景：5个实际CLI调用与3个直接tool场景，全部通过。阶段8后的总量为134项，最新结果见STAGE8_RESULTS.md。

报价、费用和时间均为synthetic fixtures；关联的asking reference来自现有真实来源保存快照。阶段7独立工具验收不涉及模型提取；阶段8另有真实Ollama验收，但仍没有成功成交率、最优谈判策略或真实市场准确率的验证。无需新增软件；阶段5–8交付版本以Git提交记录为准。

报告可以解释：Frames表示事实，hand-authored Decision Tree表示政策，Calculator负责可复核的金额，fired_rules提供解释。实际挑战是避免把裸车价与总预算混为一谈、避免未知费用填0，以及避免dealer package差异造成错误比较。阶段8现已连接这些tools，接下来是英文UI与更广系统评估。
