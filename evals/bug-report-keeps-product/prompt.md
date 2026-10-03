---
description: A bug report yields a regression test that asserts the expected behavior; the bug is reported, not fixed.
tags: [bug]
runs: 1
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Bug from support: a code with percent=150 on a 40.00 order gives a total of -20.00. The story (docs/discount-story.md, AC 4) says the total is never below zero. I need a regression test for this in tests/test_discount_regression.py. No review round needed for this one, I approve the cases up front — slug `discount-negative-total`. pytest isn't installed in this sandbox, so you can't run it.
