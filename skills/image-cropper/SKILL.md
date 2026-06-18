# image-cropper

图像处理 skill:中心裁剪 / 旋转 / 缩放 / 加水印 / 灰度滤镜。覆盖 §5.4/§5.5 中"裁剪 / 旋转 / 缩放 / 滤镜 / 水印"五种操作。

## Instructions

### Step 1: 解析用户意图
- 触发: 用户上传图片 + 描述操作(裁剪 / 旋转 / 加水印 / 缩放 / 灰度)。
- 行为: 从 user message 的 `image_url` 取输入路径,从文本中提取操作和参数(尺寸 / 角度 / 文字)。

### Step 2: 调用 process.py
- 操作 = `crop`:`--op crop --size WxH`(默认中心裁剪)。
- 操作 = `rotate`:`--op rotate --angle N`(顺时针为负)。
- 操作 = `scale`:`--op scale --size WxH`。
- 操作 = `watermark`:`--op watermark --text "SAMPLE" --position bottom-right`。
- 操作 = `filter`:`--op filter --kind grayscale`。

### Step 3: 返回结果
- 输出路径固定为 `output/<原名>_processed.<ext>`。
- 在 assistant 回复中报告:操作类型 + 输出尺寸 + 输出路径。

## Examples

### Example 1: 中心裁剪 512×512
**用户 query**: "将图片中心区域裁剪为 512×512 的正方形"(附 `input/landscape.jpg`)
**执行流程**:
1. 解析: op=crop, size=(512,512), input=input/landscape.jpg
2. `python scripts/process.py --op crop --size 512x512 --in input/landscape.jpg --out output/landscape_processed.jpg`
3. 返回:"已裁剪 → output/landscape_processed.jpg (512×512)"

### Example 2: 顺时针 90° + 右下角水印
**用户 query**: "旋转 90 度,加 SAMPLE 水印到右下角"
**执行流程**: 两步串联 — rotate 后再 watermark。

## Limitations
- 不做 AI 增强 / 上色 / 抠图(这些归 image-editor skill)。
- 输入图片必须可被 PIL 打开(JPEG/PNG/WebP)。
- 透视变换 / 拼接由 image-collage 单独 skill 处理。
