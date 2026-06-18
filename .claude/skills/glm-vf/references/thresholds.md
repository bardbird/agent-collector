# 验收门槛速查（glm-vf references）

> 来源：《多模态 Agentic 数据需求 2.0》§4.3 / §4.4 / §5.x / §8 / 附录 C。冲突一律以 docx 原文为准。

## §8.3 合格标准（任一不达标 → 整批退回）

| 指标 | 门槛 | 方式 |
|------|------|------|
| Schema 合法率 | **100%** | 自动（字段缺失/类型错/tool_call_id 不匹配即不过）|
| 内容合格率 | ≥95% | 人工抽检 |
| Verifier 通过率（RL）| ≥95% | 100% verifier 自动 + 10% 人工复审 |
| 多样性达标 | §4.4 全满足 | 分布统计 |
| 反模式检测 | 未触发任何红线 | 自动扫描 |

## §8.2 抽检策略

- SFT（5.1/5.4/5.6/5.8）：分层随机抽样 + 人工，每批 3% 且 ≥100 条
- RL（5.2/5.3/5.5/5.7/5.9）：100% verifier 自动校验 + 10% 人工复审
- Skills 库：随机抽 SKILL.md 完整性 + 脚本可执行性，20% 且 ≥200 个

## §8.4 退回与整改

- 任一指标不达标 → 整批退回，5 个工作日内整改
- 同一批次最多 **2 次** 整改，超过视为交付失败
- 每次复验须记录是第几次整改

## §4.3 Verifier 接口（RL 必备）

```python
def verify(pred: str, answer_gt: str, model_query: str = "") -> dict:
    return {"pass": bool, "score": float, "reason": str}
```
- 三类：`exact_match`（数值/日期，注意格式对齐如 "640kW" vs "640 kW"）、`model_judge`（开放式，需位置互换校准评判偏差）、`script`（图像/文件，每场景专用脚本）
- 每个 RL 数据集附 verifier.py 且 **100% 跑通**
- `model_query` / `answer_gt` 为 RL 必填顶层字段

## §C.2 Mock 接口（5.6/5.7/5.8/5.9 必备）

- `mock_responses.jsonl` 每行：`{request_hash, tool_name, request, response}`
- `request_hash = sha256(tool_name + json.dumps(arguments, sort_keys=True))`
- 一致性：同一 request 必须返回同一 response
- 覆盖率：轨迹中所有外部工具调用 100% 有对应 mock
- `mock_server.py`：`POST /mock/<tool_name>`，body `{"arguments":{...}}`，未命中 `404 + {"error":"no mock found","request_hash":...}`
- 附 `check_mock_coverage.py`

## §4.4 通用硬指标 + 多样性

- 工具调用：每条 ≥4 轮且平均 ≥7 轮（**5.4 例外 2–6 轮**）
- 禁纯 coding 无工具调用；禁无 workspace 纯聊天（5.1/5.2）
- 末消息须为 assistant；assistant 无 tool_calls 时 content 必须非空
- 数据须脱敏（无真实 API Key/Token/密码明文）
- 反思轨迹占比 5–10%（5.2/5.4/5.5/5.9）
- 多样性：D1–D8 八大领域 / 80 二级子方向；同项工具组合 ≥20 种；轮次 4–6 / 7–10 / 11+ 各 ≥15%；英文优先，中文 ≤40%

### 四大反模式（一票否决，触发即整批退回）

1. 模板化 query：同一采购项 >30% query 句式结构相同
2. 步骤处方式指令：query 逐步告诉模型该做什么（剥夺自主决策）
3. 单一操作范式：>50% 轨迹工具调用序列完全相同
4. 领域多但行为同：跨领域轨迹结构雷同度 >60%

> ⚠ 30%/50%/60% 的具体度量算法文档未定义（风险 R1），须 POC 阶段与甲方书面锁定。

## 分项专属约束

| 项 | 线 | Verifier | Mock | 量 | 专属红线 |
|----|----|---------|------|-----|---------|
| 5.1 Skills SFT | SFT | ✗ | ✗ | 5w | user 用 system-reminder 注入 skills；每 skill ≥10 条 |
| 5.2 Skills RL | RL | ✔ | ✗ | 2w | 反思 5–10%；与 5.1 共用 skill 池 |
| 5.3 RL QA | RL | ✔ | 沙盒 | 1w | answer_gt 唯一明确；verifier 二值 0/1 |
| 5.4 多模态 Python | SFT | ✗ | ✗ | 20w | **每条含图**；轮次 **2–6**；反思 ≥5% |
| 5.5 多模态 Python FC | RL | ✔ | ✗ | 2w | 需 script 验证脚本（如像素对比）；操作占比均衡 |
| 5.6 多模态搜索 SFT | SFT | ✗ | ✔ | 20–50w | query 须有搜索必要性；含意图识别/改写/证据引用 |
| 5.7 多模态搜索 RL | RL | ✔ | ✔ | 5w | **多跳搜索 ≥50%**；答案客观可验证 |
| 5.8 工具泛化 SFT | SFT | ✗ | ✔ | 50w | 覆盖 **≥10 类场景**，每场景 ≥5%；每场景 mock 工具定义+标准轨迹 |
| 5.9 工具泛化 RL | RL | ✔ | ✔ | 4w | 覆盖 **1000+ 场景**；六类情形分布见下 |

### 5.9 六类特殊情形占比

正常串联 50% / 错误恢复 15% / 冗余识别 10% / 参数错误 10% / 工具失效 10% / 合适停止 5%

## 附加自研交付物

① 5000 Skill 库（D1–D8 分布；80 子方向每个 ≥50；功能相似度 >80% 视为重复不计，判定方式未定义 = R2）；② 5 项 RL 的 verifier.py（100% 跑通）；③ 4 项 mock 包。

## POC 阶段须与甲方书面锁定的未定义项

- R1：四大反模式 30/50/60 度量算法
- R2：Skill 相似度 80% 判定标准
- R3：80 个二级子方向清单依据
- script 类型 verifier 的统一接口契约（如何传 pred_path 等产物参数）
