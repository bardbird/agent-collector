# §5.5 多模态 Python RL 成功采集流程

本文记录一次已经跑通的 §5.5 样品流程，供后续复用。核心原则仍是：

- 真实模型请求必须经过本地代理，保证 `out/raw_http/` 和 `out/raw_turns/` 有证据。
- 图片必须作为对话里的真实 image content block 输入，不用文件路径冒充多模态。
- 只沿用甲方文档格式，不复用甲方示例题材。
- 不手写工具轨迹；模型真实调用 `python`，本地真实执行代码，再把 tool_result 回填给模型。

## 成功案例

任务题材：设备质检标签图增加复检角标。

输入图片：

```text
samples/assets/inputs/device_label_hold_001.png
```

输出图片：

```text
samples/assets/outputs/device_label_rework_badge.png
```

用户目标：

```text
这张设备质检标签需要给复检队列使用。请保持原图尺寸不变，在右上角添加醒目的红色斜角角标，角标文字为 REWORK，保存为 samples/assets/outputs/device_label_rework_badge.png，并说明输出文件和尺寸。
```

验证目标：

```text
output image exists, original size 960x620 is preserved, and a red REWORK corner badge is present in the top-right area
```

## 正确采集链路

1. 启动 recorder 代理：

```bash
./start.sh -d
```

2. 通过 `capture/run_python_tool_task.py` 发起模型请求。

该脚本做三件事：

- 将输入图片编码为 Anthropic `image` block，放进首条 user message。
- 向模型暴露单一 `python` tool。
- 执行模型返回的 Python 代码，并把执行结果作为 `tool_result` 继续发回模型。

示例命令：

```bash
python3 capture/run_python_tool_task.py \
  --settings out/capture.settings.json \
  --image samples/assets/inputs/device_label_hold_001.png \
  --prompt "这张设备质检标签需要给复检队列使用。请保持原图尺寸不变，在右上角添加醒目的红色斜角角标，角标文字为 REWORK，保存为 samples/assets/outputs/device_label_rework_badge.png，并说明输出文件和尺寸。"
```

注意：`out/capture.settings.json` 的 `ANTHROPIC_BASE_URL` 必须是本地代理：

```text
http://127.0.0.1:8080
```

不要绕开代理直连上游。绕开代理就没有 `raw_http` 证据。

3. 停止代理落盘：

```bash
./start.sh stop
```

成功后应能看到：

```text
out/raw_http/<task>_turn*.request.txt
out/raw_http/<task>_turn*.response.txt
out/raw_turns/<task>.json
samples/assets/outputs/device_label_rework_badge.png
```

## 关键实现点

### 真实图片输入

`capture/run_python_tool_task.py` 必须使用 image block：

```json
{
  "type": "image",
  "source": {
    "type": "base64",
    "media_type": "image/png",
    "data": "..."
  }
}
```

转交付时再由 `transform/common.py` 抽取为：

```json
{
  "type": "image_url",
  "image_url": {
    "url": "assets/inputs/device_label_hold_001.png"
  }
}
```

### 工具轨迹

本案例中模型真实调用 `python`，并出现失败修正：

- 第一次代码引用了错误文件名。
- 后续通过 Python 查找素材文件。
- 再次生成角标时缺 `os` import。
- 最后修正代码并成功保存输出图片。

这类失败修正是有价值的 §5.5 RL 轨迹，不应删除。

### 尾部 assistant

必须保证最后一条消息是 assistant 文本，而不是 tool_use。

`capture/run_python_tool_task.py` 在检测到 Python 成功产出后，会再发一轮不带工具的请求：

```text
The image processing output was created. Now provide a concise final answer with the output path and dimensions. Do not call tools again.
```

这一步仍然经过代理，属于真实模型输出。

## Sidecar 标注

RL 字段不从模型轨迹里猜，采集后用同名 sidecar 标注：

```text
out/raw_turns/<task>.gt.json
```

本案例字段：

```json
{
  "answer_gt": "output image exists, original size 960x620 is preserved, and a red REWORK corner badge is present in the top-right area",
  "model_query": "Verify that the output image exists, keeps the original 960x620 size, and contains a red REWORK corner badge in the top-right area. Answer YES or NO.",
  "meta": {
    "operations": ["compose", "watermark"],
    "verifier_type": "script",
    "is_reflection": true,
    "output_path": "samples/assets/outputs/device_label_rework_badge.png",
    "input_path": "samples/assets/inputs/device_label_hold_001.png",
    "expected_size": [960, 620],
    "verify_op": "red_corner_badge"
  }
}
```

`transform/common.py` 会读取同名 `.gt.json` 并注入顶层 `answer_gt`、`model_query` 和 `meta`。

## 转换与校验

转换：

```bash
python3 transform/to_section_5_5.py \
  --in out/raw_turns \
  --out out/jsonl/5_5 \
  --images out/images
```

成功结果：

```text
[5.5] {'accepted': 1, 'rejected': 0, 'total': 1}
```

验证逻辑在：

```text
verifier/verifier_5_5.py
```

本案例使用：

```text
verify_op = red_corner_badge
expected_size = [960, 620]
```

verifier 检查：

- 输出图片存在。
- 输出尺寸仍为 `960x620`。
- 右上角区域存在足够比例的红色像素，确认有红色角标。

## 单项交付目录

只交付 5.5 单项时，配套文件放在 5.5 目录内，做成自包含包：

```text
delivery/5.5_python_mm_rl/
  batch_01.jsonl
  report_batch_01.md
  manifest.json
  assets/
    inputs/device_label_hold_001.png
    outputs/device_label_rework_badge.png
  verifier/
    verifier_5_5.py
```

JSONL 内相对路径也应指向本目录：

```json
"image_url": {
  "url": "assets/inputs/device_label_hold_001.png"
}
```

```json
"meta": {
  "input_path": "assets/inputs/device_label_hold_001.png",
  "output_path": "assets/outputs/device_label_rework_badge.png"
}
```

## 常见错误

- 错误：绕开代理直连上游。
  结果：没有 `raw_http` 证据，不能证明真实采集。

- 错误：只把图片路径写进 prompt。
  结果：变成文本/文件任务，不是多模态输入。

- 错误：复用甲方文档里的中心裁剪 512x512 示例。
  结果：题材撞示例，不能送检。

- 错误：最后一条停在 `assistant.tool_calls`。
  结果：尾部不是 assistant 文本收尾，转化/验收风险高。

- 错误：把 `assets/`、`verifier/`、`manifest.json` 放在根目录但只交付单项。
  结果：单项包不自包含，路径不清晰。
