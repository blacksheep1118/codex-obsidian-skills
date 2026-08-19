from check_cpp_examples import marked_blocks


def test_only_explicit_cpp17_blocks_are_selected() -> None:
    text = """\
```cpp
int unmarked = 1;
```

<!-- runnable: cpp17 -->
```cpp
int main() { return 0; }
```
"""
    blocks = marked_blocks(text)
    assert len(blocks) == 1
    assert "int main" in blocks[0][1]
