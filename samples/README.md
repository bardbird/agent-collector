# §5.1-§5.9 样例交付包

本目录是离线可验收样例，不替代真实采集。真实生产仍按 `docs/capture-checklist.md` 走代理采集，再用 `transform/to_section_5_x.py` 忠实转化。

## 生成与校验

```bash
python3 samples/build_samples.py
python3 samples/validate_samples.py
python3 mock/check_mock_coverage.py --jsonl-root samples/jsonl --db samples/mock/mock_responses.jsonl --missing samples/mock/_missing_mocks.jsonl
```

## Skill 安装到评测目录

```bash
./scripts/install_eval_skills.sh /path/to/eval/skills
```

默认安装到 `samples/eval_workspace/skills`。包含 `image-cropper`、`work-report`、`screenshot-annotator`、`visual-qa-auditor`。

## 目录

- `../delivery/jsonl/5_x.jsonl`: 最终样例交付形态。每个文件是一个分项数据集，文件内每行是一条独立 JSON 对象；当前样例阶段每个分项先放 1 行。
- `assets/`: 样例输入图、输出图、CSV、日志等离线资产。
- `mock/mock_responses.jsonl`: 5.6-5.9 工具调用 mock。
- `tasks/capture_tasks.md`: 真实采集时可用的目标导向 query，不含工具名和步骤指令。
