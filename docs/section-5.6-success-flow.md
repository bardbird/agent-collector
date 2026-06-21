# §5.6 多模态搜索 SFT 成功采集流程

本文只记录 2026-06-21 已验证通过的正式流程。历史调试命令、旧 raw 路径、旧 `max-turns=8` 示例和旧 mock 统计不再保留，避免后续误用。

## 硬规则

- 图片必须作为首条 user message 的真实 `image` content block 输入。
- 用户 prompt 只描述任务目标，不点名工具、不规定工具顺序、不写本地图片路径。
- 搜索工具调用必须由模型自主产生。
- 工具返回必须固化到 mock DB，交付和验收不得依赖 live 搜索结果。
- §5.6 是 SFT，不需要 `answer_gt`、`model_query` 或 verifier。
- 覆盖检查必须在转换完成后单独运行，不能和转换并行。

## 成功样本

```text
run: formal_rerun_5_5_5_6_5_7
raw: out/formal_rerun_5_5_5_6_5_7/in_5_6/ced8d95d666c4b32.json
jsonl: out/formal_rerun_5_5_5_6_5_7/jsonl/5_6/5_6.jsonl
mock: out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_6.jsonl
input: delivery/5.6_search_sft/assets/inputs/apollo_columbia_exhibit_001.png
turn_count: 4
search_hops: 8
tools_used: image_search, web_search
```

任务目标：根据博物馆展牌图片识别 Apollo 11 Command Module Columbia，并核对正式名称、编号或馆藏号、所属机构、任务角色和当前展陈背景，最终输出带证据表的中文科普卡片。

## 采集命令

先启动代理：

```bash
./start.sh -d
```

正式采集：

```bash
.venv312/bin/python capture/run_search_tool_task.py \
  --image delivery/5.6_search_sft/assets/inputs/apollo_columbia_exhibit_001.png \
  --out out/formal_rerun_5_5_5_6_5_7/in_5_6 \
  --mock-db out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_6.jsonl \
  --scenario apollo \
  --evidence-mode frozen \
  --max-turns 100 \
  --prompt '这张博物馆展牌图要做成一张可发布的中文科普卡片。请先识别图片中的展品名称和关键编号，再核对资料，不要只凭印象回答。最终回答请包含：搜索意图判断、检索词改写记录、证据表，以及完整中文说明。证据表至少覆盖展品正式名称、编号或馆藏号、所属机构、它在 Apollo 11 中的任务角色、当前展陈或展示背景；每个字段都要带来源标题或 URL。'
```

本次使用 `--evidence-mode frozen`。live 搜索只适合补充证据源调研，不作为正式采集默认路径。

## 工具与 Mock

`capture/run_search_tool_task.py` 暴露的工具：

```text
image_search
web_search
image_zoom_in
```

本次模型实际调用：

```text
image_search {"img_idx": 0}
web_search {"query": "Apollo 11 Command Module Columbia CM-107 catalog A19700102000"}
web_search {"query": "Smithsonian \"Destination Moon\" exhibition Apollo 11 Columbia"}
web_search {"query": "Apollo 11 Command Module Columbia mission role specifications"}
web_search {"query": "\"Destination Moon\" gallery Smithsonian National Air and Space Museum 2022 opening"}
web_search {"query": "Apollo 11 指令舱 哥伦比亚号 CM-107 史密森尼"}
web_search {"query": "Apollo 11 Columbia command module manufacturer North American Rockwell weight dimensions"}
web_search {"query": "Michael Collins named Columbia command module Apollo 11"}
```

mock DB 每行必须与 JSONL 中的 tool_call arguments 一一命中：

```text
out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_6.jsonl
```

## 转换与验收

转换：

```bash
.venv312/bin/python transform/to_section_5_6.py \
  --in out/formal_rerun_5_5_5_6_5_7/in_5_6 \
  --out out/formal_rerun_5_5_5_6_5_7/jsonl/5_6 \
  --images out/formal_rerun_5_5_5_6_5_7/images/5_6
```

通过结果：

```text
[5.6] {'accepted': 1, 'rejected': 0, 'total': 1}
```

覆盖检查：

```bash
.venv312/bin/python mock/check_mock_coverage.py \
  --jsonl-root out/formal_rerun_5_5_5_6_5_7/jsonl/5_6 \
  --db out/formal_rerun_5_5_5_6_5_7/mock/mock_responses_5_6.jsonl \
  --missing out/formal_rerun_5_5_5_6_5_7/mock/_missing_5_6.jsonl
```

覆盖结果：

```text
[coverage] total=8 hit=8 miss=0 skipped(no-mock-needed)=0 rate=100.0%
out/formal_rerun_5_5_5_6_5_7/mock/_missing_5_6.jsonl is empty
```

## 门禁要点

`transform/to_section_5_6.py` 至少检查：

- user content 包含 `image_url`。
- tools 定义包含 `image_search`、`web_search`、`image_zoom_in`。
- 实际轨迹使用 `web_search`。
- 实际轨迹使用 `image_search` 或 `image_zoom_in` 处理多模态输入。
- `meta.search_hops >= 1`。
- 最终 answer 包含搜索意图、检索词改写、证据、最终答案等信号。
- 最终 answer 覆盖正式名称、编号、机构、任务角色、展陈背景等字段。

## 常见错误

- 把输入图片路径写进 prompt，会把样本污染成路径驱动任务。
- 让模型直接写最终答案而不触发搜索工具，会被门禁拒收。
- 用 live 搜索作为正式默认路径，会引入不可控的搜索质量波动。
- 转换和 mock 覆盖并行跑，可能得到 `total=0` 的无效覆盖结果。
- 5.6 不应添加 `answer_gt`、`model_query` 或 verifier；那是 RL 条目的做法。
