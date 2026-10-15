# 第 2 课：VehicleFrame 与硬约束筛选

本阶段已接到 main.py；加上 `--match` 即可运行。应用代码、输入及输出保持英文，教学说明使用中文。无需安装新依赖。

## 1. 与上一阶段的关系

上次：用户的话 → BuyerProfileFrame → Python 规则推导买家需求。

现在：上述需求 + VehicleFrame 车辆资料 → 检查预算、座位、排除品牌 → 匹配列表及每条不匹配原因。

这是 **Hard Constraint Filtering**。Weighted Scoring、真实市场数据、价格估计、议价和多轮 Agent 仍是后续阶段。

## 2. VehicleFrame 是什么

BuyerProfileFrame 存买家的要求；VehicleFrame 存每辆车的 facts。

| slot | 含义 | 教学示例 |
|---|---|---|
| vehicle_id | 唯一编号 | DEMO001 |
| brand | 品牌 | Perodua |
| model | 车型名称 | Teaching MPV A |
| year | 年款 | 2020 |
| price_myr | 数据记录中的价格 | 45000 |
| seats | 座位数 | 7 |
| currency | 币种，默认 MYR | MYR |
| source_kind | 来源类型 | synthetic_demo |
| source_reference | 来源说明 | Hand-authored fixture |
| observed_on | 记录日期；对 synthetic data 是构造日期 | 2026-10-14 |

`PassengerCarFrame` 继承 `VehicleFrame` 的共同 slots，并增加 passenger_car 与 4 wheels defaults。这展示 **class frame / inheritance**；每条 JSON 数据加载后成为 instance。

Pydantic 检查正数价格、整数座位、唯一 ID、有效字段及日期。未知价格/座位用 null，不能默认免费或五座。加载整份数据时发现非法数据会报错，不默默跳过。

## 3. 教学数据的边界

data/vehicles_demo.json 包含 8 条人工构造的测试资料。品牌名称只用于练习品牌筛选；车型、价格、年份和座位组合均为虚构，**不能用作真实购车建议、市场价格或车厂规格**。其中 2 条故意缺少价格或座位，验证不确定资料的处理。

| ID | 品牌 | 教学名称 | MYR | 座位 |
|---|---|---|---:|---:|
| DEMO001 | Perodua | Teaching MPV A | 45000 | 7 |
| DEMO002 | Toyota | Teaching MPV B | 58000 | 7 |
| DEMO003 | Honda | Teaching MPV C | 72000 | 7 |
| DEMO004 | Proton | Teaching Sedan D | 42000 | 5 |
| DEMO005 | Toyota | Teaching Sedan E | 55000 | 5 |
| DEMO006 | Nissan | Teaching MPV F | 60000 | 7 |
| DEMO007 | Proton | Teaching Unknown Price G | 未知 | 7 |
| DEMO008 | Honda | Teaching Unknown Seats H | 50000 | 未知 |

## 4. 筛选规则

车辆必须同时满足：price ≤ budget；seats ≥ minimum required；brand 不在 excluded_brands。英文品牌比较忽略大小写和首尾空白。

价格或座位未知，无法证明满足条件，因此不进入 matches，并记录原因。多个条件不满足时列出全部理由。

preferred_brands 是 **Soft Preference**：目前只标记 preferred_brand_match，不会把其他品牌全部删除。若要“只能 Toyota”，以后需单独定义明确 hard brand requirement，不能混淆偏好与强制条件。

matches 目前按价格升序、再按 ID 展示；这是固定展示顺序，**不是 lifestyle ranking**。没有 fuel feature/scoring，因此想省油的用户暂时不能得到已经验证的省油推荐。

## 5. 第一次运行：不调用 Ollama

打开 PowerShell，进入项目：

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
```

运行上一课家庭资料并筛选：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_buyer.json --match
```

预期：status=matches_found、checked_count=8、matched_count=3；matches 中有 DEMO001、DEMO002、DEMO006。

再运行排除 Toyota 的人工资料：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/family_no_toyota.json --match
```

预期：matched_count=2，留下 DEMO001 和 DEMO006。DEMO002 被 FILTER_EXCLUDED_BRAND 排除；DEMO003 超预算；五座记录不足六座；未知价格/座位各有独立原因。MYR60000 刚好等于预算，允许保留。

`--fixture` 使用固定已填写资料，适合先检查逻辑；`--match` 打开这一阶段的新功能。不加 --match 时保留上一课的行为。

## 6. 第二次运行：英文自然语言 + Ollama

保持 Ollama 运行，在同一 PowerShell 窗口执行：

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM60000, six-person family, mainly city commuting, save fuel, do not want Toyota." --match
```

先检查 buyer_reasoning.extracted_profile 是否提取正确，再检查 matches。理想结果同上：DEMO001、DEMO006。如果模型错误提取需求，即使筛选逻辑正确也会影响结果；这是把 extraction 与 deterministic tools 分开测试的原因。

测试资料不足：

```powershell
.\.venv\Scripts\python.exe main.py --text "I want a fuel-efficient car." --match
```

预期 status=needs_clarification，显示英文问题，checked_count=0，matches=[]。

测试低预算：

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM30000, at least seven seats, mainly family travel." --match
```

预期 status=no_matches。系统不会自行把预算提高。

## 7. 如何看输出

| 字段 | 作用 |
|---|---|
| status | matches_found / no_matches / needs_clarification |
| buyer_reasoning | 上一阶段的 facts、rules 与追问 |
| dataset_notice | 提醒虚构资料的边界 |
| constraints | 本次明确执行的硬条件 |
| matches | 满足所有硬条件的记录 |
| rejected | 未通过记录，以及每项 rule ID / reason |
| checked_count | 实际检查数量 |
| matched_count | 最终保留数量 |

新增文件：vehicle_frame.py 定义 Frames；matching.py 执行筛选；data/vehicles_demo.json 是数据；test_matching.py 验证逻辑。

## 8. 验证与下一步

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_profile test_matching
```

共有 13 项 tests，包括 5 项旧规则测试与 8 项新增匹配测试。它们验证逻辑与边界，不证明真实市场推荐准确。

后续学习：确定真实数据来源并记录 provenance；增加需要的 fuel/space features；在 hard filtering 后实现 Weighted Scoring 和可解释排序；最后纳入 Agent 工具调用循环。
