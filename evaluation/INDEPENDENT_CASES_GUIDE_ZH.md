# 独立案例怎样提交

独立案例是组员在看到该输入的程序结果之前，自己写好输入、必须满足的条件和预期依据。它用于检查系统是否适合真实需求；照抄教程的已知成功案例只算操作检查。

1. 建议由未参与相应案例调试的组员先写案例，可按4人各5例、合计20例安排，覆盖自己真实想到的买车、卖车、议价、Trade-In或信息不足情况。这个数量是本组可执行目标，不是official guide新增硬性要求，也不保证统计代表性。
2. 复制 `independent_cases_template.json` 到自己本机 `team_results` 文件夹，保留原始空模板。用VS Code或普通文本编辑器填入 `cases` 数组。字符串用双引号，不能在JSON中写comments。
3. 每个case填写 `case_id`、`author`、`authored_on`、`goal`、`english_input`、`expected_hard_constraints`、`acceptable_outcome_and_reason`、`source_basis`、`frozen_before_outputs`。多轮输入可在english_input中用数组保留先后次序；预算／座位／币种等预期应明确。无法预先判断某个市场数值时，预期可以是“资料不足、不应造价”，附理由。
4. 文件完成后，在PowerShell执行 `Get-FileHash .\team_results\YOUR_NAME-cases.json -Algorithm SHA256`，把实际哈希和冻结日期记入自己的记录表。此时还未运行这些输入。之后实际结果另记，不覆盖预写版本。
5. 运行自己的案例，保存所有状态／追问／失败／耗时与咨询导出。财务数字另行手算；推荐要解释是否满足需求，不把程序自己产生的分数当正确答案。
6. 若比较v1与v2，评审时可让另一位成员把两份输出换成A／B标记，先评分再揭晓。明确记录哪些输出确实盲评，未做到就不声称盲评。
7. 如使用这些案例调试／改权重，之后它们改归development cases；要检验改完后的泛化能力，需要另留没用来调试的输入。独立案例不等于真实成交数据，不证明提高成交成功率。

填写示意只说明结构，下面的占位符不能当作已提交的真实案例：

```json
{
  "cases": [
    {
      "case_id": "YOUR_NAME-01",
      "author": "YOUR_NAME",
      "authored_on": "填写实际日期",
      "goal": "buy",
      "english_input": "填写自己设计的英文输入",
      "expected_hard_constraints": {},
      "acceptable_outcome_and_reason": "先写预期和原因",
      "source_basis": "依据课程规则、公开计算或适用来源；不足资料要说明",
      "frozen_before_outputs": true
    }
  ]
}
```

组员填好后，通过组内既定方式交给Ryan；仓库当前空模板仍不能算已收到个人贡献或已完成独立验收。
