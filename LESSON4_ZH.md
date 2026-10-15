# 第 4 课：Rule-Based Valuation Engine 与 AI/tools 分工

日期：2026-10-15。应用和代码均使用英文，本课用中文讲解。无新增依赖。

同日输入审查更新：`input_grounding.py` 在 LLM 提取后独立核对单位与来源，`mileage_km` 支持小数。`900 m` 应为 `0.9 km`，缺少单位则追问。新增19项测试，详见 `INPUT_VALIDATION_FIX_ZH.md`；下方40项是本课最初的阶段记录。

## 1. 回答你的问题：先做 tools，再让 AI 调用吗？

是。先使 Python tools 的参数、结果和规则可验证，再接动态 Agent。

最终分工：

1. LLM 理解自然语言，识别买车/卖车/议价目标与资料。
2. LLM 在允许的 tools 中提出 tool call；必要时先追问。
3. Python Agent Controller 校验工具名和参数，实际运行工具。
4. Python tool 从数据与规则计算，返回 facts、数字、sources、rule trace。
5. Controller 检查结果是否足够、是否需要继续；LLM 将结果解释成英文。

模型本身不能仅凭生成“我调用了工具”就算真正执行。Tool Calling 需要程序执行并回传 observation。LLM 不可自行修改价格或执行任意代码。业务推理也不限于LLM：Python中的Rule-Based Expert System属于symbolic AI。

**当前是模块开发阶段**：--rank/--value仍由命令选择，没有自动 intent routing、动态 tool calling 或 conversation memory。稍后才由 Agent Controller 接管这些步骤。

## 2. 本次新增文件

| 文件 | 用途 |
|---|---|
| seller_profile.py | SellerVehicleFrame、英文卖车资料提取 |
| valuation.py | 可比记录规则、挂牌参考和教学调整计算 |
| examples/seller_alza.json | 固定卖车示例，便于先验证Python逻辑 |
| test_valuation.py | 12项估价/边界测试 |
| evaluate_valuation.py | 一个真实Ollama英文输入全流程开发案例 |

main.py 新增 --value。原 --match / --rank 保留。三种动作一次只选一种。

## 3. SellerVehicleFrame 的输入

brand、model、variant、manufacturing year、transmission、mileage_km、condition。

condition允许good/fair/poor/unknown。major_accident_reported和flood_damage_reported可为true/false/null；未明确说明的历史保持未知。“good condition”不自动代表无重大事故和无泡水。

不能把注册年份无条件当制造年份。变速箱枚举Automatic/Manual/D-CVT，匹配时不把不同变速箱混为同一版本。

## 4. 默认估价流程

### 资料检查

若报告有major accident或flood damage，返回inspection_required，暂停普通估价。缺关键字段或冲突时返回needs_clarification。

### 选择comparables

当前保守规则：相同brand/model/variant/manufacturing year/transmission；真实asking-price listing；listed_snapshot；来源更新日期已知且在90天窗口内；观察日期不晚于valuation date；不重复计算相同ID或URL。

至少3条才能返回参考值。3条与90天是公开的设计参数，不是证明统计可靠性的标准。样本不足返回insufficient_evidence，不凭LLM记忆补数字。不自动跨年份并猜贬值，也不混合asking/transaction price。

### 参考计算

输出median asking price和observed min/max，逐条附source、price、mileage、日期。不是保证成交价，也未自动个性化调整里程/车况。

采用3条同为2020 Alza 1.5 SE Automatic的当前保存快照：35888、45000、44800 MYR。排序后中位数44800，观察范围35888–45000。价格跨度较大，因此附提醒核查差异。重复广告/VIN身份仍需后续审查。

## 5. 为什么默认不自动套扣价比例

数据里没有独立核验的condition标签，也没有已校准的里程/车况系数。不能把自定“车况fair扣5%”写成马来西亚真实市场规律。

因此default status=reference_only；reference.personalized_for_mileage_or_condition=false。它完成可比规则与挂牌参考计算，但不是已验证的fair-market valuation model。

为展示规则计算另有explicit opt-in教学模式：--illustrative-adjustments。教学参数：每10,000km相差1%，里程调整上限±10%；good/fair/poor因子1/0.95/0.85。参数在结果policy中公开，market_validated=false。

教学公式：reference median × mileage factor × assumed condition factor。可比里程是范围时保留范围，并计算median lower/upper reference；中点只作为明确的scenario calculation，不写成原始观测里程。超出已观察里程包络不外推；缺可比里程不调整。Observed range与scenario range都不是confidence interval。

若以后取得足够的可核实数据/专家依据，再校准规则并验证；不能现在把教学因子宣传为实际估价标准。historical trend仍未实现。

## 6. 先运行固定资料

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15
```

示例输入：2020 Perodua Alza 1.5 SE Automatic，90000km，self-reported fair condition，声明无major accident/flood damage。

预期：status=reference_only；comparable_count=3；median_asking_price_myr=44800；observed_asking_range_myr=[35888,45000]；adjusted_scenario=null。

--as-of指定快照评估日期以便教学复现；不传时按马来西亚当天日期检查freshness。以后原数据过时可能不再有足够comparables，不能通过改日期把过期证据冒充最新价格。

## 7. 真正英文输入

保持Ollama运行：

```powershell
.\.venv\Scripts\python.exe main.py --text "I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 90000 km, fair condition. No major accident and no flood damage." --value --as-of 2026-10-15
```

先查看seller_profile，再看comparables/excluded_records/reference/fired_rules。输出来源于Python计算，不是AI凭空猜价。

## 8. 可选：演示假设调整

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15 --illustrative-adjustments
```

预期：status=illustrative_scenario；adjusted_scenario.label=ILLUSTRATIVE_UNCALIBRATED_SCENARIO；market_validated=false。

本示例median reference mileage interval=100000–105000；seller=90000，mileage factor=1.01–1.015，fair factor=0.95。中点场景44800×1.0125×0.95=43092 MYR。这是教学算式，不是经过市场验证的报价。

## 9. 结果状态

| status | 含义 |
|---|---|
| needs_clarification | 关键资料缺失/矛盾，需要追问 |
| inspection_required | 重大事故/泡水报告，普通估价暂缓 |
| insufficient_evidence | 同条件有效comparables不足，不返回估价 |
| reference_only | 返回可比asking-price参考，不套未校准因子 |
| illustrative_scenario | 明确启用假设调整，仅用于教学 |

## 10. 验证与下一阶段

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_profile test_matching test_scoring test_valuation
```

共40项tests（28旧+12新）通过；一个qwen3:4b英文seller extraction→valuation开发案例通过。它们验证规则与集成，不是对真实成交价的accuracy评估。

下一阶段制作Negotiation/Trade-In tool，再连接真正Agent Controller和UI。最终报告需如实写明：目前估价是挂牌reference与教学scenario，校准、独立condition数据、transaction labels与泛化验证仍待补足。
