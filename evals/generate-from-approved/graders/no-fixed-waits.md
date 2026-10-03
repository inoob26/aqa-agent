---
type: regex
target: { source: file, path: tests/test_discount.py }
pattern: 'sleep\s*\(|assert True'
match: not_contains
---
