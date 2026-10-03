---
description: An approved matrix becomes traced pytest tests; the product code is not touched.
tags: [generate]
runs: 1
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

The matrix for discount-codes in .agents/aqa/discount-codes is approved. Write the tests into tests/test_discount.py. pytest isn't installed in this sandbox, so don't try to run them — just write them and run the static checks.
