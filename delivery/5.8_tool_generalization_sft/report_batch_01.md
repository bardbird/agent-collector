# 5.8 工具调用泛化 SFT 样例交付自测报告

## 样例场景
- 场景：多模态活动安排，混合工具链
- 输入：活动场地图 `event_venue.png`
- 目标：根据天气决定室外/室内，查场地，创建日历并发送通知

## 自测结果
- 转换：accepted=1, rejected=0
- Schema：§4.1 校验无错误
- 工具调用配对数：5
- 实际工具：venue_options_read / weather_query / room_availability / calendar_create / email_send
- Mock 覆盖：total=5, hit=5, miss=0, rate=100.0%
