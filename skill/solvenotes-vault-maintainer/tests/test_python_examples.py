from check_python_examples import python_blocks


def test_python_blocks_are_extracted_without_execution() -> None:
    text = """\
```python
value = 1 + 2
```

```text
not_python(:
```
"""
    blocks = python_blocks(text)
    assert len(blocks) == 1
    assert blocks[0][0] == 1
    assert "value = 1 + 2" in blocks[0][1]


def test_python_info_string_does_not_consume_first_code_line() -> None:
    blocks = python_blocks("```python title=example\nvalue = 1\n```\n")
    assert blocks == [(1, "value = 1\n")]
