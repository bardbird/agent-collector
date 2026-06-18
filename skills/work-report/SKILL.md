# work-report

生成结构化的日报 / 周报 / 月报。从用户提供的工作记录片段中提炼"本周重点 / 产出 / 风险 / 下周计划"四段式内容。

## Instructions

### Step 1: 确认报告类型
- 触发: 用户说"写周报 / 月报"或包含日期范围。
- 行为: 若类型未指明,通过 `AskUserQuestion` 询问类型(周报 / 月报 / 季度报)。

### Step 2: 收集元信息
- 必填: 花名(reporter)、报告周期(period)、核心工作主题(theme)。
- 缺失时通过 `AskUserQuestion` 逐项追问,**不得编造**。

### Step 3: 填充模板
- 读取 `assets/report_template.md` 作为报告结构。
- 用收集到的元信息和工作记录填充四段:本周重点 / 关键产出 / 风险与阻塞 / 下周计划。

### Step 4: 落盘
- 调用 `scripts/generate.py --reporter X --period Y --theme Z --notes-file N`,产出 `out/<reporter>_<period>.md`。

## Examples

### Example 1: 数据清洗周报
**用户 query**: "帮我写一份本周的周报,主要内容是完成了数据清洗工作。"
**执行流程**:
1. Skill 触发 → 加载 SKILL.md。
2. `AskUserQuestion` 问花名 / 周期范围。
3. 用户回复"张三 / 2026.04.14-2026.04.18"。
4. `scripts/generate.py` 渲染模板。
5. 返回 `out/张三_2026W16.md`。

## Limitations
- 不主动对接外部 KMS(语雀 / 飞书) — 需另起 fetch_yuque skill。
- 仅做结构化生成,不做内容润色 / 翻译。
