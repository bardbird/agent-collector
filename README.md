# POC:Claude Code 真实轨迹采集 + §4.1 转化

样例阶段聚焦一条最小闭环:**真实采集 → 忠实转化**,不构造反思轨迹。

```
Claude Code  ──HTTP──▶  本地代理(:8080, reverse)  ──HTTPS──▶  配置的上游
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

## 目录分层

顶层目录按用途分成四类：代码、需求文档、交付物、运行态中间产物。

### 代码目录

这些目录是采集、转换、验证和回放逻辑，属于工程代码。

```text
proxy/        recorder 代理，负责录制 /v1/messages
capture/      分项采集驱动器，负责暴露工具、执行 tool_use、写 mock
transform/    raw_turns → §4.1 / §5.x JSONL 转换器
verifier/     RL 项验证脚本
mock/         通用 mock 回放服务和覆盖率检查脚本
dashboard/    本地采集查看面板
scripts/      辅助脚本
skills/       §5.1-§5.3 skill workspace 草稿/样例
```

### 文档

需求、设计和成功流程统一放在文档目录。正式输入素材随交付包放在 `delivery/*/assets/inputs/`，不再维护独立样本素材目录。

```text
docs/         甲方 docx、整理说明、成功采集流程
```

### 交付物

`delivery/` 是当前可送检样例包所在目录。每个分项自包含 JSONL、assets、mock/verifier、manifest 和报告。

```text
delivery/
  5.5_python_mm_rl/
  5.6_search_sft/
  5.7_search_rl/
  5.8_tool_generalization_sft/
  5.9_tool_generalization_rl/
```

### 运行态中间产物

`out/` 是唯一运行态中间产物目录，采集/转换时生成，清理后可以不存在，不应提交。

```text
out/
  raw_http/     代理原始 HTTP 证据
  raw_turns/    recorder 中间格式
  jsonl/        转换后的临时 JSONL
  images/       临时抽取图片
  proxy.log     代理日志
```

当前仓库已清理运行态数据；重新采集时 `out/` 会自动生成。

## 顶层文件

```text
start.sh          一键启动/停止代理、转换、面板等
run_proxy.sh      最简代理启动脚本
requirements.txt  Python 依赖
AGENTS.md         本仓库协作和编码约定
README.md         本说明
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
