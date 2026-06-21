# 5.9 工具调用泛化 RL 样例交付自测报告

## 样例场景
- 场景：电商比价报价
- 目标：查商品、过滤库存、试算优惠、生成报价但不下单
- answer_gt：1179

## 重采说明
- 本批次经 recorder proxy 重采。
- 新轨迹仅使用标量参数工具，避免 stringified array 进入交付样例。
- 交付包已清理采集链路内部字段和模型标识。

## 自测结果
- 转换：accepted=1, rejected=0
- Schema：§4.1 校验无错误
- 工具调用配对数：8
- 实际工具：product_search / inventory_check / coupon_apply / order_quote
- 参数契约：tool_call arguments 与 mock request 均符合 tools schema
- Verifier：pass=True, score=1.0
- Mock 覆盖：total=8, hit=8, miss=0, rate=100.0%
