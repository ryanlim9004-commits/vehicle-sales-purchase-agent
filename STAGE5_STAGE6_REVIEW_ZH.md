# 阶段 5 与阶段 6 验收记录

日期：2026-10-15。本文件使用用户的阶段编号：阶段5=真实数据与Lifestyle Scoring；阶段6=Rule-Based Valuation。LESSON3/LESSON4是教学课次，不是同一套阶段编号。

## 验收结论

阶段5的约定基础范围已完成，并在本次修复边界后通过验收。阶段6的估价基础版也已经实现，本次一并复核通过。下一个尚未实现的业务模块是Negotiation/Trade-In，之后才是完整Agent Controller、多轮状态与UI。

“完成”指当前公开、有限的教学原型范围，不代表数据覆盖充分、模型市场准确率已验证，或完整Agent已经完成。

## 阶段5逐项核对

| 要求 | 实际实现／结果 |
|---|---|
| brand/model/variant/year | 17条来源快照均有身份字段；制造年／标题依据的不确定性保留于notes |
| price/seats/mileage | 全部有asking price；3条座位未知；16条有精确里程或完整范围 |
| 可核实fuel/space features | 17条中各10条有fuel和boot，11条可用挂牌中各8条有；旧Alza不套新车型参数 |
| source/date/unit/unknown | listing、fuel与specs来源分开；MYR/km/km per litre/litres/mm；缺失保留null；新增DATA_DICTIONARY |
| asking vs transaction | 全部17条是asking；售出页面仍不是成交价；本次补上买家筛选对transaction记录的明确排除 |
| 每个车型的可比样本 | 新质量报告按精确identity和90天窗口分组；只有2020 Alza 1.5 SE Automatic达到minimum3 |
| 硬筛选在前 | 预算、座位、排除品牌、asking listing和snapshot availability合格后才评分 |
| 偏好改变权重／排序 | fuel和brand偏好均有测试；真实city案例Top3不是价格排序 |
| 公开公式／解释 | scoring_weights、scoring_anchors、score_breakdown、source_reference、coverage、missing features |
| 未知／不可比数据 | 缺失项显示上下界；不同fuel_basis时整体关闭fuel打分并解释 |

`--match`仍是硬筛选后的价格/ID展示；`--rank`才会进行Lifestyle Scoring。旧句“当前只是按价格和ID展示”不再适用于`--rank`。

## 本次发现与修复

1. **中等：成交记录可能进入买家推荐。** 人工构造transaction但availability为listed_snapshot时，旧筛选会接受。已增加FILTER_PRICE_BASIS。
2. **中等：里程字段可能矛盾。** exact reading可落在另附范围之外；现在Frame拒绝这种数据。
3. **中等：规格来源校验不足。** 真实车源的fuel/size来源原可填任意非空文字，甚至使用synthetic fuel basis。现在要求所用真实feature附HTTPS来源，并排除synthetic basis。HTTPS只检验格式，不证明内容真实。
4. **中等：来源核对自动化缺漏。** 过去只覆盖URL集合；现在逐ID、URL和12个记录字段检查receipt覆盖与一致性。现有17条无差异；这不等于独立核验原广告事实。
5. **低：制造年份容许未来一年。** 阶段6及VehicleFrame原本容许next-year值；现在制造年份不能晚于观察／估价年份，卖家输入矛盾时追问。
6. **文档缺漏。** 补齐data dictionary、估价可比组覆盖和最新进度，避免把旧教学课次当当前阶段状态。

## 数据范围与未解决事项

资料单元是广告／库存ID，不是已核对VIN的独立车辆。17个ID和URL唯一、receipt一致；未发现所选字段完全重复组合，但跨网站同车重复风险仍存在。

11条listed_snapshot、5条sold、1条reserved。4条来源更新距记录日期超过60天，7条更新日期未知。买家模式会标注快照，不能保证实时库存；估价模式按已知更新日期及90天规则进一步排除。

真实condition标签为0条，transaction价格为0条。数据偏向Perodua，Toyota两条均不可用于推荐。没有足够证据时不补值、不放宽条件、不猜估价。这些限制需要写入报告，后续增加数据可改善覆盖，但不阻止当前有边界的功能进入集成。

long_distance可被记录为usage，但当前没有独立核实的长途舒适性、安全性或可靠性评分feature；不能把当前分数解释成全面长途适用性测评。排名仍为hand-authored heuristic，尚无独立专家／用户holdout relevance验证。

本次在线选择性复核了三个Perodua官方型号页和一条旧Alza挂牌，不声称重新刷新全部17条库存：

- [Alza官方规格](https://www.perodua.com.my/our-models/mpv/new-alza)：137L与第三排放倒498L分开，长度4425mm和22km/L参考claim仍可找到。
- [Myvi官方规格](https://www.perodua.com.my/our-models/hatchback/myvi)：对应1.5 D-CVT参考21.1km/L、277L、3895mm。
- [Bezza官方规格](https://www.perodua.com.my/our-models/sedan/bezza)：1.3 X参考21km/L、AV参考22km/L、508L、4170mm。
- [2020 Alza挂牌](https://www.carlist.my/used-cars/2020-perodua-alza-1-5-se-mpv-warranty-free-super-good-condition-clean-interior-car-paint-glossy-engine-smooth/18923892)：页面保留MYR35888、65–70K km、manufacture2020和7seats；网页读取可能来自缓存，不能据此保证有货。

## 阶段6的实际能力

- `SellerVehicleFrame`及英文提取已经存在，含原文单位核对。
- `valuation.py`按相同brand/model/variant/year/transmission、有效来源、已知近期更新和唯一ID/URL选择至少3条挂牌。
- 默认`reference_only`，示例median44800 MYR、observed range35888–45000。
- 缺字段返回needs_clarification；不足3条返回insufficient_evidence；报告重大事故／泡水返回inspection_required。
- 默认无已校准的里程／车况调整。`--illustrative-adjustments`是opt-in教学假设，market_validated=false，示例43092 MYR。
- historical trends、transaction-price calibration、market accuracy仍未实现。不可在报告中宣传为已验证的完整fair-market appraisal。

## 验证与复现

完整回归67项测试方法通过（部分含多个subTests）。本次新增Stage5AuditTests共7项，Valuation新增1项未来年份检查。

`stage5-stage6-acceptance.json`保存10个验收案例，全部通过：8个人工确定输入→工具场景，以及2个真实qwen3:4b英文提取→工具场景。真实案例分别为buyer ranking和seller 50000m→50km→asking reference。它们不是未见数据市场accuracy评估。

```powershell
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit
.\.venv\Scripts\python.exe check_data_quality.py
.\.venv\Scripts\python.exe evaluate_stage5_stage6.py --live
```

用户运行入口：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/city_buyer.json --rank
.\.venv\Scripts\python.exe main.py --fixture examples/seller_alza.json --value --as-of 2026-10-15
```

第一条预期Top3为PT_K4EDNMNYPG、PT_7PRLM3GLPK、CS_C606800；第二条预期reference_only、comparable_count3、median44800。`--as-of`用于复现日期，不让旧快照成为最新报价。

本轮无需安装软件。新代码与验收文件保存在本地工作区；GitHub仍为上次初始提交，本轮未自动commit/push。
