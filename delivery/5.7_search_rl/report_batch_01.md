# 5.7 多模态搜索 RL 样例交付自测报告

## 样例场景
- 场景：ISS 时间线卡片事实核验
- 输入：Zarya/FGB 航天器模块展牌图 `assets/inputs/zarya_module_panel_001.png`
- 目标：核对模块正式名称、首次发射日期、运载火箭型号和发射场
- answer_gt：`1998年11月20日，Proton-K火箭，拜科努尔航天发射场`

## 交付内容
- `batch_01.jsonl`：1 条 §4.1 JSONL，含 `answer_gt` 和 `model_query`
- `assets/inputs/zarya_module_panel_001.png`：多模态输入图片
- `mock/mock_responses.jsonl`：4 条外部工具调用固化响应
- `mock/mock_server.py`：本地 mock 回放服务
- `mock/check_mock_coverage.py`：mock 覆盖率检查脚本
- `verifier/verifier_5_7.py`：RL 自动验证脚本
- `manifest.json`：交付文件清单与 SHA256

## 自测结果
- Schema：§4.1 校验无错误
- 工具调用配对数：4
- `meta.search_hops`：4
- 实际工具：image_search / web_search
- Verifier：`pass=True, score=1.0`
- Mock 覆盖：`total=4, hit=4, miss=0, rate=100.0%`

## 复验命令

```bash
python3 delivery/5.7_search_rl/mock/check_mock_coverage.py \
  --jsonl-root delivery/5.7_search_rl \
  --db delivery/5.7_search_rl/mock/mock_responses.jsonl \
  --missing /tmp/poc_5_7_missing.jsonl
```
