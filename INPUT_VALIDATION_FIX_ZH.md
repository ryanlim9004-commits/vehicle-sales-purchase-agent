# 输入资料核对与单位错误修复

日期：2026-10-15。应用代码、提示与输出仍使用英文。

## 实际发现了什么

用户上传的运行记录中，`50000 m` 被记录为 `50000 km`。随后用本机 qwen3:4b 重现：`900m` 一次被提取为 `90000km`，`900 miles` 被提取为 `900km`。这些是实际记录的错误，不是假设案例；小模型其他次运行也可能产生不同错误。

原因：Pydantic 能检查 mileage_km 是合法数字，却不能证明数字符合原句单位。此前过度依赖 LLM 完成数值转换。

现在的数据流程为：英文输入 → LLM 提取 → Frame 类型检查 → Python source grounding → 匹配／估价工具。新增 `input_grounding.py` 独立从原文核对显式数值与单位，并将依据记录在 `input_validation_notes`。

## 修复与边界

| 输入／情况 | 现在的处理 |
|---|---|
| 900 m | mileage_km=0.9 |
| 50000 m | mileage_km=50.0 |
| 900 miles | mileage_km=1448.4096 |
| 90k km、90,000 km、90 000 km | mileage_km=90000.0 |
| 只写 mileage 90000，没有单位 | 保留 null，追问单位 |
| 冲突里程、范围或约数 | 保留 null，追问一个明确读数 |
| 里程与每日通勤距离同时出现 | 排除明确标注的每日通勤距离 |
| USD、单独 $、没有币种的预算 | budget_myr=null，要求明确 MYR；不猜汇率 |
| 只有月供 | 不当作购车总预算 |
| 月供与明确总预算同时出现 | 识别明确总预算，移除已解决的预算追问 |
| 币种无法使用，但座位／用途明确 | 保留可确认的其他需求，再追问 MYR 预算 |

注册年份与制造年份、未知事故／泡水历史也加入检查。原始审查案例中这两类本来已正确返回 null；这次是加固，不能写成曾经重现了相应错误。“good condition”仍不能证明没有事故或泡水。

`SellerVehicleFrame.mileage_km` 改用 float，避免无法表示不足 1km 的读数。原本整数里程仍可使用。用户没有声明的事实不会因为资料看起来完整就自动补为确定值。

这是一组有边界的英文输入检查，不是完整 English parser。特殊表达仍可能需要重述；brand、variant、condition 等语义也仍需继续评估。通过下列案例不代表系统没有任何 bug。

## 如何自行重测

不需要安装或更新软件。保持 Ollama 运行，在 vehicle-agent 目录重新执行：

```powershell
.\.venv\Scripts\python.exe main.py --text "I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 50000 m, fair condition. No major accident and no flood damage." --value --as-of 2026-10-15
```

检查 seller_profile.mileage_km=50.0；input_validation_notes 应说明从 50000 m 换算成 50 km。把 50000 m 改成 900 m，预期 0.9；改成 900 miles，预期 1448.4096。

默认估价仍为 reference_only，没有根据卖家里程／车况个性化调整，因此可比挂牌中位数可能仍为 MYR44800。应以里程字段和换算依据验证本次修复，不以参考价是否改变判断。

## 验证证据

- `input-audit-before.json`：修复前 9 个实际 Ollama 边界案例。
- `input-audit-after.json`：修复后同组 9 个实际案例；这是当时记录，保留了后续进一步修复前的 USD 案例其他字段缺失情况。
- `input-fix-verification.json`：9 个关键字段检查，以及随后运行的 3 个完整流程案例。后者包括普通买家排名、普通卖家参考估价，以及 USD 预算时保留五座和 city_commute 需求；三项实际通过。
- `test_input_grounding.py`：19 项测试方法，含多个 subTests，覆盖单位、数字格式、币种、范围／冲突、年份、事故历史和 extraction 入口。
- 完整回归：原有 40 项加新增 19 项，共 59 项测试方法。

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding
```

这些验证针对输入一致性和程序行为，不是市场估价 accuracy 或全面自然语言准确率。

## 可用于报告的 Challenge

Structured output satisfied the schema but misrepresented measurement units. We added deterministic source-text validation and unit conversion before tool execution, retained normalization evidence, and requested clarification for unsupported or conflicting values. Regression tests and local-model cases verify the supported forms; broader language coverage remains future work.
