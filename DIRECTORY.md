# 目录分层

这个仓库外层目录按用途只分四类：工程代码、需求文档、送检交付物、运行态中间产物。

## 1. 工程代码目录

```text
proxy/        recorder 代理，录制 Claude Code /v1/messages
capture/      真实采集驱动器，暴露工具、执行 tool_use、冻结 mock
transform/    §4.1 / §5.x 转换器
verifier/     RL 场景验证脚本
mock/         通用 mock 回放服务和覆盖率检查脚本
dashboard/    本地采集查看面板
scripts/      辅助脚本
skills/       skill workspace 草稿/样例，仅用于 5.1-5.3
```

这些目录是代码或可复用工程资产，不属于交付包，也不是临时产物。

## 2. 需求文档

```text
docs/         甲方 docx、整理文档、成功流程记录
```

正式输入素材随各分项交付包放在 `delivery/*/assets/inputs/`，不再维护独立样本素材目录。

## 3. 送检交付物

```text
delivery/
  5.5_python_mm_rl/
  5.6_search_sft/
  5.7_search_rl/
  5.8_tool_generalization_sft/
  5.9_tool_generalization_rl/
```

`delivery/` 是当前送检样例包目录。每个分项目录必须自包含：

```text
batch_01.jsonl
manifest.json
report_batch_01.md
assets/
mock/       需要 mock 的场景才有
verifier/   RL 场景才有
```

交付包不能依赖 `out/`。

## 4. 运行态中间产物

```text
out/
```

`out/` 由采集和转换命令生成，属于中间产物，可以随时删除，不提交。

当前已经清理掉 `out/`，重新采集时会自动生成。

## 根目录脚本和配置

```text
start.sh          启动/停止代理、转换、面板
run_proxy.sh      最小代理启动脚本
requirements.txt  Python 依赖
AGENTS.md         仓库协作规则
README.md         项目说明
DIRECTORY.md      本目录分层说明
```

## 删除规则

可以删：

```text
out/
*.log
*.tmp
.DS_Store
__pycache__/
*.pyc
```

不要删：

```text
delivery/     当前送检交付物
docs/         甲方需求和成功流程记录
capture/      重新采集要用
transform/    重新转换要用
mock/         mock 回放和覆盖率检查要用
verifier/     RL 验证要用
```
