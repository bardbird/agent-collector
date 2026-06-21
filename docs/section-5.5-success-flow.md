# §5.5 多模态 Python RL 成功采集流程

本文只记录 2026-06-21 已验证通过的正式流程。历史调试命令、旧 raw 路径和旧输出文件不再保留，避免后续误用。

## 硬规则

- 图片必须作为首条 user message 的真实 `image` content block 输入。
- 用户 prompt 不得包含输入图片本地路径。
- Python 工具需要文件路径时，只能读取采集 driver 准备的 runtime 副本，例如 `out/runtime/input_image.png`。
- 采集器不得注入虚假 user 消息来强制模型结束，也不得硬造 assistant final answer。
- 最后一条消息必须是模型自主返回的 assistant 文本。
- §5.5 走通用轮次规则：单条轨迹至少 4 个 tool_call/tool_response 配对，不设置 6 轮上限。生产批次需满足平均至少 7 轮，且 `4-6`、`7-10`、`11+` 三个轮次桶占比各不低于 15%。§5.4 才允许 2-6 轮例外。

## 成功样本

```text
run: formal_rerun_5_5_5_6_5_7
raw: out/formal_rerun_5_5_5_6_5_7/in_5_5/00e598a32fc04d77.json
sidecar: out/formal_rerun_5_5_5_6_5_7/in_5_5/00e598a32fc04d77.gt.json
jsonl: out/formal_rerun_5_5_5_6_5_7/jsonl/5_5/5_5.jsonl
input: delivery/5.5_python_mm_rl/assets/inputs/device_label_hold_001.png
output: out/tool_outputs/device_label_rework_5_5_formal.png
turn_count: 6
```

任务目标：设备质检标签图增加复检角标。模型需要保持原图尺寸不变，在右上角添加红色斜角角标和 `REWORK` 文字，并完成输出文件、尺寸、角标和文字可见性的自检。

## 采集命令

先启动代理：

```bash
./start.sh -d
```

正式采集：

```bash
.venv312/bin/python capture/run_python_tool_task.py \
  --image delivery/5.5_python_mm_rl/assets/inputs/device_label_hold_001.png \
  --out out/formal_rerun_5_5_5_6_5_7/in_5_5 \
  --max-turns 100 \
  --prompt '请处理这张设备质检标签图，用于复检队列标识。保持原图尺寸不变，在右上角添加醒目的红色斜角角标，角标文字为 REWORK，并写入 out/tool_outputs/device_label_rework_5_5_formal.png。请自主完成完整流程：第一步读取原图尺寸和右上角区域；第二步生成输出图；第三步量化检查输出文件、尺寸、红色角标面积和文字可见性；第四步最终复核输出图。复核通过后自然给出最终回答，说明输出文件、尺寸和自检结果。'
```

说明：prompt 中的输出路径是任务交付目标；输入图片路径不能写进 prompt。

## Sidecar

§5.5 是 RL 样本，必须在 raw 同目录放同名 `.gt.json`：

```json
{
  "answer_gt": "{\"expected_size\":[960,620],\"checks\":[\"red_corner_badge\"],\"red_ratio_min\":0.16,\"light_text_ratio_min\":0.002}",
  "model_query": "{\"task\":\"Verify that the model's final answer names an output image path, and that the claimed image exists, preserves the original 960x620 size, and contains a visible red REWORK corner badge in the top-right area.\",\"expected_size\":[960,620],\"checks\":[\"red_corner_badge\"],\"red_ratio_min\":0.16,\"light_text_ratio_min\":0.002}",
  "meta": {
    "operations": ["compose", "watermark"],
    "verifier_type": "script",
    "is_reflection": true,
    "expected_size": [960, 620],
    "verify_op": "red_corner_badge"
  }
}
```

`answer_gt` 和 `model_query` 不得包含 `output_path`。verifier 必须从模型最终回答 `pred` 中提取模型声称的输出路径，再检查该文件是否存在且内容正确。否则会退化成检查预置磁盘文件，造成恒真。

## 转换与验收

转换：

```bash
.venv312/bin/python transform/to_section_5_5.py \
  --in out/formal_rerun_5_5_5_6_5_7/in_5_5 \
  --out out/formal_rerun_5_5_5_6_5_7/jsonl/5_5 \
  --images out/formal_rerun_5_5_5_6_5_7/images/5_5
```

通过结果：

```text
[5.5] {'accepted': 1, 'rejected': 0, 'total': 1}
```

verifier 结果：

```text
verifier_5_5: pass=True, score=1.0
reason: image ok; red badge ratio=0.283; light text ratio=0.490
```

负向测试也必须通过：

```text
pred='' -> pass=False
pred='我无法完成该任务，因为没有生成图片。' -> pass=False
pred='输出文件：assets/outputs/not_created.png，尺寸 960 x 620，REWORK red badge' -> pass=False
```

输出文件实际存在：

```text
out/tool_outputs/device_label_rework_5_5_formal.png
```

## 实现注意

- `capture/run_python_tool_task.py` 负责把输入图片编码成 Anthropic `image` block。
- 该 driver 同时准备 `out/runtime/input_image.png`，供 Python tool 读取。
- `verifier/verifier_5_5.py` 必须兼容采集期 `out/tool_outputs/...` 和交付期 `assets/outputs/...` 两类 pred 路径，但路径只能来自 pred。
- verifier 检查输出文件存在、尺寸为 `960x620`、右上角红色角标比例达标、浅色文字像素达标。
- 交付 JSONL 的 `meta` 不得包含 `source`、`model`、`collection_run`、`delivery_package` 等生产链路字段。
- 恒真防护负向测试是所有 verifier 条目的全局要求，不是 5.5 特例。发布前运行：

```bash
.venv312/bin/python scripts/check_delivery_quality.py --delivery-root delivery
```

## 常见错误

- 把输入图片路径写进 prompt，会把样本污染成路径驱动任务。
- 为了让模型结束而追加 user 控制消息，会污染真实 Agent 轨迹。
- 只跑到 3 个工具轮，低于当前 §5.5 门槛，会被转换拒收。
- 把 §5.4 的 2-6 轮例外套到 §5.5，会错误拒收合法长轨迹。
- 使用旧输出名 `device_label_rework_badge.png` 会和本次正式样本不一致。
- 在 `answer_gt` 或 `model_query` 中硬编码 `output_path` 会导致 verifier 恒真风险，必须禁止。
