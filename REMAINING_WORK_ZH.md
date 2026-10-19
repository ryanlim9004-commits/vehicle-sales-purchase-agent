# 第一版复核与剩余交付清单

**2026-10-19交接更新：当前195项离线测试、新环境两轮真实模型和教程工具命令通过；详细剩余工作及本机检查范围见[交接结果](TEAM_HANDOFF_RESULTS.md)。组员从[手把手指南](TEAM_GUIDE_ZH.md)开始。以下17Oct／16Oct数量保留为历史记录，不代替本次结果。回归、资料覆盖、组员独立评估与跨电脑实测、最终作业材料仍待完成。**

**2026-10-17更新：此文件保留第一版交付清单；2.0以V2_RESULTS.md和V2_GUIDE_ZH.md为准。当前184项离线测试通过、最终2轮真实Ollama V2验收通过。优先补充可用价格资料和适用评论，之后才训练／启用回归；独立评估、跨电脑复现与报告／视频仍待完成。可靠性参考机制已实现，但真实资料尚不够给数值。多年趋势／品牌折旧、车况／损伤扣价、真实成交率提升证明、全部照片功能已取消，不再列为必做。**

状态日期：2026-10-16。阶段1–9已实现当前获同意的教学原型范围；整个assignment尚未全部交付。下列待办没有因为UI完成而自动变成已完成。

## 已完成及本次修复

| 范围 | 实现／证据 | 仍需诚实说明的边界 |
|---|---|---|
| 需求与AI设计 | Frames、Production Rules、Forward Chaining、Weighted Scoring、Rule-Based Valuation、手写Decision Tree、Agent Loop | lecturer批准Agent方案由用户确认；原Chatbot guide仍是原文，没有伪造替代rubric |
| 数据／买车 | 保存来源、日期、单位、unknown；硬筛选先于评分；可解释候选比较 | 17条挂牌快照中11条listed；非实时库存，非专家认可的推荐准确率 |
| 卖车 | 同identity近期comparables、minimum3、挂牌中位数／范围、损伤或证据不足处理 | 仅一个identity组满足minimum3；默认无市场校准的里程／车况调整 |
| 议价／Trade-In | 总预算／净底价、完整费用、贷款结清、四个独立quote对象、两条现金路径、网站asking context | 用户报价／时间估计未经dealer文件认证；asking reference不是收车现金报价 |
| Agent整合 | 多轮facts、条件修改、目标切换、实际tools、参数与结果检查、有限重试／timeout／stop、trace | structured JSON tool requests，不声称已验证native tool_calls或模型自行训练 |
| 英文UI | 聊天、辅助表单、比较、价格明细、来源、临时记忆和手动export | 本机使用；刷新／重启可能丢失状态；Stop在轮次之间生效 |
| 当前复核 | 152项回归通过；实际浏览器／Ollama记录见STAGE9_RESULTS.md | development acceptance不是独立holdout，也不是市场价格准确率 |

本次补齐：模型忙碌时保留原提交／request ID，明确Retry或Discard；丢弃／reset无需调用模型；估价区间保留cents且可换行；Git忽略`.streamlit/secrets.toml`；修正新旧文档的当前状态说明。旧服务器导入模块未更新的问题通过重启验证，运行指南已解释。

## 接下来必须完成的验收

1. **独立系统评估**：请未参与该案例调试的组员先写英文输入、预期facts／必须满足的约束／追问及金额，再运行冻结版本。覆盖四类业务、多轮修改、排除品牌、无匹配、单位／币种错误、未知费用、证据不足、事故／泡水和任务切换。保留失败、耗时及实际trace，不只录成功结果。把用于修复的用例转入regression；另保留未调试的holdout，不把二者合算成泛化准确率。
2. **计算与推荐验证**：财务结果按公开公式人工复核，检查费用／贷款只计一次、预算与净底价不突破；硬约束通过率和slot正确率分别记录。Lifestyle relevance需要独立用户／组员评价标准；当前heuristic分数不当作accuracy。无独立成交labels就不报告市场MAE／RMSE或“最佳售价”。
3. **跨电脑复现**：至少另一名组员从仓库重新建立venv、安装锁定依赖、下载qwen3:4b并运行tests／UI／四类演示；记录OS、Python、模型、硬件、安装问题和实际结果。本机pip check通过不等于组员电脑已通过。现有Python、Ollama、Streamlit足够；测试使用unittest，无需另装pytest或LangChain。
4. **数据范围决策**：在录制前决定保留目前有限样本并清楚展示不足，或补充经核实的exact comparables。新增记录需验证来源、日期、单位、去重、variant／year／transmission及asking标签，再重跑质量与业务检查。30–50条只是早期建议，不是官方最低要求；总数不能代替某车型的有效可比覆盖。
5. **演示冻结**：固定Git revision、依赖、模型、数据／reference日期、演示输入和预期结果，先排练再录屏。保留一个失败／恢复故事及导出证据。来源网页打开需要网络；本地保存数据与已下载模型的咨询路径不靠实时网页。此前冻结／视频目标不后移。

以上是建议的工程验收方法，不是课程新增的官方硬性数量要求。独立测试、其他电脑、成员贡献和视频排练必须以真实参与结果填写，不能由本机开发记录替代。

## Assignment材料仍待完成

| 交付 | 剩余工作 |
|---|---|
| Final Report | 完成Introduction、Literature Review、Methodology、Implementation、Conclusion五章；把真实算法、数据、至少两个实施挑战、验证结果、限制／future work写入对应章节 |
| Video／Final Demonstration | 英文脚本、真实操作录屏、配音、字幕／剪辑与排练；覆盖生活方式选车、挂牌参考估价、议价／Trade-In和Agent多轮恢复；时长按课程实际通知 |
| Individual Presentation／Q&A | 每人能解释完整架构及本人真实贡献；说清Frames／rules／scoring／LLM职责、unknown、价格来源及为何不是训练的ML tree |
| Contribution／Workload Matrix | 按真实工作填写self-rating及Remarks justification、各任务分工、Student ID／签名；不预填虚构贡献 |
| Submission checks | APA文内引用与references对应、页码、末尾references前word count、Times New Roman或Arial 11pt、1.15行距、justified；按课程要求提供Turnitin及最终文件，核实portal／具体提交时刻 |

权重沿用已读取的原guide：system30%、report30%、video10%、presentation10%、Q&A10%、contribution10%；lecturer的Agent adaptation是功能／技术方向，不能据此声称原rubric已被正式替换。原guide的report章节标注歧义及检测阈值保留在课程context，应按lecturer最终解释和课程提交规定处理，不把本清单当成新的课程文件。

现有排程目标为10/23前冻结核心、10/24–10/28集中视频、10/29–11/01材料review／排练／提交检查、11/02按指定时刻提交。脚本、报告和成员解释现在即可并行制作。

## 第一版暂缓记录（2.0范围见开头更新）

当天日期检查、咨询时实时搜索、额外马力／drivetrain／油箱指标和云端部署仍未加入。2.0已授权扩充可用数据，但未授权绕过网站使用条件；市场校准的车况／损伤扣价与全部Vision已取消。当天日期检查仅检查保存证据是否过期，实时搜索才取得新资料，两者不同。
