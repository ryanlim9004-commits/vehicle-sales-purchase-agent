# 历史 Regression 接入与操作（2026-10-31）

## 现在实际完成了什么

根据用户本轮明确要求，原有挂牌快照和历史模拟记录一起用于一个**课程用历史价格模型**。它已经实际训练，并接入 Sell、Negotiation 和 Trade-In。Ollama 的语言模型没有重新训练；新增的是 Python 用 NumPy 拟合的 Ridge Regression（带约束的线性回归，减少过度拟合）。不需要安装新软件。

现有 `price_regression.py` 和 `data/regression_manifest.json` 仍负责更严格的真实市场实验。那份清单依然没有获准的市场训练行。新增的 `historical_price_regression.py` 和 `data/historical_price_model.json` 是有明确用途标记的另一项历史教学实验。没有修改原始数据的来源、日期或市场使用批准标记。

## 用了哪些数据

输入114条：17条原始 asking-price snapshots（挂牌广告快照）和97条历史模拟记录。实际拟合111条：16条原始挂牌快照、95条历史模拟记录。1条缺少里程范围，未编造里程；2条和已有记录的车型、版本、年份、变速箱、里程范围完全一样，按可能重复先只保留一个稳定代表。排除详情见 `docs/historical-regression-results.json`。

这不是已验证的111辆独立实车；没有VIN，无法证明跨网站完全去重。Sold／reserved广告里的价钱仍是挂牌价。模拟资料缺少广告日期，程序没有填入今天日期，也没有声称它们是当前市价。

训练输入为制造年份、里程、版本文字中可直接读取的排量，以及品牌／车型／变速箱类别。为了保持价格为正，模型学习 `log(price)`，输出再转换回MYR。类别编码和数字标准化只在每次训练部分学习。没有加入座位、油耗或主观车况的假价格系数。

大多数里程是区间，例如60,000–65,000 km。模型特征暂用区间中点62,500 km作为**明确的近似输入**；源资料仍保留区间，系统不会说实车刚好跑了62,500 km。制造年直接作为数值输入，不计算无法确定的“广告时车龄”。排量无法从版本文字读出时，特征使用0作为缺失编码，不能解释为车辆真的有0L发动机。这些选择与混合历史来源都会影响误差，不建立因果折旧或车况扣价规律。

## 为什么目前只启用两个车型组

资料有很多不同车型，但大多数只有1–2条。先固定评价政策，再训练：某品牌／车型／变速箱组至少5条保守去重记录；逐次留出一组，其他数据训练，预测未参与这次训练的那组。标准化参数也只从该次训练数据计算。这样检查会不会只是记住原有价钱。

每组同时比较简单baseline（取训练部分同车型价格中位数）。只有Regression平均绝对误差更低、平均误差不超过该组平均价格的20%、最差相对误差不超过40%，才允许历史演示调用。这是课程设计政策，不是公认市场认证门槛。没有看到结果后放宽阈值。

| 品牌／车型／变速箱 | 留出组数 | Regression MAE | 中位数baseline MAE | 历史调用 |
| --- | ---: | ---: | ---: | --- |
| Toyota Alphard Automatic | 9 | RM22,945.92 | RM34,722.50 | 通过，但仅在已见版本与数值范围内 |
| Toyota Harrier Automatic | 5 | RM11,493.56 | RM13,459.90 | 通过，但仅在已见版本与数值范围内 |
| Perodua Alza Automatic | 7 | RM15,174.81 | RM12,926.86 | 不通过，保留原有规则估价 |
| Toyota Vellfire Automatic | 6 | RM35,073.65 | RM24,114.17 | 不通过，保留原有退路 |

MAE（Mean Absolute Error）就是平均差多少MYR。这里是很小样本的开发检查，不是独立或当前市场准确率。预测值±MAE仅作误差提示，不是95% confidence interval，也不保证真实价格一定落在里面。其余车型组未达5条，不启用。Jetta在保守重复处理后只剩4组。

通过组也要确认品牌、车型、具体版本、年份、变速箱和里程。没见过的版本不自动替代；制造年份必须在该版本已有年份范围内，里程也必须在该版本观察范围内。例如Alphard `2.5 G S C Package`已有2015、2019、2020的样本，所以2018可以尝试插值。它仍不能证明不同年份的配备／世代完全相同。只有一个样本的版本不会获得跨年份预测范围。

## 三个功能怎样使用它

1. **Sell：**先按原规则找至少3条相符的真实挂牌记录。足够时继续显示原中位数；不足时尝试历史模型。符合范围才返回 `historical_reference`。重大事故或水灾仍先建议检查，不计算未经校准的扣价。
2. **Negotiation：**先确认对方报价、完整费用、买方总预算或卖方净底线／贷款。有准确挂牌参考时用它；否则可用经检查的历史预测作讨论起点。还价仍不能超过买家总预算，也不能低于卖家净收入底线。历史结果不会写成“当前市场报价公平”。
3. **Trade-In：**附上旧车历史价格背景，可显示它与用户所给收车报价的差额。两条路线的补差额继续用用户输入的实际／情境报价、费用和贷款计算。模型没有dealer-offer标签，不能自行把历史预测填进缺少的trade-in offer或private-sale quote。

议价／Trade-In现在支持里程聊天和表单输入。若该车型可使用历史模型但缺里程，Agent会询问；不清楚可回答 `Unknown`，继续有限的预算／报价计算。卖车资料切到议价／Trade-In时可带入已确认里程；换另一辆车会清掉旧里程。m／km／miles转换沿用原有来源文字检查。

每个历史预测保留模型ID、数据指纹、训练范围、来源和误差。Python结果检查器会重算预测与议价／Trade-In结果；手改一个价格、换车型或换里程，不能直接通过检查。修改数据库后，数据指纹不符会停用旧模型，需重新训练并审阅结果，不会继续使用过期系数。

## 在网页尝试

先在原来启动网页的PowerShell按Ctrl+C，然后：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

打开终端显示的本机地址。刷新网页并输入 `/reset`，选择Sell，输入：

```text
I want to sell my Toyota Alphard 2.5 G S C Package. Manufacturing year is 2018. Transmission is Automatic. Odometer is 65000 km. Condition is good. No major accident and no flood damage.
```

当前保存模型的历史参考为**RM187,371.70**，模型组开发MAE约RM22,945.92；没有完全匹配的2018版本广告仍能做这个范围内的历史插值。价钱不是对今天的市场估价承诺。Results会显示Historical regression reference、误差提示和来源。若模型遗漏某项，先回答追问或用表单补充；实际模型验收记录另外列出，不把这段预期当成已经通过的真实对话。

议价可以新开咨询输入：

```text
I want to negotiate as the buyer of a Toyota Alphard 2.5 G S C Package. Manufacturing year is 2018. Transmission is Automatic. Odometer is 65000 km. The seller current offer is RM230000 excluding fees. Total applicable fees are RM1000 and all fees are complete. My maximum total purchase budget including fees is RM300000.
```

独立工具的预期是历史还价起点RM187,371.70，另加RM1,000费用，仍小于RM300,000预算。它是规则给出的情境建议，不保证对方接受。

Trade-In可在辅助表单填 `examples/trade_in_historical_alphard.json` 的值：旧车同上；两条路线替换车都RM250,000、购买费用RM1,000；trade-in收车RM160,000、处理费用RM500；私售报价RM180,000、出售费用RM1,000；旧贷款RM10,000；全部费用确认完整。结果应为trade-in补RM101,500，私售补RM82,000。私售情境少补RM19,500，来自明确输入的两个报价，不是模型保证能多卖的钱。

## 复现训练和离线计算

模型JSON已随项目文件保存，正常启动不用每次训练。更新数据库后运行：

```powershell
.\.venv\Scripts\python.exe historical_price_regression.py
```

该命令重新生成模型与评估报告。固定模型／阈值，不根据留出结果自动反复挑参数。训练和评估都很小，可在CPU完成；Ollama推理另用原来的环境。

不运行Ollama也能检查三个工具：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/seller_historical_alphard.json --value --as-of 2026-10-15
.\.venv\Scripts\python.exe main.py --fixture examples/negotiation_historical_alphard.json --negotiate --valuation-seller examples/seller_historical_alphard.json --as-of 2026-10-15
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in_historical_alphard.json --trade-in --valuation-seller examples/seller_historical_alphard.json --as-of 2026-10-15
```

全部离线测试和本机模型验收分别运行，报告自动写到忽略Git的 `team_results/`：

```powershell
.\.venv\Scripts\python.exe run_team_tests.py --tester YOUR_NAME
.\.venv\Scripts\python.exe evaluate_historical_live.py
```

后者会实际运行两条自然语言消息及一条结构化表单的Ollama Planner；不等同真实浏览器测试、组员独立评价或市场准确率验证。使用新的报告路径保留历史失败记录。

## Documentation可以怎样写

可写：**A Ridge regression model was trained on a combined historical teaching dataset. It supplies bounded fallback references for model groups that beat a median baseline in grouped development evaluation.**

必须同时披露111条实际训练资料的来源组成、里程中点近似、日期缺失、样本很少、版本范围、两个启用组和两个失败组。不能写已训练当前马来西亚fair-market-value模型，不能写准确率100%，不能把MAE当作置信区间，不能把历史预测等同dealer收车价或实际成交价。

## 这次实际验收

最终**274项离线测试全部通过，21.949秒**，包含16项新增历史模型／整合检查。Sell／Negotiation／Trade-In的真实Streamlit渲染由AppTest检查，语言模型回复在离线测试中采用脚本；并未声称进行了一次新的真实浏览器操作。

实际本机qwen3:4b另运行三项：Sell自然语言58.37秒、Negotiation自然语言53.78秒、Trade-In结构化表单加真实Planner 26.06秒，全部完成且Python结果检查通过。Sell参考RM187,371.70；议价起点RM187,371.70并符合预算；Trade-In补RM101,500，私售补RM82,000。三条独立工具示例也已执行并返回预期状态。

第一次受限环境下的专项界面／临时文件检查被Windows临时目录权限阻挡，授权后专项测试通过；初轮完整273项通过，再增加一项直接回答里程／Unknown及防止替换车里程串入旧车的边界检查后，最终274项通过。早期记录保留在本机 `team_results/`，摘要见 `docs/historical-regression-acceptance.json`。真实Ollama验收后没有改动业务运行代码；最后只补测试、模型文件的来源指纹和说明。以上都属于开发验收，仍没有独立市场标签、组员盲评或第二台电脑的复现证据。

技术参考：[Ridge官方说明](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)、[避免训练／测试资料泄漏](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)。实现使用现有NumPy，不依赖scikit-learn。
