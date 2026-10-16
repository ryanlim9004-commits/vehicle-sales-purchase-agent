# JSON数据、示例与验收记录阅读说明

更新：2026-10-16。JSON不支持普通代码comments；本文件解释它们，原始数据和历史结果没有为了注释而改写。

阶段9新增stage9-browser-buy.json／stage9-browser-trade.json／stage9-browser-sell.json／stage9-browser-negotiation.json，保存真实浏览器买车两轮、Trade-In一轮、卖车一轮与议价一轮的手动导出及验证说明，共5个独立model-driven turns。negotiation导出也包含先前seller turn，不重复计数。它们来自实际Ollama与tools；客户金额／偏好为synthetic场景，来源广告仍为保存快照。浏览器导出的vehicle-consultation.json不是可导入恢复的session文件；第一版不自动写聊天历史。

## 1. 先认识JSON写法

```json
{
  "budget_myr": 60000,
  "family_size": 6,
  "required_seats": null,
  "usage": ["city_commute"],
  "fuel_priority": "high",
  "excluded_brands": []
}
```

这是教学节选。Object用`{}`保存命名字段；array用`[]`保存多个项目。文字用双引号，数字不加引号。`null`是未知，`false`是否定，`0`是已知零，三者不能混用。这里的required_seats未知，可以由Python规则按家庭出行事实推导；不是说不需要座位。

## 2. 车辆与来源资料

| 文件 | 用途 |
|---|---|
| `data/vehicles_demo.json` | 八条明确虚构的教学车辆，用于理解／测试，不是市场价格 |
| `data/vehicles_real.json` | 17条人工整理的网站广告快照，含sold/reserved历史记录；不是实时库存 |
| `data/source_receipts.json` | 保存每条ID、URL和当时核对的关键字段，追踪本地来源对应关系 |
| `data/quality_report.json` | 汇总missingness、可能重复、receipt检查与exact comparable覆盖，不是修复后的新数据 |

主要VehicleFrame字段：

| 字段 | 含义／单位 |
|---|---|
| vehicle_id | 一条source ad/inventory记录的标识；不代表VIN已跨网站验证唯一 |
| brand / model / variant | 品牌／车型／具体版本，估价时不能随意混合 |
| year / transmission | 制造年份／变速箱；注册年份不是同一字段 |
| currency / price_myr / price_type | 币种、金额、asking／transaction／illustrative标签 |
| seats | 可核实的整数座位数；不明确的“7 & Above”不能直接当精确7 |
| mileage_km | 精确里程，单位km；未知则null |
| mileage_min_km / mileage_max_km | 来源只给区间时保留上下界，不自动取中点 |
| condition | 可用车况标签；现有真实资料缺独立inspection labels |
| source_kind / source_reference | synthetic_demo／listing／transaction及对应来源 |
| observed_on / source_updated_on | 保存观察日期／来源自己的更新时间，二者不同 |
| availability | listed_snapshot／sold／reserved／unknown；快照不保证今天仍可买 |
| fuel_km_per_l / fuel_basis | 油耗参考km/L及测试／claim口径；不同口径不能直接评分比较 |
| fuel_source_reference | fuel数值的证据链接 |
| boot_litres / boot_configuration | 行李厢litres及座椅状态；第三排折叠不等于满座时容量 |
| length_mm / specs_source_reference | 车长mm及规格来源；车长只是城市紧凑程度proxy |
| evidence_notes | 当时来源事实、缺失与限制的文字记录 |

source_receipts的agreement只表明本地表格与记录一致，不独立证明广告真实、车况良好或库存最新。

## 3. examples人工输入

这些fixtures是手写输入，不是模型成功抽取的证据。`--fixture`仍会验证其类型，但不调用模型。

| 文件 | 代表场景 |
|---|---|
| `family_buyer.json` | 六人家庭、省油、城市通勤的基本Frame／规则示例 |
| `family_no_toyota.json` | 家庭需求加排除Toyota，用于硬筛选 |
| `city_buyer.json` | fuel／space偏好的城市买家，用于评分 |
| `seller_alza.json` | 旧Alza卖家身份／里程／车况与history，用于估价与reference关联 |
| `negotiation_buyer.json` | 买方对方报价、总预算、费用与车型identity |
| `negotiation_seller.json` | 卖方对方出价、净底价、费用、结清额与identity |
| `trade_in.json` | 两条完整现金路径、时间／投入和偏好；数字是教学场景 |
| `trade_in_unknown_fees.json` | 一条路径费用未知／未完整，预期应追问 |
| `agent_buy_dialogue.json` | 英文string list，供Agent依次接收三轮消息；不是预存模型回答 |

Buyer／Seller字段与允许范围见buyer_profile.py、seller_profile.py；quote结构见consultation_frames.py。

## 4. 结果中常见字段

| 字段 | 应怎样阅读 |
|---|---|
| extracted_profile / seller_profile / profile | 本次计算所使用的明确输入；须区分模型提取和人工fixture |
| derived_facts / fired_rules | Python推导事实，以及触发的规则ID／理由 |
| missing_slots / clarification_questions | 尚缺或冲突的资料；不能自动当默认值 |
| matches / rejected | 通过硬条件的记录／被拒绝记录与原因 |
| score_breakdown | 各feature normalized_value、weight、weighted_points和source |
| weighted_data_coverage_percent | 活跃权重中有可用数据支持的比例，不是准确率 |
| score_upper_bound | 若未知feature最高取1的可能分数上界，不是confidence interval |
| reference / comparables | 从哪些asking ads计算median/range；不表示已确认成交价 |
| adjusted_scenario / market_validated | 可选未校准教学调整及其标记；不能改写成已验证市场估价 |
| current_offer_myr | 对方提出的裸车报价／出价，费用另列 |
| asking_price_context / valuation_evidence | 实际valuation observation关联的挂牌背景，不替代gross offer |
| net_proceeds_myr | gross disposal offer减费用／旧贷款后的净额，可为负 |
| cash_difference_myr | replacement package减净收入；正需补钱、负为盈余 |
| suggested_path / action | 在已知事实与限制内的条件性建议，不自动执行交易 |
| expected / actual / passed | 测试预期／实际／字段核对结果；开发通过不等于泛化accuracy |
| seconds / elapsed_seconds | 当时测得延迟，不保证以后相同 |

## 5. 历史验收与失败记录

| 文件／组 | 证据范围 |
|---|---|
| `evaluation-results.json` | 早期真实提取记录，含当时中文示例；保留原历史 |
| `evaluation-results-english.json` | 英文buyer extraction小样本 |
| `stage3-live-results.json` / `stage4-live-result.json` | 当时真实模型→排名／估价开发案例 |
| `input-audit-before.json` / `input-audit-after.json` | 单位、币种、年份、history修复前后实际模型读数 |
| `input-fix-verification.json` | 已保存audit字段复核与live tool pipelines |
| `stage5-stage6-acceptance.json` | 阶段5/6十个场景，含两个live模型案例 |
| `stages1-7-tool-recheck.json` | 最新八个固定data/scoring/valuation复核 |
| `stage7-results.json` / `stage7-recheck.json` | 议价／Trade-In八个固定场景，报价／时间synthetic |
| `trade-in-reference-recheck.json` | 单工具Trade-In实际关联asking reference，并保留现金报价 |
| `stage8-live-results.json` | 最终实际Ollama Agent八轮验收，含一次reset |
| `stage8-live-initial-failures.json` | Agent开发早期失败结果，保留而非当成功 |
| `stage8-live-before-trade-scope-fix.json` | Trade-In目标scope修复前的记录 |
| `stage8-live-before-quote-role-fix.json` | gross offer／replacement price归属修复前的记录 |
| `stage8-smoke.json` / `stage8-smoke-fixed.json` | 早期协议／提取修复过程的smoke记录 |
| `stage8-structured-smoke.json` / `stage8-valid-actions-smoke.json` | structured requests及动作限制开发过程；按各文件实际status阅读 |
| `comment-only-verification.json` | 本轮注释修改的AST／配置检查与离线测试记录，不是新模型验收 |

不要为了让报告好看而改旧失败结果、把同一套调试案例当holdout，或把历史成功复制成一次新运行。需要重跑时参照COMMANDS_ZH.md，使用新输出名保留旧证据。

## 6. Agent session与trace

`sessions/*.json`是可选本机会话，包含四类Frame、goal、provenance、issues和trace；不提交GitHub。`provenance`追踪事实来自哪轮／哪句话，`issues`记录尚未解决的问题，`trace`按turn/category保存事件。

Agent返回：`facts`是当前目标事实；`rules`是规则记录；`tools`是实际执行／拒绝的请求和observation；`checks`是独立核对。`model` trace只记录请求阶段、成功／失败和有限metrics，不是可要求模型自报的“已执行证据”。

恢复session时只恢复经类型验证的状态；当前工具仍应重算。已保存的旧observation不能证明网站、报价或候选今天仍相同。
