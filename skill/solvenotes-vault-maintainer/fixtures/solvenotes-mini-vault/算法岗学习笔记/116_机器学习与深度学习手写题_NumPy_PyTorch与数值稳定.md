---
course: "算法岗学习笔记"
note_type: "course_note"
source_files: []
coverage: "checked"
last_checked: "2026-08-20"
tags:
  - "course/算法岗学习笔记"
---

# 机器学习与深度学习手写题

手写题先确认 shape、公式和边界，再实现最小 NumPy 版本；这里的 Python fence 只做语法解析，不执行训练。

```python
def mean_squared_error(values, targets):
    return sum((value - target) ** 2 for value, target in zip(values, targets)) / len(values)
```
