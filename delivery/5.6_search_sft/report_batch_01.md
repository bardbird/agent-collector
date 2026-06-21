# §5.6 多模态搜索 SFT 交付报告

## 样本

- package: `5.6_search_sft`
- batch: `batch_01.jsonl`
- uuid: `c2b9476c-b83c-486c-8213-1584b1b7c813`
- turn_count: `4`
- tools_used: `image_search, web_search`

## 验收

- transform accepted=1 rejected=0
- mock coverage total=8 hit=8 miss=0 rate=100.0%
- delivery package production metadata cleaned

## 文件

- `batch_01.jsonl`
- `assets/inputs/apollo_columbia_exhibit_001.png`
- `mock/mock_responses.jsonl`
- `mock/mock_server.py`
- `mock/check_mock_coverage.py`

## 说明

- turn_count=4
- search_hops=8
- evidence_mode=frozen
