---
description: A story must become reviewed-on-disk test cases; no test code before the human approves the matrix.
tags: [gate]
runs: 1
max_turns: 40
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

We're picking up SHOP-42, the story is in docs/discount-story.md. Work out the test cases for it — use the slug `discount-codes`.
