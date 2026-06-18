---
name: glm-vf
description: Use when 作为甲方/质检方验收多模态 Agentic 训练数据交付包(JSONL 轨迹、verifier、mock、skills 库,对应需求 §5.1-5.9),或复检供应商整改后是否合格。触发词:验收、抽检、复验、送检、退回整改、verifier 跑通/恒真/宽松、mock 覆盖率、schema 校验、反模式检测、数据合格率、RL verifier 通过率。
---

# glm-vf — 多模态 Agentic 数据全量验收（甲方质检）

以甲方/质检方身份，对供应商交付的训练数据包做**全量、独立、可复现**的验收。
立场：**采信证据，不采信自报。**

## 六条铁律（不可绕过，违反即判定验收无效）

1. **不采信自报** — manifest / report / 供应商"已修复" / 自测数字，一律视为未经证实。所有门槛由验收方独立实跑。
2. **证据先行** — 任何"通过"结论必须附实跑命令 + 输出。无证据 = 未验证，禁止凭印象判通过。
3. **verifier 正负双向** — 只跑正向 pass=True **不算通过**。必须构造负向（错答/缺字段/无产物/无关文本）证明 pass=False；负向也 pass=True 即判"恒真/宽松"退回。
4. **覆盖率看分母** — mock 覆盖率 100% 不够，必须确认 `skipped=0`；skipped>0 = 可能静默跳过未定义工具，虚报嫌疑。
5. **一票否决即退回** — schema / verifier 跑通 / 反模式 任一不达标，整批退回。不存在"基本通过"。
6. **整改次数** — §8.4 同一批次最多 2 次整改。每次复验记录"第 N 次"，第 2 次仍不达标 = 交付失败。

> **违反铁律的字面就是违反其精神。** 不得以"差不多""供应商说修了""样例太少就算了"绕过。

## 验收清单（按序执行，每步留证据）

脚本位于本 skill 的 `scripts/`。`<交付目录>` 指含各分项目录的根（如 `delivery`）。

### 0. 包完整性
每个分项自包含：`batch_*.jsonl` + `manifest.json` + `report_batch_01.md` + `assets/`（有图项）+ `mock/`（5.6/5.7/5.8/5.9）+ `verifier/`（5.2/5.3/5.5/5.7/5.9）。**缺一即退回。**（教训：5.7 曾缺 manifest+report。）

### 1. Schema 独立校验（门槛 100%）
```bash
python3 scripts/acceptance_schema.py --root <交付目录>
```
硬查：tools 非 null/非空、`tool_calls[].name` 在 tools 定义、`tool_call_id` 严格配对、末消息 assistant、assistant 无 tool_calls 时 content 非空、tool content 非截断、image_url 路径存在、system-reminder 不误入 system role、RL 必填 model_query+answer_gt。**任一 error → 整批退回。**

### 2. Verifier 实跑 + 正负向（RL 项，门槛 ≥95%）
```bash
python3 scripts/verify_recheck.py --item <RL分项目录>   # 可多次 --item
```
必查：正向真实 pred pass=True；**负向（空 pred / 无产物 pred）必须 pass=False**；返回含 pass/score/reason；`py_compile` 通过；依赖在 requirements 声明。
（教训：5.5 曾依赖未声明的 Pillow → 0% 跑通；后又一版 fallback 预置标准图 → 恒真。）

### 3. Mock 覆盖率（5.6/5.7/5.8/5.9，门槛 100% 且 skipped=0）
```bash
python3 scripts/mock_coverage.py --root <交付目录>
```
要求 `miss=0` **且** `skipped=0` **且** `rate=100%`。skipped>0 须逐条核查是否漏录工具 mock。

### 4. Mock 确定性 + 404
```bash
python3 scripts/mock_server_e2e.py --root <交付目录>
```
逐条回放：同 request → 同 response（一致性 100%）；未命中 → HTTP 404。

### 5. 反模式 + 占比约束（§4.4）
四大反模式（模板化 query >30% / 步骤处方 / 单一操作 >50% / 跨域雷同 >60%）一票否决。占比类（反思 5–10%、多跳 ≥50%、场景 ≥10 类每类 ≥5%、5.9 六类情形、语言中文 ≤40%）需足够样本。**POC 样例量小无法统计时，必须标注"无法判定，留全量批次"，不得判通过。**

门槛与分项约束详见 `references/thresholds.md`。

## 合理化漏洞表（验收方常见放水点，全部禁止）

| 借口 | 现实 |
|------|------|
| 供应商说"已修复" | 不算数，按清单全部重跑 |
| 只跑了正向 pass=True | 必须负向证明非恒真，否则退回 |
| 覆盖率显示 100% | 必须查 skipped；>0 即虚报嫌疑 |
| 样例只有 1 条，占比没法算 | 标注"POC 无法判定"，**不得**判通过 |
| verifier 能编译就行 | 须实跑 + 负向 + 依赖声明 |
| 基本达标，给个通过 | 一票否决项无"基本"，不达标即退回 |
| manifest/report 齐全就信 | 自报值，独立复算 |
| verifier 对当前样例 pass 就行 | 须能区分正负轨迹（有效性），全量前要去硬编码 |

## 红线 — 出现即停，判退回

- 采信自报而未独立验证
- verifier 只测正向 / 负向也 pass=True（恒真）
- 覆盖率 skipped>0 未深究
- 占比约束未达标却写通过
- RL verifier 0% 跑通 / 签名偏离统一接口 / 依赖未声明

## 输出报告（必须含）

1. 结论先行表（分项 × 判定：🟢通过 / 🔴退回整改）
2. 每项实跑证据（命令 + 输出）
3. 缺陷分级：🔴 退回级 / 🟡 整改级 / 🟢 提示级
4. 整改要求（可执行）+ §8.4「第 N 次整改」标注
5. 占比类约束标注「POC 无法判定 / 全量待验」
