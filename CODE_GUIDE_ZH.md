# 全项目代码与命令阅读说明

更新：2026-10-16。应用与代码注释使用英文，本文件用中文辅导。这里的comments是给人阅读的解释；commands是PowerShell执行的指令，两者不同。

## 1. 这次补充的内容

34个Python文件均补充模块职责说明，275个类／函数均有用途注释，关键算法另有内部步骤解释，包括生产规则、单位换算、Weighted Scoring、估价、议价、Trade-In和Agent Loop。测试中的注释解释“期望什么行为”，而不是假装测试本身训练了模型。

只增加普通`#`注释，没有改Prompt、schema字段、权重、公式、数据或历史验收结果。特别是Pydantic类没有新增class docstring，避免影响模型JSON schema中的description。JSON格式不支持`#`或`//`注释，所以用独立的[JSON阅读说明](docs/JSON_FILES_GUIDE_ZH.md)解释数据、fixtures与结果文件。配置文件则直接补上其支持的`#`注释。

## 2. 先看懂最小流程

建议按下面顺序阅读，不要第一天就逐行研究Controller：

1. `examples/family_buyer.json`：看一份已经填好的买家资料。
2. `buyer_profile.py`：理解Frame、slots、unknown和BUY规则。
3. `vehicle_frame.py` → `matching.py`：理解车辆资料与必须满足的条件。
4. `scoring.py`：理解通过硬筛选后怎样计算偏好分。
5. `seller_profile.py` → `valuation.py`：理解卖家输入与挂牌参考。
6. `consultation_frames.py` → `negotiation.py` → `trade_in.py`：理解总预算、净底价与补差。
7. `agent_state.py` → `agent_grounding.py` → `agent_tools.py` → `agent_controller.py` → `agent_cli.py`：理解多轮记忆和实际工具调用。
8. 对应的`test_*.py`与`evaluate_*.py`：看系统怎样被验证。

你以前运行的`main.py`一次执行一个明确动作；新的`agent_cli.py`在同一会话里接收多次输入、更新记忆并协调工具。

## 3. 常见Python写法

| 写法 | 在本项目中的意思 |
|---|---|
| `# explanation` | comment；Python不执行这段解释 |
| `class ... (BaseModel)` | Pydantic Frame，定义允许的slots、类型、默认值和范围 |
| `float \| None` | 可为数值或未知；未知不等于0 |
| `Field(default=None, gt=0)` | 默认未知；一旦提供必须大于0 |
| `default_factory=list` | 每个对象建立自己的空列表，避免不同会话共享列表 |
| `Literal[...]` | 只允许列出的固定标签，例如Automatic或Manual |
| `strict=True`／`extra='forbid'` | 不随意转换类型、不接受未定义字段 |
| `model_validate_json(...)` | 读取JSON并检查是否符合Frame |
| `model_dump()` | 将Frame变成Python dictionary，不表示保存到硬盘 |
| `model_dump(mode='json')` | 生成适合JSON输出的值，例如把日期转为字符串 |
| `@field_validator`／`@model_validator` | 分别检查单个字段、整份资料之间的一致性 |
| `def ...`／`return` | 定义函数／返回结果给调用者 |
| `if`／`elif`／`else` | 有顺序的条件分支；手写Decision Tree的基础 |
| `for` | 对每辆车、每条规则或每个案例重复处理 |
| `dict`／`list`／`set` | 命名键值资料／有序项目／不重复项目集合 |
| `Decimal(str(value))` | 用十进制金额计算，减少binary float误差 |
| `try`／`except`／`finally` | 尝试执行、处理错误、无论成功失败都清理资源 |
| `if __name__ == '__main__'` | 只在直接运行该文件时启动入口；Windows子进程尤其需要此保护 |

代码中的regex只识别已支持的英文表达；comment说明用途不等于支持所有英文表达。看到`PROMPT`、`SENSE_PROMPT`、`PLAN_PROMPT`时，那是实际发送给模型的字符串，不是普通注释。

## 4. 业务与Agent文件逐一对应

| 文件 | 输入 → 输出／主要职责 |
|---|---|
| `main.py` | CLI flags + text/fixture → 单次工具JSON；负责选择明确动作 |
| `agent_cli.py` | 连续英文输入 → 同一Controller的多轮回复；处理显示与可选session保存 |
| `buyer_profile.py` | BuyerProfileFrame → explicit/derived facts、BUY_01–04、缺失／矛盾问题 |
| `seller_profile.py` | 英文卖车资料 → SellerVehicleFrame；本地Ollama提取后检查原文 |
| `vehicle_frame.py` | 车辆JSON → VehicleFrame/PassengerCarFrame；验证资料与provenance |
| `matching.py` | 买家事实 + 车辆 → matches/rejected；只有硬筛选，没有生活方式评分 |
| `scoring.py` | 已筛选结果 + 偏好 → score、breakdown、coverage、Top3 |
| `valuation.py` | 卖家身份／事实 + 来源快照 → asking reference或不足／追问／inspection状态 |
| `consultation_frames.py` | 买卖方限额、四个独立quote对象 → 有类型、金额精度明确的输入 |
| `negotiation.py` | 对方报价 + 自己限额 + 可选实际reference → 手写树的action/counter/理由 |
| `trade_in.py` | 两条路径的完整报价／费用／结清额 → 净收入、补差与条件性建议 |
| `input_grounding.py` | 原始英文 + 单轮提取结果 → 经核对的单位、币种、年份与history |
| `agent_state.py` | 已确认facts + task信息 → typed memory、可更新slot路径、limits与trace |
| `agent_grounding.py` | 当前消息 + model patch + memory → 经原文核对后的记忆修改 |
| `agent_tools.py` | allowlisted request + checked memory → 实际tool observation与独立checks |
| `agent_controller.py` | 一轮英文输入 → Sense/Plan/Act/Observe/Check/Ask/Finish；限制重试与时间 |
| `check_data_quality.py` | 本地车辆资料 + receipts → 缺失率、来源一致性、可比组覆盖 |
| `data/build_curated_snapshot.py` | 文件内保存的人工核对事实 → 重建车辆JSON与receipts；不联网抓取 |

## 5. 需要能向lecturer解释的算法

**Frames + Production Rules + Forward Chaining。** `BuyerProfileFrame`保存明确输入；`reason_about_profile`复制为working facts。BUY_01在没有明确座位、且未说明不是全家同行时，从家庭人数推导座位；BUY_02再从座位推导车辆minimum seats。BUY_03识别城市／省油profile，BUY_04记录并非全家同行。`fired_rules`显示每条推理依据。

**先硬筛选，再Weighted Scoring。** 预算、座位、排除品牌是门槛。通过后，依据用户偏好选择raw weights，统一归一化：

```text
weight_i = raw_weight_i / sum(active raw weights)
weighted_points_i = 100 * weight_i * normalized_feature_i
score = sum(weighted_points_i)
```

例如fuel raw weight为4、全部raw weights之和为9，则weight为4/9。若fuel normalized_value为0.8，贡献为`100 × 4/9 × 0.8 = 35.5556`。数据未知时只不给supported points，同时显示coverage与可能上界；不能给这辆车单独重新分配权重。权重是公开heuristic，不是训练得到的ML参数。

**Rule-Based Valuation。** 筛选同brand/model/variant/manufacturing year/transmission、符合来源与日期要求的挂牌，至少三条后算median和observed min/max。默认不按车况／里程猜调整因子。`identity_reference_only`只查车型挂牌背景；不能因此说已了解旧车真实车况。事故／泡水先inspection。

**Handwritten Decision Tree + Calculator。** 议价分别约束买方总支出与卖方净收入：

```text
Buyer: counter + fees <= total budget
Seller: counter - fees - old loan settlement >= minimum net

Net disposal proceeds = gross offer - disposal fees - old loan settlement
Cash difference = replacement price + replacement fees - net disposal proceeds
```

Trade-In与private sale各有自己的replacement price／fees和gross offer／disposal fees。未知费用不填0；正cash difference需补钱，负数为现金盈余。Asking reference只作背景，不填补实际收车报价。

**Agent Loop。** 读取新消息与checked memory →模型提出fact patch→原文校验与合并→模型请求工具→Python检查并执行→把真实observation返回给planner→独立check_result→追问、继续或finish。模型只说“已完成”不能代替执行；未通过检查不能finish。Conversation memory不是训练模型。

## 6. 测试与评估脚本

| 文件 | 验证什么／是否调用真实模型 |
|---|---|
| `test_profile.py` | 买家Frame／规则／矛盾；不调用 |
| `test_matching.py` | 硬条件、unknown、继承、重复ID；不调用 |
| `test_scoring.py` | 偏好、公式、missing policy、来源规格；不调用 |
| `test_valuation.py` | 可比选择、拒绝状态、reference和教学调整；不调用 |
| `test_input_grounding.py` | 单位、MYR、月供、年份／history，mock错误模型输出；不调用 |
| `test_stage5_audit.py` | 来源、receipt、里程范围、日期等已发现bug；不调用 |
| `test_negotiation.py` | 买卖方分支、Trade-In公式及真实CLI subprocess；不调用 |
| `test_agent.py` | 用ScriptedBackend控制模型回复，但运行真实业务tools；不调用真实Ollama |
| `evaluate_extraction.py` | 四个英文buyer extraction案例；调用 |
| `evaluate_ranking.py` | 两个英文extraction→ranking案例；调用 |
| `evaluate_valuation.py` | 一个extraction→valuation案例；调用 |
| `audit_input_cases.py` | 九个单位／币种／history边界输入，保存原始结果；调用 |
| `evaluate_input_fix.py` | 三个live regressions + 九个已保存audit字段检查；部分调用 |
| `evaluate_stage5_stage6.py` | 默认八个固定案例；只有`--live`再调用两个模型案例 |
| `evaluate_negotiation.py` | 五个实际CLI + 三个direct tool案例；不调用模型 |
| `evaluate_agent.py` | 四种目标、共八轮（含reset）的完整Agent验收；其余七轮调用 |

`assertEqual`是比较实际与预期；`assertRaises`检查应该拒绝的错误。`patch`／mock用来控制测试环境，不代表真实模型已达到同样语言准确率。134项unit tests与少量开发验收不是独立holdout或市场估价accuracy。

## 7. 其他文件在哪里解释

- [运行命令逐条说明](COMMANDS_ZH.md)：包括启动、flags、测试及会重写结果的开发脚本。
- [JSON、fixtures和历史结果](docs/JSON_FILES_GUIDE_ZH.md)：说明字段与保存证据的意义。
- `requirements.txt`允许依赖版本范围；`requirements-lock.txt`记录复现版本。
- `.gitignore`排除venv、cache、session和凭证；`.gitattributes`统一文本换行。
- `README.md`是英文项目入口；`README_ZH.md`与`LESSON2–4`保留逐课教学。
- `STAGE*_RESULTS.md`及相关review/guide保存各阶段的实现与验收边界；历史日期的数量不自动代表当前总量。
- `ASSIGNMENT_ROADMAP_ZH.md`和`ACCELERATED_PLAN_ZH.md`说明当前进度与交付安排。
- `docs/PROPOSAL_EN.md`／`docs/BUILD_PLAN_ZH.md`保留原始方案，不取代实际实现状态。
- 原课件、正式guide与完整context在repository之外作为参考保存；本轮没有修改`sources/`。
