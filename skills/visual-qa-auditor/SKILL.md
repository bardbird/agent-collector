---
name: visual-qa-auditor
description: Audit multimodal QA tasks that combine an attached image with local files such as CSV, JSONL, logs, or manifests. Use when the answer must be objectively checked with scripts or shell commands.
---

# visual-qa-auditor

Resolve verifiable QA tasks from an image plus local structured files.

## Workflow

1. Read the user's goal and identify which local files can verify the visual claim.
2. If the image provides context only, state the visual cue briefly and compute the final answer from files.
3. Use shell or small scripts for arithmetic, filtering, exact counts, and consistency checks.
4. Return a single final answer first, followed by a compact audit note with file names and filters used.

## Verification Rules

- Prefer deterministic commands over visual guessing.
- Treat `answer_gt` tasks as exact-match unless the user asks for a tolerance.
- For counts and totals, include the inclusion rule in the final note.
- Do not invent missing rows; ask for the missing export when the referenced file is absent.
