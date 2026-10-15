# 第 3 课：真实来源数据与 Lifestyle Scoring

更新：2026-10-15。无需安装新依赖。应用、Prompt、测试输入和结果仍使用英文。

## 1. 这次完成什么

- 新增 `data/vehicles_real.json`：17 条人工核对的公共挂牌快照，保留 URL、日期、variant、里程范围、价格性质、可用状态和未知值。
- 新增 `scoring.py`：先执行已有 hard filtering，再进行透明加权评分。
- 新增 `--rank`：默认使用真实来源快照；原 `--match` 默认仍使用教学 fixtures，旧命令继续可用。
- 新增 `space_priority`：明确偏好行李空间时提取为 high。它表示 boot/luggage，不把它冒称乘员腿部空间。
- 每条结果有权重、分项贡献、资料覆盖率、缺失字段及来源。

## 2. 数据的真实含义

17 行表示 17 个广告/库存记录，不表示 17 辆经过 VIN 核对的独立汽车，也不是 17 宗成交。

| 内容 | 数量/处理 |
|---|---|
| 型号覆盖 | Alza 8、Myvi 3、Bezza 4、Avanza 2 |
| 页面仍展示的挂牌快照 | 11；不保证此刻仍有货 |
| 明确售出 | 5，筛选排除 |
| 明确已预订 | 1，筛选排除 |
| 价格类型 | 17 条全部 asking price，含售出页面残留的旧挂牌价 |
| 有精确里程或里程范围 | 16；范围保持范围，不用中点伪装精确数值 |
| 有参考油耗/boot值 | 各10条，按匹配世代/variant附来源；实际在售候选仅其中8条有这些值 |
| 独立核验的 condition | 0；卖家广告中的 good condition 不当作客观车况标签 |

规格用 Perodua 官方型号页，价格/里程用 Carlist、Carsome 和 paultan.org classifieds 的具体详情页。Source receipts 保存在 `data/source_receipts.json`；不保留联系人、电话、车牌或广告全文。

已识别的质量边界：

- 4 条记录的 source update 距观察日期超过60天；页面缓存和最近检索都不能证明车源刚更新。
- 17 个 ID 和17个来源URL唯一，未发现相同选定字段组合，但没有 VIN，不能排除不同网站重复发布同一车。
- 2020 Alza 不套用新一代22 km/L，也不猜 boot litres。
- 新 Alza 的137 L是第三排立起；498 L需要放倒第三排，七人出行不能用后者打分。
- Bezza X 与 AV 的参考油耗不同，分别为21和22 km/L。
- 厂商宣传/测试油耗不是这辆旧车实测，也不是保证的城市油耗。
- 样本目前偏向 Perodua；Toyota 两条均不可用。不能把该小样本宣称为全马市场或充分估价数据集。

## 3. 筛选与评分的区别

Hard constraints 决定“能否进入候选”：price≤budget、seats≥required、非排除品牌、页面未明确售出/预订。

Soft preferences 决定“在候选中更适合哪些需求”：省油、行李空间、品牌偏好、城市紧凑程度。

高分不能救回违反硬约束的车。我们没有训练 scoring model；权重与anchors是公开的 heuristic design choices，需要在最终评估中检验。

## 4. 权重如何产生

初始 raw weights：budget=1；城市通勤的compactness=1；有preferred brand时brand=2；fuel high/medium/low分别4/2/0.5，未指定为0；luggage high/medium/low分别3/2/0.5，未指定但family_travel时默认2并视为设计假设。

将启用的权重除以总和，得到归一化权重，合计1。

示例：city commute + high fuel priority + high luggage priority + no brand preference：

| 部分 | raw weight | normalized weight |
|---|---:|---:|
| budget | 1 | 11.11% |
| fuel | 4 | 44.44% |
| luggage | 3 | 33.33% |
| city_compactness | 1 | 11.11% |

## 5. 各项评分公式

先把每项变成0–1，再算 `100 × Σ(weight × normalized_value)`。

| 项目 | 归一化公式 | 含义与边界 |
|---|---|---|
| budget | 1 − price/budget | 同预算下保留较多预算的车更高；不是整体拥有成本 |
| fuel | clip((km/L−10)/15,0,1) | 固定10–25 anchors；只在同一claim basis中启用，不保证真实油耗 |
| luggage | clip(boot_litres/600,0,1) | 固定600 L anchor，必须all_seats_up；不是腿部空间 |
| brand | 符合preferred brand=1，否则0 | 未偏好任何品牌则不启用；不会替代排除条件 |
| city_compactness | clip((5000−length_mm)/1500,0,1) | 3500–5000 mm固定anchors；仅为长度proxy，不等同实际停车难度 |

clip表示把超范围数值限制在0–1。这些anchors不是标准法规或实证最优值，都会写入结果。

不同候选油耗口径同时出现（如MDC与eco-driving）时，对这次整个候选集合关闭fuel criterion并说明原因；不能直接把不同口径数字当作真实可比的油耗排名。即便同属eco-driving，也只是厂商参考claim，具体测试条件不保证完全相同。

## 6. 缺失资料怎样处理

每辆车使用相同的一组权重，不能因为缺少feature就把其他feature重新放大。

未知项对 `score`（有证据支持的下界）贡献0，同时减少weighted_data_coverage_percent，并增大score_upper_bound。0贡献并不说明这辆车实际很差；它表示没有证据支持该部分得分。按下界排序是保守的证据排名，不是“绝对最好”或统计置信区间。

例如旧Alza没有核实油耗/boot，结果会标出missing features和低coverage，不能宣称它实际比新车更费油或更小。

## 7. 运行：先固定资料，不需要 Ollama

```powershell
cd "C:\Users\Ryan\.codex\.chatgpt-projects\g-p-6a995ecd270c8191911fcbcf58759bdf\vehicle-agent"
.\.venv\Scripts\python.exe main.py --fixture examples/city_buyer.json --rank
```

输入：budget50000、five seats、city commute、high fuel/space priorities。按当前冻结快照和v1权重，9条通过硬约束；前三个ID预期为 PT_K4EDNMNYPG、PT_7PRLM3GLPK、CS_C606800。这是项目算法对当前样本的输出，不是购车推荐或市场结论。

查看新字段：
- scoring_weights：采用哪些偏好，权重是多少。
- scoring_anchors：计算公式与参数。
- score_breakdown：每个criterion的value/weight/weighted_points/source。
- score：按证据支持的下界得分，越高排名越前。
- score_upper_bound：若未知项全得到满分的上界，不是预测。
- weighted_data_coverage_percent / missing_scoring_features：资料覆盖和未知项。
- top_vehicle_ids：前三条。

## 8. 运行：Ollama英文输入

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM50000, at least five seats, mainly city commuting. Fuel economy and a spacious boot are high priorities." --rank
```

再试六人家庭：

```powershell
.\.venv\Scripts\python.exe main.py --text "Budget RM60000, six-person family, mainly city commuting. Save fuel and do not want Toyota." --rank
```

第二个案例当前只留下三条2020 Alza，均无核实油耗。scoring_notes必须说明无法支持fuel比较，不能输出“这三辆很省油”。

不加--rank仍保持旧行为。--rank可配合--vehicles自选数据文件；教学fixtures和真实来源快照应该分开使用。

## 9. 检查与复现

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_profile test_matching test_scoring
.\.venv\Scripts\python.exe check_data_quality.py
```

28项unit tests覆盖旧功能、评分偏好改变排序、约束不被突破、missing、口径冲突、折叠座椅空间、加总、排序稳定性与来源字段。

`check_data_quality.py` 可复现质量报告，结果在data/quality_report.json。`data/build_curated_snapshot.py`可重建本次人工整理快照；它不是scraper，执行不会刷新网站，真正更新数据仍需重新核对来源。

后续：在此基础上制作估价与议价工具。不要等到所有细节完美才写报告；本阶段已有Frames、rules、missingness、ranking trade-offs的可展示证据。
