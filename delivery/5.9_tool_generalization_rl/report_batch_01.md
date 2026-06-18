# 5.9 工具调用泛化 RL 样例交付自测报告

## 样例场景
- 场景：电商比价报价
- 目标：查商品、过滤库存、试算优惠、比较到手价、生成报价但不下单
- answer_gt：1179

## 自测结果
- 转换：accepted=1, rejected=0
- Schema：§4.1 校验无错误
- 工具调用配对数：9
- 实际工具：product_search / inventory_check / coupon_apply / price_compare / order_quote
- Verifier：pass=True, score=1.0
- Mock 覆盖：total=9, hit=9, miss=0, rate=100.0%
