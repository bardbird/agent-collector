# 5.6 多模态搜索 SFT 样例交付自测报告

## 样例场景
- 场景：博物馆展牌图文检索问答
- 输入：生成的 Apollo 11 Command Module Columbia 展牌图片
- 目标：识别展品，核对公开资料，输出搜索意图、检索词改写、证据整合和最终中文说明
- 采集方式：通过 Claude Code/Anthropic messages 代理链路真实采集，raw 来源 `out/raw_turns/7df5baea1316a3f3.json`

## 搜索执行说明
- `web_search`：采集阶段真实请求 `wikipedia_api + duckduckgo_html`，响应固化进 `mock/mock_responses.jsonl`
- `image_zoom_in`：本地图片局部读取工具，响应固化进 `mock/mock_responses.jsonl`
- 交付阶段不再访问外网，统一通过 mock 回放

## 交付内容
- `batch_01.jsonl`：1 条 JSONL，每行一个 §4.1 JSON 对象
- `assets/inputs/apollo_columbia_exhibit_001.png`：样例输入图片
- `mock/mock_responses.jsonl`：8 条工具调用固化响应
- `mock/mock_server.py`：本地 mock 回放服务
- `mock/check_mock_coverage.py`：mock 覆盖率检查脚本
- `manifest.json`：文件清单与 SHA256

## 自测结果
- 转换：accepted=1, rejected=0
- Schema：§4.1 校验无错误
- 工具调用配对数：8
- 工具定义：包含 image_search / web_search / image_zoom_in
- 实际使用工具：image_zoom_in / web_search
- Mock 覆盖：total=8, hit=8, miss=0, rate=100.0%
- Mock 回放：`POST /mock/web_search` 返回 200
