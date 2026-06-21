# 5.5-5.9 AI 全流程托管采集技术设计

依据：`docs/多模态Agentic数据需求2.0.docx`  
范围：§5.5、§5.6、§5.7、§5.8、§5.9 的批量采集、转换、校验与交付。  
当前基线：2026-06-21 已用正式流程跑通并重打 `delivery/5.5_python_mm_rl`、`delivery/5.6_search_sft`、`delivery/5.7_search_rl`。

## 1. 目标

本项目的目标不是让模型直接批量写交付 JSONL，而是让 AI 托管采集全流程：

1. 规划任务数量、场景、轮次、语言和多样性配额。
2. 生成自然任务种子和多模态素材。
3. 为 RL 条目准备 `answer_gt`、`model_query` 和 verifier 参数。
4. 调用真实模型，让模型自主使用工具完成任务。
5. 本地工具执行器真实执行工具并回填 `tool_result`。
6. 固化外部工具请求/响应为 mock。
7. 将真实 raw 轨迹转换为客户 §4.1 messages JSONL。
8. 自动执行 schema、分项规则、verifier、mock 覆盖、多样性和反模式门禁。
9. 对失败任务修任务种子、工具场景、GT 或 mock 后重跑；不手改最终 JSONL。
10. 生成自包含交付包、manifest 和报告。

最终交付 JSONL 必须来自真实执行轨迹和转换器，不能由 AI 直接手写。

## 2. 硬规则

### 2.1 多模态输入

- 多模态输入必须作为真实 message image block 进入模型上下文。
- raw Anthropic 轨迹使用 `type: image`；交付 JSONL 使用 `type: image_url`。
- 禁止在用户 prompt 中写本地输入图片路径来冒充多模态输入。
- 若工具执行需要读取图片，采集 driver 必须从 message image block 准备固定 runtime 副本，并只在 tool description 或 executor contract 中暴露给工具。
- 当前 Python 图像工具 runtime 副本为 `out/runtime/input_image.png`，该路径不得写进 user prompt。
- Python 工具中间输出写入 `out/tool_outputs/`；打包时只将最终需要交付的产物复制到 package 内 `assets/outputs/`。

### 2.2 自然结束

- 采集器不得注入虚假 user/control 消息来强制模型结束。
- 禁止硬造 assistant final answer。
- accepted 轨迹必须由模型自主返回自然 final assistant message。
- 最后一轮 assistant 必须有非空文本且不包含 `tool_calls`。
- 如果模型达到 turn 上限仍未自然结束，任务进入 `failed_finalization`，不得进入 accepted raw。

### 2.3 Turn 上限

- `max_turns` 必须可配置。
- 当前 driver 支持 `--max-turns`，正式重跑使用 `100` 作为临时硬上限以避免过早截断。
- 批量生产不建议默认 100。建议默认值：
  - 5.5：`20`，用于覆盖通用轮次分布中的 11+ 桶，并给真实反思/修正留空间。
  - 5.6：`12`，允许多搜索并发和一次补检。
  - 5.7：`16`，允许多跳搜索和 verifier 所需证据链。
  - 5.8/5.9：按 toolset 设置，普通场景 12，复杂 RL 场景 16-20。
- 上限用于失败保护，不用于诱导模型结束。不能用“追加停止消息”绕过上限。
- 轮次验收不能把 §5.4 例外扩展到其他分项：除 §5.4 外，单条轨迹至少 4 个 tool_call/tool_response 配对；生产批次平均至少 7 轮，且 `4-6`、`7-10`、`11+` 三个轮次桶占比各不低于 15%。

### 2.4 Mock 和 Verifier

- 5.6/5.7/5.8/5.9 涉及外部工具，交付包必须提供 mock。
- mock 覆盖率必须 100%，覆盖检查必须在 JSONL 转换完成后单独运行。
- 5.5/5.7/5.9 是 RL 条目，必须提供 verifier 并全量校验。
- RL sidecar 必须与 raw 同名，注入 `answer_gt`、`model_query` 和必要 meta。
- 当前 5.7 verifier 接口期望 `answer_gt`、`model_query` 为字符串；结构化内容需写成 JSON 字符串。
- 5.5 verifier 不得从 `answer_gt` 或 `model_query` 读取 `output_path` 作为待验产物路径；输出路径必须从模型最终回答 `pred` 中提取。
- 每个 verifier 都必须有负向测试：空 pred、拒答 pred、错误事实 pred、缺失产物 pred 等应返回 `pass=False`。该规则适用于所有需要 verifier 的分项，不是 5.5 特例。

### 2.5 交付包自包含

- 每个分项目录必须自包含，不依赖 `out/` 或转换期 `../images`。
- JSONL 内图片路径必须重写为包内路径，例如 `assets/inputs/...`。
- 5.5 输出路径必须重写为包内 `assets/outputs/...`。
- 交付 JSONL 的 `meta` 不得包含生产链路元数据，例如 `source`、`model`、`collection_run`、`delivery_package`。该规则适用于所有分项和所有交付包。
- 交付包的 manifest/report 也不得暴露采集链路路径或模型标识，例如 `source_run`、`source_raw`、`model`、`claude-opus-*`、`claude-code-capture`。
- mock 响应中的业务来源字段可以保留，例如搜索结果来源或工具 fixture 来源；它们不是生产链路元数据。
- 交付包不得包含 `__pycache__`、临时 raw、调试截图或未使用旧输出。

## 3. 当前成功基线

### 3.1 §5.5 Python 多模态 RL

```text
package: delivery/5.5_python_mm_rl
batch: delivery/5.5_python_mm_rl/batch_01.jsonl
input: delivery/5.5_python_mm_rl/assets/inputs/device_label_hold_001.png
output: delivery/5.5_python_mm_rl/assets/outputs/device_label_rework_5_5_formal.png
turn_count: 6
tools_used: python
```

通过结果：

```text
transform accepted=1 rejected=0
verifier_5_5 pass=True score=1.0
verifier_5_5 negative empty/unable/no_artifact pass=False
reason: image ok; red badge ratio=0.283; light text ratio=0.490
```

关键经验：

- 任务要自然包含“读取原图、生成输出、量化自检、最终复核”，否则模型可能 3 轮就结束，低于 5.5 当前 4 轮门槛。
- 5.5 不存在 6 轮上限；长轨迹不是天然错误，但必须自然结束、证据链完整、不过度模板化，并符合批次轮次分布。
- 5.5 verifier 必须从 pred 提取输出路径，不能信任 GT 中的路径。
- 5.5 verifier 必须兼容 pred 中的采集期 `out/tool_outputs/...` 和交付期 `assets/outputs/...`。

### 3.2 §5.6 多模态搜索 SFT

```text
package: delivery/5.6_search_sft
batch: delivery/5.6_search_sft/batch_01.jsonl
input: delivery/5.6_search_sft/assets/inputs/apollo_columbia_exhibit_001.png
mock: delivery/5.6_search_sft/mock/mock_responses.jsonl
turn_count: 4
search_hops: 8
tools_used: image_search, web_search
```

通过结果：

```text
transform accepted=1 rejected=0
mock coverage total=8 hit=8 miss=0 rate=100.0%
```

关键经验：

- 正式采集默认使用 frozen curated evidence，避免 live 搜索结果质量波动。
- prompt 应要求搜索意图、检索词改写、证据表和最终说明，但不能要求具体工具顺序。
- 覆盖检查如果和转换并行跑，可能得到 `total=0` 的无效结果；必须转换完成后单独执行。

### 3.3 §5.7 多模态搜索 RL

```text
package: delivery/5.7_search_rl
batch: delivery/5.7_search_rl/batch_01.jsonl
input: delivery/5.7_search_rl/assets/inputs/zarya_module_panel_001.png
mock: delivery/5.7_search_rl/mock/mock_responses.jsonl
turn_count: 4
search_hops: 5
tools_used: image_search, image_zoom_in, web_search
```

通过结果：

```text
transform accepted=1 rejected=0
verifier_5_7 pass=True score=1.0
mock coverage total=5 hit=5 miss=0 rate=100.0%
```

关键经验：

- 5.7 gate 当前要求 `search_hops >= 4`，任务必须天然需要多跳证据链。
- sidecar 中结构化 GT 要写成 JSON 字符串，否则现有 verifier 会收到 dict 并抛类型异常。
- `required_sources` 能防止模型只给事实、不引用关键证据源。

## 4. 分项设计

### 4.1 §5.5 多模态 Python FC 强化

要求：

- 类型：RL。
- 数据量：20,000。
- 多模态必需。
- 必填 `answer_gt`、`model_query`。
- 必须包含 `python` 工具定义和真实 Python 执行轨迹。
- 操作覆盖裁剪、旋转、缩放、滤镜、合成、色彩调整、水印、透视变换、拼接等。
- 使用脚本式 verifier，优先像素级、尺寸级、文件级验证。
- 反思轨迹目标 5%-10%，生产建议锁定 6%-8%。

任务设计：

- prompt 只描述业务目标和验收要求，不写输入图片路径。
- 输出路径可以作为交付目标写入 prompt，但需要按 task_id 或唯一文件名隔离。
- 每条任务应有明确可验证终止目标，例如输出文件、尺寸、颜色比例、文本可见性、裁剪区域、拼接尺寸等。
- 对需要反思的任务，只通过真实错误信号制造修正机会，例如输出目录缺失、图片模式不匹配、坐标越界、字体缺失、依赖缺失。
- `answer_gt`/`model_query` 只能描述正确输出应满足的条件，例如尺寸、检查项和阈值；不得硬编码产物路径。
- verifier 必须从模型最终回答中抽取模型声称的输出路径，然后验证该路径指向的文件内容。

门禁：

- user content 必须含 `image_url`。
- tools 只允许 `python`。
- `meta.operations` 必填且属于白名单。
- `answer_gt`、`model_query` 必填。
- 4.4 通用轮次要求至少 4 个工具配对轮；5.5 不设置 6 轮上限。§5.4 才是 `2-6` 轮例外。
- verifier 必须通过。

### 4.2 §5.6 多模态搜索 SFT

要求：

- 类型：SFT。
- 数据量：200,000-500,000。
- 多模态必需。
- tools 必须包含 `image_search`、`web_search`、`image_zoom_in`。
- 最终回答必须包含搜索意图、检索词改写、证据整合和最终答案。
- 交付必须提供 mock，不提供 verifier。

任务设计：

- prompt 描述业务目标和证据字段，不规定工具顺序。
- 题目必须有搜索必要性，不能仅靠图片 OCR 或常识回答。
- frozen evidence 应覆盖所有必答字段，避免模型因证据缺口无限扩搜。
- 对 SFT，最终答案质量门禁应检查必备字段是否出现，而不是只看是否用了搜索工具。

门禁：

- user content 必须含 `image_url`。
- tools 定义包含 `image_search`、`web_search`、`image_zoom_in`。
- 实际轨迹必须使用 `web_search`。
- 实际轨迹必须使用 `image_search` 或 `image_zoom_in` 处理多模态输入。
- `meta.search_hops >= 1`。
- mock 覆盖率 100%。

### 4.3 §5.7 多模态搜索 RL

要求：

- 类型：RL。
- 数据量：50,000。
- 继承 5.6 工具和多模态要求。
- 必填 `answer_gt`、`model_query`。
- 答案必须客观可验证。
- 多跳搜索问题占比不低于 50%。
- 交付必须包含 verifier 和 mock。

任务设计：

- 题目必须需要图像线索和外部证据共同完成。
- 多跳题应要求至少两个以上事实维度，例如实体识别、别名、时间、地点、型号、来源交叉验证。
- `model_query.required_sources` 应列出必须引用的关键来源，防止无来源事实匹配。
- GT 推荐使用结构化事实 JSON 字符串，便于 verifier flatten 后逐项匹配。

当前门禁：

- `meta.search_hops >= 4`。
- tools 定义包含 `image_search`、`web_search`、`image_zoom_in`。
- 实际轨迹必须使用 `web_search`。
- 实际轨迹必须使用 `image_search` 或 `image_zoom_in`。
- `answer_gt`、`model_query` 必填。
- verifier 必须通过。
- mock 覆盖率 100%。

### 4.4 §5.8 工具调用泛化 SFT

要求：

- 类型：SFT。
- 数据量：500,000。
- 文本为主，部分多模态。
- 覆盖搜索、地图、电商、日程、天气、表格、代码、知识问答、设备控制等场景。
- 每个场景配置不同工具集和 scenario simulator。
- 重点训练模型何时调用、调用哪个工具、如何串联工具。
- 交付必须提供 mock。

设计重点：

- 不要求 verifier，但需要高质量最终答案和完整工具轨迹。
- 场景 simulator 必须稳定返回，避免 live API 波动。
- 工具组合、参数形状、成功/失败路径要多样化。

### 4.5 §5.9 工具调用泛化 RL

要求：

- 类型：RL。
- 数据量：40,000。
- 文本为主，部分多模态。
- 覆盖 1000+ 场景。
- 必填 `answer_gt`、`model_query`。
- 交付必须包含 verifier 和 mock。
- 重点验证任务完成、调用效率、参数正确性和停止时机。

情形分布：

| 情形 | 目标占比 |
|---|---:|
| 正常多工具串联 | 50% |
| 错误恢复 | 15% |
| 冗余调用识别 | 10% |
| 参数错误修正 | 10% |
| 工具失效应对 | 10% |
| 提前停止/停止时机 | 5% |

## 5. 批量架构

```text
Quota Planner
  ↓
Seed Agent
  ↓
Prompt Critic Agent
  ↓
Asset Agent
  ↓
GroundTruth Agent
  ↓
Toolset / Mock Scenario Builder
  ↓
Execution Workers
  ↓
Transform Gate
  ↓
Verifier / Mock Coverage Gate
  ↓
Diversity & Anti-pattern Gate
  ↓
Repair or Reject
  ↓
Batch Publisher
```

原则：

- 控制面负责规划、状态、并发、返修、统计和发布。
- 数据面负责真实模型调用、工具执行、raw 记录、mock 记录和转换。
- Execution Worker 不写交付 JSONL，只写 raw、mock_delta、assets 和 run report。
- Transform 和 gate 统一在 worker 后执行，避免并发竞态导致覆盖统计失真。

## 6. Agent 职责

### 6.1 Quota Planner

- 拆分分项数量、场景、语言、轮次、工具组合、多跳比例和反思比例。
- 只生成 quota slot，不生成用户 prompt。
- 控制 5.7 多跳占比、5.9 情形占比、5.5 operations 占比。

### 6.2 Seed Agent

- 生成自然、目标导向、非模板化用户请求。
- 不直接告诉模型工具步骤。
- 确保任务有工具必要性并能由当前工具集完成。
- 对多模态任务只描述视觉内容和目标，不写本地输入路径。

### 6.3 Prompt Critic Agent

检查：

- 是否模板化。
- 是否直接规定工具顺序。
- 是否缺少工具必要性。
- 是否存在不可验证终止目标。
- 是否把输入路径、driver 路径或内部 mock 信息写进用户请求。
- 是否可能诱导模型无限搜索或无限工具循环。

### 6.4 Asset Agent

- 为 5.5 准备可验证图像处理输入。
- 为 5.6/5.7 准备具备搜索必要性的图片、截图、表格、文档片段或视频帧。
- 记录素材 hash、来源、授权状态和包内目标路径。
- 不把素材路径注入用户 prompt。

### 6.5 GroundTruth Agent

仅服务 5.5、5.7、5.9：

- 生成唯一、明确、可验证的 GT。
- 生成 verifier 参数。
- 5.5 输出文件、尺寸、像素阈值等写入 JSON 字符串。
- 5.5 GT 不写 `output_path`；路径属于 pred 校验对象，不属于 GT。
- 5.7/5.9 结构化事实写成 JSON 字符串，除非 verifier 已升级为直接接受 object。

### 6.6 Toolset / Mock Builder

- 定义工具 schema、执行器和 simulator。
- frozen evidence 优先用于正式采集，live API 只用于证据调研或构建 fixture。
- mock key 为 `sha256(tool_name + json.dumps(arguments, sort_keys=True))`。
- 同一 request_hash 必须返回同一 response。
- 冲突 mock 进入 quarantine，不得合并入交付包。

### 6.7 Execution Worker

- 组装 system/user/tools。
- 调用真实模型。
- 执行 assistant 返回的 tool_use。
- 写回真实 tool_result。
- 循环直到自然 final 或达到 max_turns。
- 写 raw、mock_delta、assets 和执行日志。
- 不手改最终 JSONL。

### 6.8 Trajectory Critic / Repair Agent

Trajectory Critic 检查工具必要性、调用效率、证据完整性、停止时机和分项规则。  
Repair Agent 只修 TaskSpec、prompt seed、tool scenario、GT 或 mock，然后重跑真实执行；不得直接修 JSONL 通过 gate。

## 7. 数据模型

### 7.1 TaskSpec

```json
{
  "task_id": "5.7-zarya-timeline-000001",
  "section": "5.7",
  "target_batch": "batch_01",
  "quota_slot": "5.7.space_timeline.zh.multi_hop.4-6",
  "scene": "space_timeline",
  "language": "zh",
  "modality": "image_text",
  "difficulty": "medium",
  "expected_turn_bucket": "4-6",
  "reflection_required": false,
  "toolset_id": "search_image_web_zoom_v1",
  "asset_ids": ["zarya_module_panel_001"],
  "prompt_seed": "这张图里的航天器模块要放进一张 ISS 时间线卡片...",
  "answer_gt": "{\"module_name\":\"Zarya\",\"first_launch_date\":\"1998年11月20日\"}",
  "model_query": "{\"required_sources\":[\"mock://esa/iss/assembly/zarya-launch\"]}",
  "verifier_type": "script",
  "mock_policy": "frozen_curated"
}
```

### 7.2 状态机

```text
planned
  → claimed
  → seed_ready
  → prompt_checked
  → assets_ready
  → gt_ready
  → toolset_ready
  → executing
  → raw_done
  → transformed
  → schema_checked
  → verifier_checked
  → mock_checked
  → diversity_checked
  → accepted
```

失败分支：

```text
gate_failed → repair_pending → retrying → rejected
execution_failed → retrying 或 rejected
failed_finalization → repair_pending 或 rejected
mock_conflict → quarantine
```

### 7.3 运行目录

每个 task 使用独立目录：

```text
runs/
  batch_01/
    task_id/
      task_spec.json
      raw_turn.json
      raw_http/
      mock_delta.jsonl
      assets/
      transformed.jsonl
      gate_report.json
```

隔离要求：

- Python 输出文件名必须唯一或位于 task workspace。
- mock_delta 不直接写全局 mock。
- raw、assets、mock_delta、gate_report 都带 task_id 和 run_id。
- 任务成功后由 publisher 重写路径并复制到 delivery 包。

## 8. 执行链路

```text
TaskSpec
  ↓
组装 system/user/tools
  ↓
调用模型 /v1/messages
  ↓
assistant 返回 tool_use
  ↓
本地工具执行器执行
  ↓
写 mock_delta
  ↓
追加 tool_result
  ↓
继续调用模型
  ↓
模型自然 final
  ↓
写 raw_turn.json
  ↓
转换 JSONL
  ↓
verifier / mock coverage / schema gate
```

5.5 执行：

- 暴露单一 `python` 工具。
- 首条 user message 包含 image block。
- driver 准备 runtime 图片副本。
- 任务设计要有明确量化自检，不依赖模型主观判断。

5.6/5.7 执行：

- 暴露 `image_search`、`web_search`、`image_zoom_in`。
- 正式采集默认 frozen evidence。
- 每个外部工具 response 写入 mock_delta。
- 5.7 额外注入 sidecar 并跑 verifier。

## 9. 质量门禁

### 9.1 单条门禁

每条轨迹必须通过：

1. JSON 可解析。
2. §4.1 schema 合法。
3. `tool_call_id` 配对。
4. tools 定义完整。
5. 最后一条消息是自然 assistant final。
6. 无采集控制型 user 消息。
7. 无敏感信息。
8. 分项规则通过。
9. 5.5/5.7/5.9 verifier 通过。
10. 5.6/5.7/5.8/5.9 mock 覆盖 100%。
11. Trajectory Critic 通过。
12. 交付 JSONL meta、manifest 和 report 不含 `source`、`model`、`source_run`、`source_raw` 等生产链路字段。
13. verifier 负向测试通过，不存在恒真。

仓库级交付检查：

```bash
.venv312/bin/python scripts/check_delivery_quality.py --delivery-root delivery
```

该脚本遍历所有 `delivery/*/batch*.jsonl` 及其 package manifest/report，统一检查：

- 所有交付 JSONL meta 不含生产链路字段。
- 所有交付 manifest/report 不含采集链路路径和模型标识。
- 所有带 `verifier/` 的交付包正向样本通过。
- 所有带 `verifier/` 的交付包负向样本失败。
- 所有带 `mock/` 的交付包 mock coverage 100%。

### 9.2 批次门禁

- Schema 合法率 100%。
- RL verifier 全量运行，目标通过率不低于 95%。
- mock 覆盖率 100%。
- 内容合格率预估不低于 95%。
- 中文占比不超过 40%，除非批次明确要求中文。
- 同一分项工具组合类型不少于 20 种。
- 5.7 多跳比例不低于 50%。
- 5.5/5.9 反思轨迹 5%-10%。
- 5.9 场景数不少于 1000。
- 不触发模板化、工具序列重复、结构雷同等反模式阈值。

## 10. 反模式检测

### 10.1 Query 模板

提取用户 query，替换实体、数字、日期、地名、商品名为占位符，生成句式 hash。同一分项同模板超过 30% 时阻断批次。

### 10.2 工具序列

抽象工具名序列和参数形状序列：

```text
image_search > image_zoom_in > web_search > web_search > final
img_idx > bbox,label > query > query
```

同一分项完全相同工具序列超过 50% 时阻断批次。

### 10.3 行为结构

抽象行为结构，例如：

```text
observe_image → identify_entity → search_fact → cross_check_source → summarize
```

跨领域结构雷同度超过 60% 时阻断批次。

## 11. Mock 设计

mock 行格式：

```json
{
  "request_hash": "sha256(tool_name + json.dumps(arguments, sort_keys=True))",
  "tool_name": "web_search",
  "request": {"query": "example"},
  "response": {"results": []}
}
```

要求：

- 回放接口：`POST /mock/<tool_name>`，body 为 `{"arguments": {...}}`。
- 未命中返回 404 和 request_hash。
- `mock_server.py` 和 `check_mock_coverage.py` 随交付包提供。
- 交付前必须运行包内 coverage 脚本。
- coverage 输出中 `miss=0` 且 `_missing_mocks.jsonl` 为空。

## 12. Verifier 设计

统一接口：

```python
def verify(pred: str, answer_gt: str, model_query: str) -> dict:
    return {"pass": True, "score": 1.0, "reason": ""}
```

类型：

- `exact_match`：数值、日期、枚举、ID。
- `script`：图像尺寸、文件存在、像素差异、结构化文件输出。
- `model_judge`：开放式回答；必须固定 judge prompt 并做位置偏差校准。

当前策略：

- 5.5 使用 `script` verifier。
- 5.5 verifier 只能从 pred 抽取输出路径；`answer_gt/model_query` 只提供尺寸、检查项和阈值。
- 5.7 使用结构化 fact flatten + required_sources 检查。
- 5.9 优先 exact/rule verifier，开放任务再使用校准后的 model_judge。
- 所有 verifier 都必须纳入 `scripts/check_delivery_quality.py` 的正负向测试矩阵。

## 13. 交付包结构

当前包命名和文件结构：

```text
delivery/
  5.5_python_mm_rl/
    batch_01.jsonl
    manifest.json
    report_batch_01.md
    assets/
      inputs/
      outputs/
    verifier/
      verifier_5_5.py

  5.6_search_sft/
    batch_01.jsonl
    manifest.json
    report_batch_01.md
    assets/
      inputs/
    mock/
      mock_responses.jsonl
      mock_server.py
      check_mock_coverage.py
      _missing_mocks.jsonl

  5.7_search_rl/
    batch_01.jsonl
    manifest.json
    report_batch_01.md
    assets/
      inputs/
    mock/
      mock_responses.jsonl
      mock_server.py
      check_mock_coverage.py
      _missing_mocks.jsonl
    verifier/
      verifier_5_7.py
```

发布规则：

- package 内 JSONL 只引用 package 内相对路径。
- package 内 JSONL meta 不包含 `source`、`model`、`collection_run`、`delivery_package`。
- package 内 manifest/report 不包含 `source_run`、`source_raw`、`model`、`claude-opus-*`、`claude-code-capture` 等采集来源或模型标识。
- `_missing_mocks.jsonl` 可以随包保留，但必须为空。
- manifest 只记录交付包内可公开的结构化信息，例如 package、section、batch、sample_count、uuid、turn_count、tools_used、validation、files 和 notes。
- report 必须列出验收命令输出摘要。
- 重新打包前删除旧分项目录，避免旧资产残留。
- 发布前必须运行 `scripts/check_delivery_quality.py`，不能只对单个样例做局部检查。

## 14. 当前仓库实现状态

已具备：

- 采集 driver：
  - `capture/run_python_tool_task.py`
  - `capture/run_search_tool_task.py`
  - `capture/run_general_tool_task.py`
- 转换器：
  - `transform/to_section_5_5.py`
  - `transform/to_section_5_6.py`
  - `transform/to_section_5_7.py`
  - `transform/to_section_5_8.py`
  - `transform/to_section_5_9.py`
- verifier：
  - `verifier/verifier_5_5.py`
  - `verifier/verifier_5_7.py`
  - `verifier/verifier_5_9.py`
- mock 工具：
  - `mock/mock_server.py`
  - `mock/check_mock_coverage.py`
- 全局交付检查：
  - `scripts/check_delivery_quality.py`
- 最新交付包：
  - `delivery/5.5_python_mm_rl`
  - `delivery/5.6_search_sft`
  - `delivery/5.7_search_rl`

仍需产品化：

- 任务池和状态机。
- 并发 worker。
- per-task workspace。
- mock_delta merge job。
- quota planner。
- toolset registry。
- scenario simulator。
- batch publisher。
- 批次级多样性和反模式扫描。
- Repair Agent。

## 15. 下一步实现清单

建议新增：

```text
orchestrator/
  task_spec.py
  task_store.py
  quota_planner.py
  worker.py
  gates.py
  mock_merge.py
  publisher.py
  report.py
  agents/
    seed_agent.py
    prompt_critic.py
    gt_agent.py
    trajectory_critic.py
    repair_agent.py
  toolsets/
    registry.json
    simulators/
```

最小可运行命令：

```bash
.venv312/bin/python orchestrator/quota_planner.py --section 5.6 --count 100 --out out/tasks.sqlite
.venv312/bin/python orchestrator/worker.py --db out/tasks.sqlite --concurrency 4
.venv312/bin/python orchestrator/mock_merge.py --runs runs/batch_01 --out out/batch_01/mock
.venv312/bin/python orchestrator/publisher.py --runs runs/batch_01 --delivery delivery
.venv312/bin/python orchestrator/report.py --db out/tasks.sqlite --runs runs/batch_01
```

`start.sh` 后续可增加：

```bash
./start.sh collect --section 5.6 --count 100
./start.sh collect-all --batch batch_01
```

实现优先级：

1. per-task workspace 和 publisher，解决路径、资产和交付包一致性。
2. gates.py，统一封装 transform、verifier、mock coverage。
3. task_store + worker，支持多任务并发采集。
4. quota_planner + seed/prompt critic，保证任务数量、分布和多样性。
5. mock_merge + scenario simulator，支撑大规模 5.6/5.7/5.8/5.9。
