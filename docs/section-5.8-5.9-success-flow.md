# §5.8 / §5.9 工具调用泛化成功采集流程

本文记录已经跑通的 §5.8 SFT 和 §5.9 RL 样品流程，供后续复用。核心原则：

- 工具由采集器通过 Anthropic `tools` 字段暴露给模型。
- 模型必须真实返回 `tool_use`；工具轨迹不手写。
- 每个工具调用的 request/response 都写入 `mock/mock_responses.jsonl`。
- 交付包必须自包含 JSONL、mock 包、自测报告和 manifest。
- §5.9 是 RL，必须额外交 `answer_gt`、`model_query` 和 verifier。

## 采集器

本次使用：

```text
capture/run_general_tool_task.py
```

它负责：

- 按 `--section 5.8` 或 `--section 5.9` 选择工具集。
- 把工具 schema 放入 `/v1/messages` 请求的 `tools` 字段。
- 执行模型真实返回的 `tool_use`。
- 把执行结果作为 `tool_result` 继续回填给模型。
- 同步写入 `mock/mock_responses.jsonl`。
- 写出 recorder-compatible raw，供分项转换器处理。

## §5.8 成功案例

场景：多模态活动安排，混合工具链。

输入图片：

```text
samples/assets/inputs/event_venue.png
```

用户目标：

```text
周五下午上海客户共创会预计 32 人，图里有室外草坪和室内厅两个选择。帮我做一个实际安排：如果天气不适合户外就改室内，安排进日历，并给参会同事发一封简短通知。
```

实际工具链：

```text
venue_options_read
weather_query
room_availability
calendar_create
email_send
```

采集命令：

```bash
./start.sh -d

python3 capture/run_general_tool_task.py \
  --section 5.8 \
  --image samples/assets/inputs/event_venue.png \
  --prompt '周五下午上海客户共创会预计 32 人，图里有室外草坪和室内厅两个选择。帮我做一个实际安排：如果天气不适合户外就改室内，安排进日历，并给参会同事发一封简短通知。' \
  --max-turns 8

./start.sh stop
```

转换：

```bash
python3 transform/to_section_5_8.py \
  --in out/raw_turns \
  --out out/jsonl/5_8 \
  --images out/images/5_8
```

成功结果：

```text
[5.8] {'accepted': 1, 'rejected': 0, 'total': 1}
```

mock 覆盖：

```bash
python3 mock/check_mock_coverage.py \
  --jsonl-root out/jsonl/5_8 \
  --db mock/mock_responses.jsonl \
  --missing mock/_missing_mocks.jsonl
```

成功结果：

```text
total=5 hit=5 miss=0 rate=100.0%
```

交付目录：

```text
delivery/5.8_tool_generalization_sft/
  batch_01.jsonl
  manifest.json
  report_batch_01.md
  assets/
    inputs/event_venue.png
  mock/
    mock_responses.jsonl
    mock_server.py
    check_mock_coverage.py
```

§5.8 是 SFT，不放 `answer_gt`、`model_query`，不放 verifier。

## §5.9 成功案例

场景：电商比价报价，正常多工具串联。

用户目标：

```text
我要给上海办公室买一副 AuroraBuds Pro 3，本周内能送到，直接给我最低到手价和对应 SKU。不要下单，只要报价。
```

实际工具链：

```text
product_search
inventory_check
coupon_apply
price_compare
order_quote
```

采集命令：

```bash
./start.sh -d

python3 capture/run_general_tool_task.py \
  --section 5.9 \
  --prompt '我要给上海办公室买一副 AuroraBuds Pro 3，本周内能送到，直接给我最低到手价和对应 SKU。不要下单，只要报价。' \
  --max-turns 8

./start.sh stop
```

RL sidecar：

```text
out/raw_turns/<task>.gt.json
```

本次字段：

```json
{
  "answer_gt": "1179",
  "model_query": "判断模型最终报价是否选择 SKU ABP3-MALL-001，且最低到手价为 1179 元，并明确没有下单。回答 YES 或 NO。",
  "meta": {
    "scene": "ecommerce",
    "situation": "normal_chain",
    "verifier_type": "exact_match",
    "is_reflection": false
  }
}
```

转换：

```bash
python3 transform/to_section_5_9.py \
  --in out/raw_turns \
  --out out/jsonl/5_9 \
  --images out/images/5_9
```

成功结果：

```text
[5.9] {'accepted': 1, 'rejected': 0, 'total': 1}
```

verifier：

```text
verifier/verifier_5_9.py
```

本次自测：

```text
pass=True
score=1.0
reason=contains numeric gt with thousands separator
```

mock 覆盖：

```text
total=9 hit=9 miss=0 rate=100.0%
```

交付目录：

```text
delivery/5.9_tool_generalization_rl/
  batch_01.jsonl
  manifest.json
  report_batch_01.md
  mock/
    mock_responses.jsonl
    mock_server.py
    check_mock_coverage.py
  verifier/
    verifier_5_9.py
```

## 已踩坑

### 1. 参数类型要容错

模型可能把复杂参数传成 JSON 字符串。例如 `price_compare.candidates` 曾被传成：

```json
"[{\"sku\":\"ABP3-MALL-001\", ...}]"
```

工具执行器要能解析字符串 JSON，不能直接假设是 array。

### 2. 工具响应必须自洽

5.9 第一次采集时，`price_compare` 选出 `1179`，但 `order_quote` 返回了另一个 SKU 的 `1207`，导致最终答案和工具证据冲突。修复方式是让 `order_quote` 按 SKU 返回对应报价，不允许跨 SKU 混用报价单号。

### 3. verifier 要支持展示格式

最终答案可能写成 `¥1,179`，`answer_gt` 是 `1179`。`verifier_5_9.py` 已支持千分位数字匹配。

### 4. 清理生成垃圾

运行 verifier 会生成 `__pycache__`，打包前必须删除：

```bash
find delivery -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store'
```

## 最终自检命令

```bash
python3 delivery/5.8_tool_generalization_sft/mock/check_mock_coverage.py \
  --jsonl-root delivery/5.8_tool_generalization_sft \
  --db delivery/5.8_tool_generalization_sft/mock/mock_responses.jsonl \
  --missing /tmp/agent_collector_5_8_missing.jsonl

python3 delivery/5.9_tool_generalization_rl/mock/check_mock_coverage.py \
  --jsonl-root delivery/5.9_tool_generalization_rl \
  --db delivery/5.9_tool_generalization_rl/mock/mock_responses.jsonl \
  --missing /tmp/agent_collector_5_9_missing.jsonl
```

mock server 回放示例：

```bash
python3 delivery/5.9_tool_generalization_rl/mock/mock_server.py \
  --data delivery/5.9_tool_generalization_rl/mock/mock_responses.jsonl \
  --port 18084
```

回放接口：

```text
POST /mock/<tool_name>
body: {"arguments": {...}}
```
