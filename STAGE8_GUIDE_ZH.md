# 阶段8：完整、受约束的多轮Agent Loop

日期：2026-10-15。应用交互与代码使用英文，教学用中文。无需新依赖，保持本机Ollama服务运行。

## 1. 现在新增了什么

Agent可以记住单次会话中已确认的事实，回答追问、修改预算／座位／偏好，切换任务、重置状态，并根据目标请求实际业务工具。Python会验证参数、执行工具、检查结果，最后才允许完成。

```text
Current message + confirmed session facts
  -> Ollama structured fact patch
  -> Python evidence/unit/type checks + memory merge
  -> Ollama structured tool request
  -> Controller checks tool name/arguments/current state
  -> Actual Python tool -> observation
  -> check_result -> ask_user or finish
```

这是hybrid agent：LLM负责理解新消息、识别目标并提出业务工具请求；显式规则限制可用动作与停止条件。业务阶段模型在注册工具中提出请求，Controller拒绝与当前目标不符的调用。开始、追问、检查和完成阶段的动作空间更严格。它不是任意代码执行Agent。

本机qwen3:4b的native tool_calls开发实测曾超时或返回非执行文本，因此当前采用**Schema-constrained JSON tool requests**，不是声称已通过原生tool_calls API验收。返回JSON只是一项请求；真正执行由Controller完成，真实observation再交回模型。原生方式失败记录被保留，没有计算为成功案例。

当前最终英文说明由Controller按检查过的结果生成，避免模型自由改写价格／ID。没有训练新模型，session memory不会更新模型权重。

对于用户明确写出的buy/sell/negotiate/trade-in目标，Python原文规则会约束本轮目标及可提取字段，减少小模型把Trade-In误分成sell的情况。财务金额还按用户明确标注的gross offer／replacement price／replacement fees／disposal fees核对归属；缺少标签或存在冲突时追问，不靠模型猜哪个金额属于哪条路径。`All fees are complete, except insurance is unknown.`不能算完整费用确认。这些是有边界的输入规则，不是通用英文理解保证。

## 2. 先运行交互式CLI

在原vehicle-agent目录：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --as-of 2026-10-15
```

出现`You:`后逐条输入英文：

```text
I want to buy a car. Save fuel.
```

它应追问预算、座位／人数和用途。随后输入：

```text
My vehicle budget is RM60000, a six-person family, mainly city commuting. Exclude Toyota.
```

上一轮的省油偏好仍在；当前快照仅有三条合格旧Alza，没有可核实fuel比较，因此说明不能支持省油结论。再输入：

```text
Change my budget to RM35000.
```

家庭人数、用途和排除品牌保留；当前快照无匹配，不自动提高预算或减少座位。

`--as-of`复现保存快照日期；不传时按马来西亚当天日期验证估价证据。旧数据以后可能过期，不得使用历史日期伪装最新市场参考。

## 3. 其他目标的英文示例

卖车：

```text
I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, odometer 50000 m, fair condition. No major accident and no flood damage.
```

应记录50km，查询三条挂牌reference。默认不自动按里程／车况调整价格。

议价：

```text
I want to negotiate as a buyer for a Perodua Alza 1.5 SE, manufactured in 2020, automatic. The seller currently quotes RM46000 excluding fees. My total purchase budget including fees is RM46000. All fees total RM1500 and are confirmed complete.
```

应实际先取得同identity asking reference再给出建议。裸车counter上限44500，费用仍另计。模型不能把median当保证成交价。

Trade-In可以分两轮填资料；完整示例见evaluate_agent.py中的trade_in场景。每条路径明确replacement price／fees与gross disposal offer／fees，旧贷款结清额明确，确认费用完整后才作完整财务比较。current_vehicle是被卖掉／折抵的旧车，不是replacement vehicle。

## 4. 记忆、修改、选择与重置

- 默认记忆在该CLI进程内；只更新本轮有原文依据的slots，不因用户没重复就清空旧值。
- 非MYR预算、缺单位里程或非法修改会追问；相关旧金额不会悄悄继续驱动结果。
- `also exclude Honda`增加排除品牌；`remove Toyota from excluded brands`移除指定品牌。重新排名后不能选择已经不合格的旧候选。
- `select the first vehicle`可让模型从当前已验证候选ID选择；不允许任意ID。保存挂牌价不会自动成为“对方当前报价”。
- 改变明确的车辆身份会使旧报价、费用及相关结清资料失效，除非用户本轮重新明确提供。
- 切换目标会清空新任务对应的旧输入，避免另一任务金额泄漏；从sell进入negotiate／trade_in可复用已确认车辆身份与损伤报告，不编造财务报价。
- 家庭人数与座位不符时，可回答`Not everyone travels together.`；它记录出行事实，不篡改家庭人数。
- `/reset`清空会话，`/stop`停止本次咨询并保留事实，`/quit`退出CLI。

需要跨命令保存时：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --session sessions/demo.json --as-of 2026-10-15
```

同一文件恢复已验证类型的事实。历史工具结果不会作为新鲜observation使用，每次重新执行当前工具。sessions目录已gitignore；文件本身保存在本机。文件上限5MB。

## 5. 如何检查工具真的执行

普通输出会显示`Status`及executed tools。完整记录：

```powershell
.\.venv\Scripts\python.exe agent_cli.py --message "I want to buy a car. Budget RM50000, at least five seats, mainly city commuting. Save fuel and a spacious boot." --as-of 2026-10-15 --json
```

查看facts、rules、tools、checks和trace。tools记录实际参数与observation，checks记录独立的约束／金额核对。模型说“done”不等于完成；业务工具必须真正运行且check_result通过，finish才有效。

主要检查包括：候选ID是否来自dataset且全都符合硬条件；分数是否与分项一致；参考median/range是否由可比价格算出；买方counter+fees是否超预算；卖方counter扣费／结清是否低于净底价；Trade-In是否双扣贷款、误把未知金额当0或推荐超现金上限的路径。

## 6. 超时与停止

- 每个模型请求默认最多90秒，并有独立可取消进程的wall-clock边界。
- 每轮总预算240秒；每项模型请求最多重试1次。
- 每轮最多10次工具请求、最多2次工具修复错误。
- 输入最多6000字符，数据上限5000行，trace保留最近400个事件。
- 达到限制／模型故障／错误参数／未通过检查时，不标记complete；保留已经通过检查的事实。
- `complete`表示本次咨询已得到经检查的结果，也可能是no_matches、insufficient_evidence或inspection_required；不表示已经买卖成功。

本机4GB VRAM的小模型仍可能较慢，复杂资料可分多轮输入。正确失败与追问是必要行为，不应把所有输入都包装成成功。

## 7. 文件与验证入口

| 文件 | 用途 |
|---|---|
| agent_state.py | typed memory、fact patch、goal switch、limits |
| agent_grounding.py | 当前消息证据、类型、单位、币种与修改校验 |
| agent_tools.py | registry、参数校验、业务执行与result checks |
| agent_controller.py | Sense/Plan/Act/Observe/Check循环与Ollama请求 |
| agent_cli.py | 英文多轮交互入口 |
| test_agent.py | 可重复的程序状态／故障边界测试；不冒充真实模型测试 |
| evaluate_agent.py | 实际Ollama自然语言、多轮与四类工具验收 |

```powershell
.\.venv\Scripts\python.exe agent_cli.py --script examples/agent_buy_dialogue.json --as-of 2026-10-15
.\.venv\Scripts\python.exe -m unittest -q test_profile test_matching test_scoring test_valuation test_input_grounding test_stage5_audit test_negotiation test_agent
```

实际结果与限制见[STAGE8_RESULTS.md](STAGE8_RESULTS.md)；官方协议参考：[Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)。下一阶段仍是英文UI与更广的系统/holdout评估、报告和视频，尚未安装Streamlit。代码与文档的交付版本以Git提交记录为准；sessions会话文件仍仅保存在本机。
