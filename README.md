# POC:Claude Code 真实轨迹采集 + §4.1 转化

样例阶段聚焦一条最小闭环:**真实采集 → 忠实转化**,不构造反思轨迹。

```
Claude Code  ──HTTP──▶  本地代理(:8080, reverse)  ──HTTPS──▶  api.anthropic.com
                              │ 录制 /v1/messages 全量 I/O
                              ▼
                     out/raw_turns/*.json   (Anthropic 原始中间格式)
                              │ transform/to_section4_1.py
                              ▼
                     out/jsonl/*.jsonl      (§4.1 客户 messages 格式)
                     out/images/*           (图片从 base64 落盘)
```

## 为什么是代理层
代理是"真相源":拿到模型**真实看到的 input(messages/tools/system)和真实产生的 output**(含 tool_use)。hooks 只在工具执行点截获、SDK 要自己驱动并拼装;代理零拼装,且能录**人类用 Claude Code 真实完成任务的全过程**——这是 SFT 示范数据的黄金来源,多样性天然高于 LLM 自动生成。

## 目录
```
poc/
├── proxy/recorder.py          # mitmproxy addon:拦截 + stitch + 落中间格式
├── transform/to_section4_1.py # Anthropic 中间格式 → §4.1 OpenAI FC JSONL
├── start.sh                   # ★ 一键启动(依赖检查/前后台/stop/status/transform)
├── run_proxy.sh               # 最简启动版(仅 exec mitmdump)
├── requirements.txt           # mitmproxy
└── out/                       # 运行后生成:raw_turns / jsonl / images / proxy.log
```

## 运行(一键)
```bash
# 1) 启动代理(自动检查/安装 mitmproxy、初始化目录、检查端口)
./start.sh                 # 前台启动,Ctrl+C 退出即 flush
# ./start.sh -d            # 或后台启动(日志写 out/proxy.log)
# ./start.sh -p 9090       # 换端口

# 2) Claude Code 走代理执行真实任务(另开终端)
ANTHROPIC_BASE_URL=http://127.0.0.1:8080 claude
#   在 Claude Code 里正常完成一个任务(写代码 / 搜资料 / 调 skill ...)。
#   做完后:前台 Ctrl+C,或后台 ./start.sh stop  → 触发落盘

# 3) 转化为 §4.1
./start.sh transform       # → out/jsonl/<task>.jsonl  +  out/images/*
```

### start.sh 子命令速查
| 命令 | 作用 |
|------|------|
| `./start.sh` | 前台启动代理(默认) |
| `./start.sh all` | ★ 一键:后台代理 + 前台面板(Ctrl+C 同停) |
| `./start.sh -d` | 后台启动 |
| `./start.sh status` | 查看代理运行状态 |
| `./start.sh stop` | 停止后台代理(SIGTERM 触发 flush) |
| `./start.sh restart` | 重启 |
| `./start.sh transform` | raw_turns → §4.1 JSONL |
| `./start.sh -p <port>` | 指定端口 |
| `./start.sh --no-install` | 跳过 mitmproxy 自动安装 |

## 转化做了什么(对照 §4.1 / 附录 A)
- `tools`: `{name,description,input_schema}` → `{type:function, function:{...parameters}}`
- assistant `tool_use` → `tool_calls[]`,`arguments` 序列化为**字符串**
- `tool_result`(Anthropic 放在 user message 内)→ **独立 `role:tool` 消息**(配对 `tool_call_id`)
- 图片 base64 → 落盘文件 + `{type:image_url, image_url:{url:"相对路径"}}`
- 补 `uuid` / `finish`(末条是否 assistant)/ `meta`(source/model/turns/language)

## 已知边界(本样例不处理,需后续)
| 项 | 现状 | 后续 |
|----|------|------|
| **system-reminder 位置** | Claude Code 把 CLAUDE.md/skills 多注入在 `system`;§4.1 红线要求注入在 **user content 头部** | 转换器原样保留 system 并在 `meta.capture_note` 标注,后续做迁移改写 |
| 反思轨迹 | 不构造(`is_reflection` 恒 false) | 下一阶段:正确轨迹→注入错误→接续修正 |
| `thinking` blocks | 默认丢弃 | 是否保留待甲方明确 |
| `meta.domain` 等打标 | 留默认 | 后续按 D1–D8 / 语言检测补 |
| mock 固化 | 本闭环不含 | 搜索类(5.6/5.7)需在代理加 WebSearch/MCP 拦截 + request_hash 落 mock |
| Schema 门禁 | 本闭环不含 | 转化后接 §4.1 Schema 校验(tool_call_id 配对 / tools 非 null / 末条 assistant) |

> 装好 mitmproxy 首次运行会在 `~/.mitmproxy/` 生成 CA;reverse 模式下 Claude Code 走本地 HTTP,**无需**信任该 CA(到上游仍是合法 HTTPS)。

## 技术栈选择
默认 **Python + mitmproxy**:POC 最快、与 §4.3 verifier 同生态、SSE 缓冲录制最可靠。
若要更贴 Claude Code 技术栈,可换 **Node reverse proxy**(SSE `pipe` 更自然),recorder 逻辑等价迁移。
