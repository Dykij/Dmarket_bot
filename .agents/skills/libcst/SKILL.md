---
name: libcst-python-modifier
description: Use when you need to make structural modifications to Python code. Required for Python edits more complex than a single-line string replacement. Do NOT use sed, re.sub, or replace() scripts for Python.
---

# LibCST Python Modifier

Этот инструмент (skill) предписывает агентам использовать `libcst` для любых правок Python-кода, которые сложнее простой однострочной замены, во избежание повреждения синтаксиса или отступов.

## Правила
1. Никаких самописных скриптов с `sed`, `re.sub()` или `.replace()` для Python.
2. Использовать `libcst` для безопасной трансформации синтаксического дерева (AST).

## Пример использования (согласно пункту 14 VERIFICATION_STANDARDS)
Для модификации кода следует создать временный скрипт:

```python
import libcst as cst

class CustomTransformer(cst.CSTTransformer):
    def leave_Return(self, original_node: cst.Return, updated_node: cst.Return) -> cst.CSTNode:
        # Ваш код трансформации
        return updated_node

with open("target_file.py", "r") as f:
    source_code = f.read()

module = cst.parse_module(source_code)
modified_module = module.visit(CustomTransformer())

with open("target_file.py", "w") as f:
    f.write(modified_module.code)
```
