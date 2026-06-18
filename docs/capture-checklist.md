# §5.1–§5.9 真实采集任务清单

> **目的**:本仓库严守"忠实采集 → 忠实转化",**禁止捏造**。
> 本清单列出每个分项需要跑的真实任务模板,作为采集时的指导,保证产出的 raw_turns 满足甲方 §4.1/§4.4/§5.x 硬约束。
>
> 用法:`./start.sh` 起代理 → 在另一终端 `./start.sh capture` 起隔离 Claude Code → 按本清单跑任务 → `./start.sh stop` 落盘 → `./start.sh transform 5.x` 转化校验。

## 总览红线(每条都要满足)

| 维度 | 通用 | §5.4 例外 |
|------|------|-----------|
| 工具调用轮数 | ≥ 4 | 2-6 |
| 末条消息 | assistant | 同 |
| assistant 空消息 | 禁止 | 同 |
| tools 字段 | 不可 null | 同 |
| tool_call_id 配对 | 100% | 同 |

## ⚠ Query 编写第一守则:不准 prompt 里替 agent 拆解

甲方 §4.4 表 19 的 **4 条反模式红线**,触发任一条 → **整批退回**:

| 反模式 | 判定 | 典型违规 |
|-------|-----|---------|
| 模板化 query | 同采购项 > 30% 同句式 | "请用 X 分析 Y" × 100 条 |
| **步骤处方式指令** | **query 中逐步告诉模型该做什么** | **"1) 数文件 2) 读文件 3) 总结"** |
| 单一操作范式 | > 50% 轨迹工具序列完全相同 | 每条都是 `Bash→Read→Bash` |
| 领域多但行为同 | 跨领域雷同度 > 60% | 换了数据但流程一样 |

**user query 必须是"目标/痛点",不是"操作步骤"**。让 agent 自己决定:用什么工具、调几次、什么顺序、何时停。

| ✗ 反例(步骤处方式) | ✓ 正确(目标导向) |
|---|---|
| "用 work-report skill 帮我生成周报,然后 AskUserQuestion 问我细节" | "这周做了哪些事我都列在 `~/notes/2026w24.md` 里了,帮我整理成给老板看的周报,需要追问就追问" |
| "1) 读 sales.csv 2) 筛选 Q1 3) 求和 4) 输出两位小数" | "我们 Q1 收入到底是多少?数据在 `data/sales.csv`,要给 CFO 一个准数" |
| "用 image_search 识别图里的车,再用 web_search 查直流快充功率" | "这车纯电版直流快充能开多大功率?"(附图) |
| "用 weather_query 查上海周三天气,再用 calendar_create 建会" | "周三在上海有个户外团建,帮我安排一下,下雨就改室内" |

**附加禁项**:
- 不准在 query 里点名工具(`Skill` / `Bash` / `python` / `web_search`...)
- 不准在 query 里指定轮数 / 顺序 / 中间产物路径(除非确实是用户需求)
- 不准 query 里出现"step / 步骤 / 然后 / 接着 / 最后"这种程序员强制流程的词
- 一个采购项内,query 句式要打散:陈述句 / 疑问句 / 命令句 / 抱怨句 各占一些

## §5.1 Skills SFT 轨迹

| 项 | 要求 |
|----|------|
| 工具白名单 | `Skill`, `AskUserQuestion` |
| 首条 user.content | array,含 `<system-reminder>` 注入 skills 列表 |
| meta.skill_name | 必填(等于实际调用的 skill 名) |
| 反思 | 不构造 |

**采集 query 示范**(全部目标导向,**禁止逐字复制成轨迹**,且**绝不能点名 skill**):
- "下周一组会要我汇报,这周做了哪些事在 `~/notes/2026w24.md`,帮我整理成给老板看的周报,数据清洗那部分单独成段;不清楚的地方追问我。"
- "客户要一张产品主图的方版本头像,原图横构图,人脸偏左,你看着办。"(附图)
- "组员让我帮他把这张截图里的关键操作步骤标出来给培训用。"(附图)
- 跑完该会话自然出现:Skill 调度 ≥1 次 + AskUserQuestion ≥1 次 + 总轮数 ≥4。**如果跑完不达,是 query 写得不够"难",不是 agent 的错**。

## §5.2 Skills RL 轨迹

§5.1 + 额外:

| 项 | 要求 |
|----|------|
| answer_gt | 由你在转化前手工标注,落 `<task>.gt.json` |
| model_query | 形如:"判断模型生成的周报是否包含 X 关键信息。回答 YES 或 NO。" |
| 反思轨迹 | 批次 5%-10% 配比 |
| verifier | 自动跑 `verifier/verifier_5_2.py`,100% 跑通 |

## §5.3 RL 高质量 QA(沙盒)

| 项 | 要求 |
|----|------|
| 工具白名单 | `Skill`, `Bash` |
| meta.sandbox | true |
| meta.verifier_type | `exact_match` / `model_judge` / `script` |
| answer_gt | 唯一且明确(0/1 二值) |
| 示例 query | "Q1 收入到底是多少?数据在 `data/sales.csv`,要给 CFO 一个准数,小数点后保留两位。" → gt=`1284350.75` |
| 示例 query | "上个月线上崩了几次?日志在 `logs/incidents.jsonl`,只算 P0/P1。" → gt=`3` |

## §5.4 多模态多轮 Python(SFT)

| 项 | 要求 |
|----|------|
| 工具白名单 | `python`(代理需在采集前替换 Claude Code 默认工具集) |
| user 首条 | 必须 array 且含 `image_url` |
| 轮次 | **2-6**(例外) |
| meta.operations | ⊆ {crop,rotate,scale,filter,compose,color,watermark,perspective,collage} |
| 反思 | 批次约 5% |

**采集前置**:Claude Code 默认无 `python` tool,需先把代理切到能注入此工具的网关(或起一个最小化代理,只暴露 `python` exec 工具)。**此项不能用现有 5 条 raw_turns**。

## §5.5 多模态 Python FC RL

§5.4 + 额外:

> 已跑通案例与复用流程见: [`docs/section-5.5-success-flow.md`](section-5.5-success-flow.md)。

| 项 | 要求 |
|----|------|
| answer_gt | 输出图可验证描述(如尺寸保持、指定角标/水印/变换存在) |
| model_query | 围绕本条输出图的客观验证 prompt,回答 YES 或 NO |
| verifier_type | `script`(走 `verifier_5_5.py` PIL 校验) |
| 反思 | 批次 5%-10% |

## §5.6 多模态搜索 SFT

> 已跑通案例与复用流程见: [`docs/section-5.6-success-flow.md`](section-5.6-success-flow.md)。

| 项 | 要求 |
|----|------|
| 工具白名单 | `image_search`, `web_search`, `image_zoom_in` — **schema 与需求文档逐字段一致** |
| 含 system message | 是(说明能力声明) |
| user 含图 | 是 |
| meta.search_hops | ≥1 |
| mock | `mock/mock_responses.jsonl` 覆盖率 100% |

**采集前置**:Claude Code 内置 `WebSearch` 与需求 `web_search(query)` schema 不同 — 必须通过 `capture/run_search_tool_task.py` 暴露 §5.6 标准工具，并让请求经过 recorder 代理。

## §5.7 多模态搜索 RL

§5.6 + 额外:

| 项 | 要求 |
|----|------|
| answer_gt | 客观可验证(品牌型号 / 参数 / 数值) |
| meta.search_hops | ≥ 2(多跳硬要求) |
| verifier | `verifier/verifier_5_7.py` 跑通 |
| 示例 | Zarya/FGB 首次发射日期、运载火箭、发射场 → gt=`1998年11月20日，Proton-K火箭，拜科努尔航天发射场` |

## §5.8 工具调用泛化 SFT

> 已跑通案例与复用流程见: [`docs/section-5.8-5.9-success-flow.md`](section-5.8-5.9-success-flow.md)。

| 项 | 要求 |
|----|------|
| 工具集 | 按场景挑(weather / calendar / product / map / 表格 / DevOps / IoT 等) |
| meta.scene | ∈ {search, map_local, ecommerce, calendar_email, weather_travel, table_data, code_devops, knowledge_qa, device_control, mixed} |
| 跨工具串联 | ≥ 2-5 个 |
| mock | 100% 覆盖 |

## §5.9 工具调用泛化 RL

> 已跑通案例与复用流程见: [`docs/section-5.8-5.9-success-flow.md`](section-5.8-5.9-success-flow.md)。

§5.8 + 额外:

| 项 | 要求 |
|----|------|
| answer_gt + model_query | 必填 |
| meta.situation | ∈ {normal_chain, error_recovery, redundant_call, param_fix, tool_fail, early_stop} |
| 反思 | 5%-10% |
| verifier | `verifier/verifier_5_9.py` 跑通 |
| 情形分布(批次级) | 正常 50% / 错误恢复 15% / 冗余 10% / 参数 10% / 失效 10% / 早停 5% |

## 反模式守则(触发即整批退回)

- 同分项 > 30% query 同句式 → 模板化
- > 50% 轨迹 tool_call 序列完全相同 → 单一范式
- 跨领域结构雷度 > 60%
- 中文占比 > 40%
- 出现真实 API Key / Token / 密码明文 → 安全红线

## 转化执行顺序(每批跑完后)

```bash
# 1. 落盘
./start.sh stop

# 2. 逐项转化 + 校验(不通过直接落 _rejected.jsonl)
for s in 5_1 5_2 5_3 5_4 5_5 5_6 5_7 5_8 5_9; do
  python3 transform/to_section_${s}.py
done

# 3. mock 覆盖率
python3 mock/check_mock_coverage.py

# 4. 多样性报告
./start.sh report

# 5. 人工抽检 _rejected.jsonl 的错误清单,回到采集环节补
```
