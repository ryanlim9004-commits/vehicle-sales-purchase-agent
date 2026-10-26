# 用途记录修复与 Kaggle 资料检查

日期：2026-10-22。本批是本机修复与资料研究，不表示已commit／push、已扩大库存或已训练价格回归。

## 修复了什么

1. 已有`city_commute`后，用户补充`i want a long distance travel`，如果模型漏提取，旧补救规则因“用途非空”而跳过。现在会补上明确的新用途，并保留未修改的预算、座位和偏好。
2. 实际模型曾把旧用途和新用途一起返回；旧用途没有本轮证据，使整组更新失败。现在忽略没有本轮证据的已知重复项，只接收有原文支持的新项；新编造的用途仍拒绝。
3. 表单原来写comma separated，却只接受少数固定名称，`travel,commute`只显示`'travel'`。现在Driving use改为多选，避免猜固定拼写；底层适配器也接受明确英文别名并提供可操作的错误。
4. 聊天与表单共用buyer_usage.py的类别与表达；用途标签是内部标准值，不是车辆数据库字段缺失。补库存不能修复输入解析。

| 用户表达 | 内部值 |
|---|---|
| commute、commuting、city commuting | city_commute |
| family travel、family trips | family_travel |
| long distance travel、long-distance driving、road trips | long_distance |
| travel、trip单独出现 | 含义不足；须说明家庭或长途，不自动猜 |

英文支持范围有限，不能宣称所有自然语言都已解决。拒绝、未知、不确定及没有原文支持的enum不会凭标签获得确认。用途也不自动推导安全、舒适或可靠性优先级。

## 怎样操作

先下载需要保留的咨询记录。在原Streamlit终端Ctrl+C，再在项目目录执行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

打开`http://127.0.0.1:8501`。仅刷新旧服务不足以保证Python模块重新加载。

聊天：在已有通勤需求的Buy咨询中输入`i want a long distance travel`，确认usage同时保留city_commute和long_distance。

表单：Driving use可以选择City commuting、Family travel、Long-distance driving中的多项。提交的非空选择替换用途列表；留空保留旧用途；Unknown单独选择时清空。Unknown和具体用途不能一起提交。品牌列表仍支持逗号分隔。

## 验收与限制

- 最终**213项离线测试通过**，21.182秒，0failures／errors／skipped；原195项加18项用途回归。模型回复预设、业务工具真实。
- 最终qwen3:4b两轮实际测试通过，31.03秒／21.51秒。第一轮原句在已有通勤上增加长途；第二轮用表单替换成家庭＋长途。预算60000和fuel high保持，工具及结果检查通过。
- 实际浏览器多选通勤＋长途、预算60000／5座提交完成；Confirmed facts展开后同时显示city_commute和long_distance。[截图](docs/usage-fix-ui-20261022.jpg)。本轮未验证浏览器导出下载。
- 开发失败保留：第一次临时验收脚本缺Windows多进程main入口保护；修正后的首次真实模型测试仍因旧用途夹带而追问，促成本次第二项修复。最终通过不能抹去失败历史。
- 结果摘要见[机器可读记录](docs/usage-fix-20261022.json)。本轮是Ryan电脑上的开发回归，不是组员独立评估。

## 数据研究结论

用户提供的notebook底层Cars Dataset明确标注Mockaroo模拟资料，缺价格／里程／座位／油耗，未下载或导入。

另外找到并下载Malaysia_Resale_Carlist历史候选，974行／7列；已保留原ZIP、哈希、只读检查脚本和notebook，未加入Agent。详细来源与缺口见[资料检查](docs/KAGGLE_RESEARCH_20261022.md)。价格快照仍是原17笔，回归仍未启用。
