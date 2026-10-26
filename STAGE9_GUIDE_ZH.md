# 阶段9：英文Streamlit浏览器界面

更新：2026-10-26。Streamlit 1.66.0已安装在项目现有`.venv`；本机用户不必重新安装。应用、字段、错误提示和代码comments使用英文，教学说明使用中文。

## 1. Streamlit负责什么

Streamlit把Python程序呈现为网页，提供聊天框、表单和表格。它是本项目的UI，Ollama仍在本机负责模型推理，Python Controller仍负责记忆、工具执行和结果检查。浏览器操作不等于部署到云端。

第一版采用英文聊天为主、辅助表单、每个浏览器tab独立临时记忆；资料基准为15 Oct 2026，不加入当天日期切换。26Oct按用户设计要求移除整块Saved snapshot demo侧栏，包括Reset、Stop、Download按钮及其说明，同时移除主标题下两行技术／快照文字。结果和证据仍保留资料本身的来源与日期。第一版原始决定记录见docs/STAGE9_DECISIONS.md，界面操作以本次更新为准。

## 2. 怎样启动

保持Ollama运行，在PowerShell输入：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

然后在浏览器打开：

```text
http://127.0.0.1:8501
```

PowerShell负责维持服务，保持该窗口运行。结束时在该terminal按Ctrl+C；服务停止后浏览器地址就无法继续处理咨询。当前Codex启动的验证服务若仍在运行，可直接打开上述地址，不要重复占用相同端口。

其他组员首次配置，才需要建立venv、安装锁定依赖和下载模型；见README.md。当前机器已经完成安装。UI只绑定127.0.0.1，不是供互联网多人使用的部署。

## 3. 页面怎样使用

- **Consultation area**：Buy、Sell、Negotiation、Trade-In。浏览分类本身不执行工具；提交资料才开始／切换任务。英文消息明确提出另一个目标时，Controller也可以切换目标。
- **Consultation**：英文聊天、追问回答、条件修改和辅助表单。
- **Menu（三条杠）→ Results & comparison**：当前经独立检查的候选比较、估价或现金路径结果。
- **Menu → Evidence & checks**：facts、rules、tools／真实observations、checks和有限trace。
- **Menu → Vehicle research**：有来源的车型研究资料。查看后可按Back to consultation返回聊天。
- **View confirmed details**：侧栏按钮展开当前会话实际记住的资料，以易读的标签和数值显示；打开按钮不执行咨询。尚无资料时会提示先发送消息。
- **Message the Agent**：砖红色边框标出主要输入区，附英文示例。辅助表单默认收起，聊天不再固定在页面最底部。

界面在执行期间禁用重复提交。右侧 **Stop** 在计算时可用：取消当前模型请求，停止后续工具步骤，丢弃本轮未完成资料并保留之前已确认的需求。网页服务继续运行，停止后可发送新消息。没有计算时Stop为灰色。需要清空事实和聊天时发送 `/reset`；聊天命令 `/stop` 仍用于轮次之间停止。实际取消及其边界见[菜单与停止说明](STOP_MENU_20261026_ZH.md)。

## 4. 聊天和表单如何共用Agent

英文聊天仍由Ollama提取新facts；表单字段已经明确，因此不再请LLM重复提取。form_inputs.py会先在副本中验证，再生成带明确证据的TurnPatch。两条路径随后共用Controller中的原文grounding、memory merge、实际模型planner、Python tools及check_result。

这不等于让按钮直接绕过Agent计算。表单输入事件在trace标为explicit_form_fields；不会把它伪装成一次模型提取。模型提出的工具请求仍须由Python实际执行。

表单约定：

| 输入 | 意义 |
|---|---|
| 留空／Keep / not provided | 保留已确认值，本轮不更新这个字段 |
| Unknown | 明确把字段变成未知；brand／usage列表则清空 |
| 0 | 明确的已知零，仅允许在fee／settlement等支持零的字段 |
| 60000、60k、1million | 金额栏位已标MYR；支持数字及thousand／million简写，最多两位小数；不做外币兑换或接受科学记数法 |
| Driving use多选 | 选择City commuting／Family travel／Long-distance driving；非空替换、留空保留、Unknown单独清空，无需输入逗号 |
| Toyota, Honda | brand列表；本轮完整替换该列表，不是只追加 |

旧现金报价不会自动预填，避免修改车型时意外重新确认旧报价。已确认值在字段help和侧栏可查。只需填本轮想改的内容，不必重复所有资料。

## 5. 四类任务示例

### Buying

先在聊天输入：

```text
I want to buy a car. Save fuel.
```

系统追问后，打开Add or update details with a form，填budget=60000、household size=6、driving use=City commuting、excluded brands=Toyota；其他栏留空，提交。之前的fuel preference应保留。Results显示三条合格旧Alza，并说明该组缺可比fuel数据，不能据此声称省油。

随后输入`Change my budget to RM35000.`，应保留其他facts并返回no_matches。页面不会继续把旧候选作为当前结果。

### Selling

选择Sell，表单输入Perodua／Alza／1.5 SE／2020／Automatic，odometer=50000且unit=m，condition=fair。事故／泡水选No仅适用于用户明确确认的教学场景，不是系统默认值。

预期mileage为50km，asking reference median为RM44800。结果显示comparables、范围、来源、筛选规则及“No mileage/condition adjustment applied”。这个数值不是经过个性化市场校准的成交估价。

### Negotiation

选择Negotiation，填写同一旧Alza身份、role=buyer、other-party quote=46000、fees=1500、fees complete=Yes、buyer total budget=46000。Seller相关底价／贷款栏可以留空。

预期获取实际挂牌背景后，裸车counter不超过RM44500，明确总预算已经包括费用。所有报价仍属于咨询输入，程序不接受交易。

### Trade-In

输入两条完整路径：

| 字段 | Trade-in | Private sale |
|---|---:|---:|
| Replacement price | 65000 | 65000 |
| Replacement fees | 1000 | 1000 |
| Gross disposal offer | 35000 | 40000 |
| Disposal fees | 500 | 1000 |
| 每一组fees complete | Yes | Yes |

另外填old loan settlement=10000、available additional cash=50000、priority=net_cost。四个quote对象的fee completeness需分别确认。可选旧车identity用来取得网站asking背景；未知dealer offer不能由median填补。

预期trade-in补RM41500，private sale补RM37000。报价和时间标明user-provided；网站asking sources另列，不能说这些现金报价已经由dealer文件核实。

## 6. 保存、刷新与来源

本次设计已移除网页咨询记录下载按钮。需要保留网页测试证据时，手动保存输入／结果截图，并在测试表记录预期与实际结果。应用不自动保存聊天文件，也不读取本机历史session。此前导出按钮的验收属于旧版界面的历史记录。

刷新／关闭tab或重启server可能清空会话，符合第一版已确认范围。不同tab各有自己的Controller，不能把客户state放进全局cache。全局只共享一把本机推理锁；另一tab正在执行时，界面要求稍后重试，不许串用资料。

模型忙碌时，本次提交会保存在当前tab，尚未应用到facts。点击Retry saved submission才再次尝试；Discard saved submission丢弃并清空草稿。此时其他输入暂时禁用，避免旧草稿日后覆盖新条件。模型空闲不会自动执行草稿。

开发者修改被导入的Python模块后，若旧服务仍加载旧模块，应在启动服务的terminal按Ctrl+C，再执行上面的启动命令；重启会清空临时咨询，应先保存需要保留的输入和结果截图。

结果和证据保留各记录的来源与日期，首页不再显示原快照说明块。来源按钮打开原广告／规格网页；保存价格可能与后来网页不同。实时搜索需要另一套抓取、来源验证和数据更新流程，不能靠把日期改成今天实现。

## 7. 检查与后续

```powershell
.\.venv\Scripts\python.exe run_team_tests.py --tester YOUR_NAME
```

test_streamlit_ui使用控制过的模型回复验证状态与真实tools；真实浏览器／Ollama结果另存stage9-browser-*.json。具体数量、结果和限制见STAGE9_RESULTS.md。

下一步是更广的独立holdout／组员跨电脑复现、数据覆盖与assignment材料，具体验收见REMAINING_WORK_ZH.md，暂不自动扩大到实时抓取、市场校准、Vision或云端多用户服务。

官方技术依据：[Streamlit forms](https://docs.streamlit.io/develop/concepts/architecture/forms)、[Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)、[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)。
