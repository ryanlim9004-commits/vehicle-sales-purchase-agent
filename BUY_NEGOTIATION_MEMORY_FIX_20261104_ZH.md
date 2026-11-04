# Buy 推荐接续 Negotiation：2026-11-04 修正记录

## 发现了什么

同一个浏览器会话中，Buy 与 Negotiation 共用 SessionState（程序保存的本次咨询资料）。只切换 Consultation area，或打开 Menu → Results 后回来，不会清空推荐。`/reset` 会清空；另开会话也不能依靠原来的推荐编号。

问题出在“选中哪辆车”的衔接。旧代码保留了 `ranked_vehicle_ids`（按推荐顺序保存的车辆编号），但没有将 `option 1` 这种数字写法接入选车流程。它原先只检查 first、second、choose 等词，而且没有强制把用户的编号与车辆 ID 一一对应。

使用用户原来的 R2/R3 三段英文输入进行真实 Ollama 复现，第一辆仍是 2015 Peugeot 5008 1.6 THP，Reference price RM27,800，推荐编号也仍在会话里。但议价跳过了 `select_vehicle`，车辆资料为空。它只凭 RM28,800 预算减 RM1,500 费用得到 RM27,300，因此即使金额符合脚本，也不能证明记住了选中的车。

这次没有原样复现截图里的 `tool_error_limit`（工具请求连续失败达到重试上限）。截图本身不足以说明当时具体是哪两个工具请求失败；本次已确认并修复的是推荐选择没有正确关联的问题。首次受限环境测试出现本机 socket 权限错误，已单独保留，不计作真实 Ollama 复现。

## 怎么修正

- 支持 `option 1`、`option #2`、`vehicle number 3`、`the first one`、`the second car` 等明确写法。
- Python 按通过检查的推荐顺序解析编号；Ollama 请求选车时，只允许使用该编号对应的 ID。执行工具时再次检查，不能用清单中的另一辆替代。
- 在议价或追问金额前先选中车辆。缺失、越界或不清楚的编号会追问，不能悄悄给出没有关联车辆的建议。
- 如果同一句输入的车型与编号冲突，例如第一辆是 Peugeot，却明确写 Toyota，会要求确认。
- 选车带入已保存的车型、年款、变速箱；只有保存的准确里程才可直接带入，不会把里程范围取中间值当成真实读数。
- 报价、费用、预算继续来自用户；Reference price 不会自动变成卖家的当前报价。改选另一辆车时，上一辆的旧报价和车况不会继续套用；本轮明确输入的新金额会保留。
- 议价回答显示车辆名称，方便检查这次到底在讨论哪辆车。
- 新推荐只有在 `check_result` 检查通过后，才会保存为下一轮可用的选项顺序。

## 重新测试与录影

1. 在启动 Streamlit 的 PowerShell 中按 `Ctrl+C` 停止旧程序。这个动作停止网页服务；Ollama 保持运行。
2. 进入项目目录，重新启动：

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
   ```

3. 打开终端显示的 Local URL，刷新网页，选择 Buy，发送 `/reset`。录 R2 与 R3 时继续使用这个浏览器会话。
4. 发送：

   ```text
   I want to buy a bigger car for my family.
   ```

5. 回答：

   ```text
   My vehicle-price budget is RM65000. I need at least 7 seats for family travel. Comfort priority is high.
   ```

6. 可以打开 Menu → Results 查看 Fuzzy rules，再回到 Consultation。不要 reset。
7. 当前这组资料的第一辆是 2015 Peugeot 5008 1.6 THP，P = RM27,800。可留在 Buy 直接发送下面的信息，也可先把 Consultation area 切到 Negotiation，再发送同样内容：

   ```text
   I want to negotiate as the buyer for option 1. The seller current vehicle offer is RM29,800.00 excluding fees. Total applicable fees are RM1500. All fees are complete. My maximum total purchase budget including fees is RM28,800.00.
   ```

8. 检查回答含有车辆名 `2015 Peugeot 5008 1.6 THP`；当前报价加费用 RM31,300，超过总预算 RM28,800。反报价 RM27,300，另加 RM1,500 费用，刚好等于预算。状态应为 `complete`，并保留“价格公平性尚未评估”的说明。

这辆车目前没有足够的合格可比价格，也没有可启用的该车型 Regression，因此属于 `limited_advice`：可以检查预算和反报价计算，不能称为经过市场校准的公平车价。

`P − 500` 不是所有车型的统一议价公式。它来自本例的“预算 P + 1000，再减费用 1500”。如果另一辆车有可用价格参考，系统还会考虑参考值，反报价可能低于预算上限。

## 验证边界

完整离线测试：335 项通过，其中 17 个新增测试方法覆盖推荐编号、错误编号、未检查清单、重设、资料变更、金额保留、旧车资料清除、车型冲突，以及真实 Streamlit AppTest 的 Results 导航和 Consultation area 切换。另验证同款不同广告仍视为不同车辆，不继承旧报价；再次选择同一广告则保留用户已确认的里程。

实际 Ollama 复测与对应源码记录见 `docs/buy-negotiation-memory-20261104.json`。AppTest 使用预设的模型回复并执行真实 Python 工具；真实 Ollama 测试另外运行。它们不等于新一轮真实浏览器录影、独立组员验收或市场准确度评估。价格资料、Regression 系数、安装依赖没有更改。
