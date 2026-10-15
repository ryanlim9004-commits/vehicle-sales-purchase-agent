# 阶段1–7全面核对与进入Agent阶段的依据

日期：2026-10-15。按用户聊天流程统一编号；LESSON文件的教学课次不是阶段编号。以下“完成”限于已同意的教学原型范围，不宣称市场可靠性、全部语言表达或整个assignment交付完成。

| 阶段 | 核对范围 | 当前结论与边界 |
|---|---|---|
| 1 需求／课程与方案 | 原课件、正式guide/rubric、lecturer adaptation、Frames/rules/scoring/valuation/tree路线 | 已整理到本地项目context与proposal；lecturer同意由用户确认。没有虚构新的官方Agent评分表 |
| 2 环境 | Python、venv、Pydantic、Ollama SDK、qwen3:4b | 已安装并实测；新Agent沿用这些依赖，无需LangChain、云API或训练模型 |
| 3 BuyerProfileFrame／推理 | NLU、schema、原文单位／币种、unknown、Forward Chaining、矛盾追问 | 已实现；新增household_travels_together，允许用户澄清“六人家庭但不是全家同行”，不篡改家庭人数 |
| 4 VehicleFrame／硬筛选 | inheritance、价格/座位/品牌、来源类型/availability、拒绝理由 | 已实现；transaction记录不作可购买挂牌；高评分不能救回违反硬条件的车 |
| 5 数据与Lifestyle Scoring | 17条来源快照、日期、单位、receipt、unknown、权重/公式/coverage | 已实现有限样本；不是实时搜索。缺fuel不猜值，不同比较口径关闭fuel；新增long-distance指标缺口提示 |
| 6 Rule-Based Valuation | 同identity近期comparables、minimum3、median/range、damage/不足/unknown | 已实现挂牌参考；默认未校准里程/车况。新增identity-only reference入口，让议价查询市场背景时无需捏造卖家里程或车况 |
| 7 Negotiation/Trade-In | 手写tree、总预算/净底价、完整费用、贷款结清、独立replacement packages、时间/投入 | 已实现。议价关联实际估价；Trade-In现在也可附旧车asking context，但仍要求显式gross offer，不将挂牌价伪装成收车报价 |

## 本轮需要修复／明确的缺口

1. 家庭出行假设此前能追问但不能真正记录“不全家同行”；新增BUY_04与用户澄清字段，单轮与多轮路径都能保持家庭人数并采用明确座位需求。
2. 原估价入口收集个人里程／车况，即使只计算同identity挂牌参考。现在保留原卖家流程，并增加identity_reference_only模式；不推测个人资料，不执行教学调整。
3. Trade-In原本只有用户报价比较。现在可以关联旧车asking reference作背景，并核对identity/date/算术；报价缺失时仍追问，不从reference推出trade-in offer或保证私售收入。
4. 长途用途缺专门comfort/reliability/safety feature，输出必须明确只按现有可支持criterion评分。
5. 阶段7的人工JSON入口仍保留；自然语言与记忆在阶段8独立入口接入，避免把单轮CLI冒称Agent。

## 不能写成已完成的部分

- 样本扩充、车型/品牌覆盖、跨网站VIN去重、实时库存更新仍未完成。目前17条asking ads，11条listed_snapshot，只有一个exact identity组达到当前minimum3的近期估价条件。
- 没有独立condition标签、transaction price labels、经过市场校准的里程/车况因子或historical trend模型。不能声称已经验证fair-market accuracy或保证最佳售价。
- 评分仍是设计者公开权重的heuristic；没有独立专家/用户holdout relevance结论。总分不表示预测准确率。
- 马力、drivetrain、油箱等是前一轮讨论的可选扩展，尚未加入，并非自动成为第一版已同意的硬性scope。
- 英文UI、系统级holdout评估、最终报告/视频/presentation/Q&A与成员贡献材料仍在后续阶段。

这些是明确的证据／后续交付边界。进入Agent整合不会把它们变成“已解决”。对于证据不足的情况，当前tools必须返回unknown、clarification或insufficient evidence。

## 议价／Trade-In到底参考什么价格

- 独立议价命令通过--valuation-seller调用实际valuation tool；Agent知道明确车型identity时会先调用get_price_reference。
- 独立Trade-In命令现在也可配--valuation-seller；Agent知道current_vehicle身份时同样取得asking context。
- 来源仍是本地保存的Carlist/Carsome/paultan classifieds等广告快照，不是运行时实时搜索，不是dealer出具的trade-in quote。
- Trade-In gross offer、private-sale price、replacement price、费用与时间分别来自用户明确输入/确认。模型与工具都不能把asking reference当作缺失的dealer cash offer。

手动验证新关联入口：

```powershell
.\.venv\Scripts\python.exe main.py --fixture examples/trade_in.json --trade-in --valuation-seller examples/seller_alza.json --as-of 2026-10-15
```

应同时看到asking_price_context的median44800与用户gross offer35000；补差仍为41500/37000。参考背景不会替换报价。

固定输入复核结果保存于stages1-7-tool-recheck.json和stage7-recheck.json；完整单元测试与真实模型验收数量以STAGE8_RESULTS.md为准。
