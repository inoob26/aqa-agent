---
type: regex
target: files
pattern: '(^|/)test_\w+\.py$|_test\.py$|\.spec\.ts$'
flags: m
match: not_contains
---
