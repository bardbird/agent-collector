# §5.7 多模态搜索 RL 成功采集流程

本文记录 §5.7 多模态搜索 RL 的一次正式跑通流程。核心原则：

- 输入图片必须作为真实 image content block 进入对话，不能把本地图片路径写进 prompt。
- 搜索、局部放大、证据整合由模型自主完成，采集器只执行模型返回的 tool_use。
- 5.7 是 RL 样本，必须有同名 sidecar 注入 `answer_gt` 和 `model_query`。
- 多跳门槛按实际搜索工具调用计数，本项目 gate 要求 `search_hops >= 4`。
- 搜索类外部返回必须写入 mock DB，并在转换后做 100% 覆盖检查。

## 成功案例

任务题材：ISS 时间线卡片中的 Zarya/FGB 模块核验。

输入图片：

```text
delivery/5.7_search_rl/assets/inputs/zarya_module_panel_001.png
```

用户目标：

```text
这张图里的航天器模块要放进一张 ISS 时间线卡片。请先识别图片线索，再通过多跳资料核对，最终给出可验证结论。必须覆盖并交叉核对：模块正式名称、别名或缩写、首次发射日期、运载火箭型号、发射场、它为什么属于 ISS 时间线起点。请展示搜索意图、检索词改写、证据链整合，并在最终答案中给出四个客观字段和每个字段的来源标题或 URL。
```

## 2026-06-21 正式重跑记录

采集命令：

```bash
.venv312/bin/python capture/run_search_tool_task.py \
  --image delivery/5.7_search_rl/assets/inputs/zarya_module_panel_001.png \
  --out out/formal_rerun_5_5_5_6_5_7/in_5_7 \
  --mock-db out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_7.jsonl \
  --scenario zarya \
  --evidence-mode frozen \
  --max-turns 100 \
  --prompt '这张图里的航天器模块要放进一张 ISS 时间线卡片。请先识别图片线索，再通过多跳资料核对，最终给出可验证结论。必须覆盖并交叉核对：模块正式名称、别名或缩写、首次发射日期、运载火箭型号、发射场、它为什么属于 ISS 时间线起点。请展示搜索意图、检索词改写、证据链整合，并在最终答案中给出四个客观字段和每个字段的来源标题或 URL。'
```

成功样本：

```text
raw: out/formal_rerun_5_5_5_6_5_7/in_5_7/95f8307f091341a0.json
sidecar: out/formal_rerun_5_5_5_6_5_7/in_5_7/95f8307f091341a0.gt.json
jsonl: out/formal_rerun_5_5_5_6_5_7/jsonl/5_7/5_7.jsonl
mock: out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_7.jsonl
turn_count: 4
search_hops: 5
tools_used: image_search, image_zoom_in, web_search
```

实际工具链：

```text
image_search
image_zoom_in
web_search
web_search
web_search
```

## Sidecar 标注

同名 sidecar 必须放在 raw 文件旁边：

```text
out/formal_rerun_5_5_5_6_5_7/in_5_7/95f8307f091341a0.gt.json
```

当前 `verifier/verifier_5_7.py` 期望 `answer_gt` 和 `model_query` 为字符串。若要表达结构化字段，应写成 JSON 字符串，而不是直接写 JSON object：

```json
{
  "answer_gt": "{\"module_name\":\"Zarya\",\"alias\":\"FGB\",\"full_alias\":\"Functional Cargo Block\",\"first_launch_date\":\"1998年11月20日\",\"launch_vehicle\":\"Proton-K\",\"launch_site\":\"Baikonur Cosmodrome\"}",
  "model_query": "{\"task\":\"Verify that the answer identifies Zarya/FGB as the ISS module and gives the first launch date, launch vehicle, and launch site.\",\"required_sources\":[\"mock://nasa/iss/zarya-functional-cargo-block\",\"mock://esa/iss/assembly/zarya-launch\",\"mock://roscosmos/iss/zarya-baikonur-proton-k\"]}",
  "meta": {
    "verifier_type": "script",
    "domain": "多模态搜索验证"
  }
}
```

## 转换与校验

转换：

```bash
.venv312/bin/python transform/to_section_5_7.py \
  --in out/formal_rerun_5_5_5_6_5_7/in_5_7 \
  --out out/formal_rerun_5_5_5_6_5_7/jsonl/5_7 \
  --images out/formal_rerun_5_5_5_6_5_7/images/5_7
```

转换结果：

```text
[5.7] {'accepted': 1, 'rejected': 0, 'total': 1}
```

verifier 结果：

```text
verifier_5_7: pass=True, score=1.0
reason: all 6 answer_gt facts matched
```

mock 覆盖检查：

```bash
.venv312/bin/python mock/check_mock_coverage.py \
  --jsonl-root out/formal_rerun_5_5_5_6_5_7/jsonl/5_7 \
  --db out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_7.jsonl \
  --missing out/formal_rerun_5_5_5_6_5_7/mock/_missing_5_7.jsonl
```

覆盖结果：

```text
[coverage] total=5 hit=5 miss=0 skipped(no-mock-needed)=0 rate=100.0%
```

## 常见错误

- 错误：`answer_gt` 直接写 object。
  结果：现有 verifier 会收到 dict 并抛出类型异常。当前做法是写 JSON 字符串。

- 错误：搜索轮数不足。
  结果：`transform/to_section_5_7.py` 会因 `meta.search_hops < 4` 拒收。

- 错误：转换和覆盖检查并行跑。
  结果：覆盖脚本可能在 JSONL 尚未落盘时返回 `total=0`，这是无效验收结果。必须转换完成后单独运行覆盖检查。

- 错误：把图片路径写进用户 prompt。
  结果：样本退化为路径驱动任务，不是多模态输入。图片只能作为 message image block。
