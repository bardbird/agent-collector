# 5.8 工具调用泛化 SFT 样例交付自测报告

## 样例场景
- 场景：活动安排（场地 + 天气 + 日历 + 邮件）
- 目标：读取场地信息、查询天气和可用性、选择室内厅、创建日历、发送通知

## 重采说明
- 本批次经 recorder proxy 重采。
- 新轨迹使用标量参数动作工具，避免 integer / array 字段被序列化成字符串。
- 交付包已清理采集链路内部字段和模型标识。

## 自测结果
- 转换：accepted=1, rejected=0
- Schema：§4.1 校验无错误
- 工具调用配对数：5
- 实际工具：venue_options_read / weather_query / room_availability / calendar_create / email_send
- 参数契约：tool_call arguments 与 mock request 均符合 tools schema
- Mock 覆盖：total=5, hit=5, miss=0, rate=100.0%
