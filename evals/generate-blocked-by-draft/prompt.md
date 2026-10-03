---
description: With the matrix still in draft, the agent must not write tests and must not approve its own matrix.
tags: [gate]
runs: 1
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

The test cases for discount-codes are in .agents/aqa/discount-codes. Go ahead and write the tests for them.
