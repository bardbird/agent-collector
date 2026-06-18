# §5.6 多模态搜索 SFT 成功采集流程

本文记录一次已经跑通的 §5.6 样品流程，供后续复用。核心原则：

- 真实模型请求必须经过本地代理，保留 `out/raw_http/` 和 `out/raw_turns/` 证据。
- 输入图片必须作为真实 image content block 进入对话。
- 用户 query 只描述目标，不点名工具、不规定工具顺序。
- 工具返回必须固化到 mock 包，交付环境不依赖外部搜索 API。
- 5.6 是 SFT，不交 verifier；必须交 mock 包。

## 成功案例

任务题材：博物馆展牌图文检索问答。

输入图片：

```text
samples/assets/inputs/apollo_columbia_exhibit_001.png
```

用户目标：

```text
这张博物馆展牌图要配一条科普短帖说明。图片里的编号和文字比较关键，不能只凭印象回答。请识别展品、核对公开资料，并在最终回答中保留你的搜索意图判断、检索词改写记录、证据来源整合，以及一段可直接引用的中文说明：它是什么、在 Apollo 11 中承担什么角色、现在应如何描述它的展陈背景。
```

这条 query 没有写 `image_zoom_in` / `web_search` / `image_search`，只提出业务目标和交付质量要求。模型自然选择了局部放大和多轮搜索。

## 正确采集链路

1. 生成输入图片：

```bash
python3 samples/generate_inputs.py
```

2. 启动 recorder 代理：

```bash
./start.sh -d
```

3. 通过 `capture/run_search_tool_task.py` 发起模型请求：

```bash
python3 capture/run_search_tool_task.py \
  --image samples/assets/inputs/apollo_columbia_exhibit_001.png \
  --prompt '这张博物馆展牌图要配一条科普短帖说明。图片里的编号和文字比较关键，不能只凭印象回答。请识别展品、核对公开资料，并在最终回答中保留你的搜索意图判断、检索词改写记录、证据来源整合，以及一段可直接引用的中文说明：它是什么、在 Apollo 11 中承担什么角色、现在应如何描述它的展陈背景。' \
  --max-turns 8
```

4. 停止代理落盘：

```bash
./start.sh stop
```

成功后应能看到：

```text
out/raw_http/<task>_turn*.request.txt
out/raw_http/<task>_turn*.response.txt
out/raw_turns/<task>.json
mock/mock_responses.jsonl
```

本次成功 raw：

```text
out/raw_turns/7df5baea1316a3f3.json
```

## 工具与 mock

`capture/run_search_tool_task.py` 暴露 §5.6 标准搜索工具：

```text
image_search
web_search
image_zoom_in
```

脚本只负责执行模型真实返回的 tool_use，并把每个请求/响应写入：

```text
mock/mock_responses.jsonl
```

mock 每行格式遵循 docx §C.2：

```json
{
  "request_hash": "sha256(tool_name + json.dumps(arguments, sort_keys=True))",
  "tool_name": "web_search",
  "request": {"query": "..."},
  "response": {"results": []}
}
```

注意：mock response 的含义是“本条真实工具调用在交付回放环境中的固定外部 API 返回”。它不是最终答案，也不是手写轨迹；它必须与 JSONL 里的 tool_call arguments 一一命中。

## 转换与质量门禁

转换：

```bash
python3 transform/to_section_5_6.py \
  --in out/raw_turns \
  --out out/jsonl/5_6 \
  --images out/images/5_6
```

成功结果：

```text
[5.6] {'accepted': 1, 'rejected': 0, 'total': 1}
```

`transform/to_section_5_6.py` 的门禁：

- user content 必须包含 `image_url`。
- tools 定义必须包含 `image_search` / `web_search` / `image_zoom_in`。
- 实际轨迹必须使用搜索相关工具，且必须使用 `web_search`。
- `meta.search_hops >= 1`。
- 最终 assistant 回答必须包含搜索意图、检索词改写、证据整合、最终答案等信号。

共用轮次统计按“一个 tool_call 与一个 tool response 配对”计数。本次样例工具调用配对数为 6。

## Mock 覆盖与回放

覆盖检查：

```bash
python3 mock/check_mock_coverage.py \
  --jsonl-root out/jsonl/5_6 \
  --db mock/mock_responses.jsonl \
  --missing mock/_missing_mocks.jsonl
```

成功结果：

```text
[coverage] total=6 hit=6 miss=0 skipped(no-mock-needed)=0 rate=100.0%
```

mock 回放服务：

```bash
python3 mock/mock_server.py --data mock/mock_responses.jsonl --port 18081
```

接口：

```text
POST /mock/<tool_name>
body: {"arguments": {...}}
```

本次实际回放检查：`POST /mock/image_zoom_in` 返回 200。

## 单项交付目录

只交付 5.6 单项时，配套文件放在 5.6 目录内，做成自包含包：

```text
delivery/5.6_search_sft/
  batch_01.jsonl
  report_batch_01.md
  manifest.json
  assets/
    inputs/apollo_columbia_exhibit_001.png
  mock/
    mock_responses.jsonl
    mock_server.py
    check_mock_coverage.py
```

JSONL 内图片路径必须指向本目录：

```json
"image_url": {
  "url": "assets/inputs/apollo_columbia_exhibit_001.png"
}
```

5.6 是 SFT，不放 `answer_gt`、`model_query`，也不放 verifier。

## 本次已验证交付

```text
delivery/5.6_search_sft/batch_01.jsonl
delivery/5.6_search_sft/assets/inputs/apollo_columbia_exhibit_001.png
delivery/5.6_search_sft/mock/mock_responses.jsonl
delivery/5.6_search_sft/mock/mock_server.py
delivery/5.6_search_sft/mock/check_mock_coverage.py
delivery/5.6_search_sft/manifest.json
delivery/5.6_search_sft/report_batch_01.md
```

自测结果：

```text
转换 accepted=1 rejected=0
§4.1 schema 无错误
工具调用配对数 6
mock 覆盖 total=6 hit=6 miss=0 rate=100.0%
mock_server 实际 POST 回放返回 200
```
