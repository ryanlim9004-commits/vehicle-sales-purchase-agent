# Sell／Negotiation／Trade-In 提问示例（2026-11-01）

## 同日后续：Axia缺少资料时也保留格式例子

用户用 `the brand is perodua, axia` 发现旧提示只重复“No saved example”。查核确认Controller实际读取114条车辆资料，Perodua有Alza、Myvi和Bezza，**没有Axia**。这不是资料加载失败；旧提示过度要求示例也要完全匹配该车型，导致用户不知道怎么填写。

现在每轮先说明一次Axia尚未收录，再继续显示输入例子。例如版本：

```text
What is the exact vehicle variant? (e.g. 1.5 SE [Perodua Alza], 1.5 H [Perodua Myvi]; format examples from other saved models, enter your actual vehicle value)
```

这两个版本确实来自资料库，但不会被写成Axia的版本。年份和变速箱也保留资料库数值的格式示例，并说明应输入自己的真实资料。它不会修改用户记录的Axia、补造Axia资料或给Axia虚构估价。若整个资料库没有可举例的值，才改用车辆文件／Unknown的通用说明。

真实本机qwen3:4b重放 `i want to sell a car`、`the brand is perodua, axia` 两轮，分别26.48秒、19.06秒，全部通过。第二轮实际记录brand=perodua、model=axia，保留variant未知，显示一次缺少覆盖说明和三个带例子的追问。工具／提示／表单的代码与最终287项离线测试及这两轮重放的来源指纹一致。临时重放脚本最初遗漏Windows子进程入口保护，已中止该脚本并修正后使用新文件保存最终成功记录；这属于验证脚本修正，应用代码不依赖它。原记录继续留在本机 `team_results/`。

表单所有Sell／Negotiation／Trade-In字段的示例现已**直接显示在字段下方**，而不是只放在帮助按钮里。金额表单明确只输入金额数字，字段已指定MYR；里程表单明确只输入读数数字，再选下方单位；预计天数／小时也只输入数字。聊天仍要求金额有RM／MYR、里程有km／m／miles，因此分别给适合聊天和表单的提示。没有将示例设成默认值。

三个咨询页面的Agent追问现在会在问题后附上英文例子。示例由 `question_examples.py` 根据该Controller实际读取的车辆资料生成，不额外调用Ollama，也不会写入用户Frame。

刚开始Sell时显示：

```text
What is the vehicle brand? (e.g. Perodua, Toyota)
What is the vehicle model? (e.g. Alza [Perodua], Avanza [Toyota])
What is the exact vehicle variant? (e.g. 1.5 SE [Perodua Alza], 1.5 S [Toyota Avanza])
```

确认Toyota／Alphard后，优先从Toyota Alphard记录选版本示例；确认具体版本后，优先取该版本的制造年份。品牌、车型、版本、年份及变速箱来自资料库，不代表该车辆当前有货或一定可估价。没有完全匹配时，按上面的后续修复使用明确标注的其他车辆格式例子；实际查询／估价仍保留用户原来的车型。

里程、车况、事故／水灾、角色、金额、费用、贷款、时间和偏好也有回答格式提示。这些属于用户自己的资料：金额示例会明确写format only／format examples，不当作数据库已确认的车商报价、实际费用或用户预算；未知费用不填零。65000 km只是里程格式例子，必须换成实际读数。车况／损伤文字是可接受的自述示例，不代表数据库证实了这辆车的状况。

辅助表单的品牌／车型／版本文本框加入同一来源的placeholder（输入框提示字），金额／年份／里程／时间数值框也有可直接照格式输入的提示；所有字段下方和帮助按钮均可看见对应示例。表单仍保持空白，示例不会被当作已填值或自动提交。只有用户实际发送／提交的资料才进入既有来源文字校验、Frame、工具执行和结果检查。

更新后，在原来运行Streamlit的PowerShell按Ctrl+C，再运行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

刷新网页，输入 `/reset`，从新咨询开始，才能看到新产生的问题。可分别选择Sell、Negotiation、Trade-In，输入 `I want to sell a car.`、`I want to negotiate.`、`I want to compare trade-in with private sale.`。旧聊天是先前保存的文字，不会重新生成。

初版283项通过、23.491秒的历史记录保留在 `docs/question-examples-acceptance-20261101.json`。Axia修复后，**287项离线测试通过，26.942秒**，其中13项是示例专项检查；新增缺少Axia、只放宽显示示例、不虚构估价、数字placeholder可被实际表单解析，以及三页直接可见提示检查。最新结果见 `docs/question-examples-axia-acceptance-20261101.json`。初版测试曾误读Markdown组件，实际聊天使用text组件，更正测试后通过；原失败记录保留在本机忽略Git的 `team_results/`。离线AppTest和真实Ollama重放分别记录，不将它们称为新的真实浏览器操作。
