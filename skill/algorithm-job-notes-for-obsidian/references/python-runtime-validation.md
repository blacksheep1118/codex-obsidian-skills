# Dependency-backed Python note validation

## Contents

- [Trust boundary](#trust-boundary)
- [Validated direct-dependency baseline](#validated-direct-dependency-baseline)

Use this mode only when the user asks to execute dependency-backed Python
examples or to close a previously reported runtime gap. It is deliberately
separate from root `pytest`, `scripts/validate_all.py`, and `vault-full` so the
public Skill CI remains small, offline, and self-contained.

## Trust boundary

Only execute a Python fence when all of the following hold:

- the code block is self-contained and has been read in full;
- it is immediately preceded by one exact marker;
- the marker lists every non-stdlib runtime dependency;
- inputs are synthetic or explicitly authorized;
- files, Spark local storage, and intermediate models stay in a temporary
  directory.

This is a trusted-local-code gate, not an operating-system sandbox. The
checker strips credential-like inherited environment state, uses isolated
Python mode, and gives each block a temporary home and working directory, but
it cannot prevent an intentionally hostile block from reading an absolute
path, opening a network connection, or detaching a process on every supported
platform. Review every marked block in full. Never invoke this gate for an
untrusted pull request or as ordinary public CI.

Marker syntax:

````markdown
<!-- runnable: python-e2e requires=python,numpy,torch,onnx,onnxscript,onnxruntime -->
```python
# reviewed self-contained example
```
````

Supported requirement names are `python`, `numpy`, `torch`, `onnx`,
`onnxruntime`, `onnxscript`, `pyspark`, and `java17`. An unknown name, malformed
marker, missing package, old Java runtime, syntax error, timeout, nonzero exit,
or excessive output is a hard failure. The checker never turns missing
dependencies into a passing skip.

## Validated direct-dependency baseline

Install the known-good Python set with Python 3.10 or newer into a dedicated
environment outside the Notes and Skills repositories. From a Skills source
checkout, use:

```bash
python3 -m venv /absolute/path/to/solvenotes-runtime
/absolute/path/to/solvenotes-runtime/bin/python -m pip install \
  -r skill/algorithm-job-notes-for-obsidian/requirements-runtime.txt
```

From a synchronized installed mirror, the equivalent requirements path is
`/absolute/path/to/.codex/skills/algorithm-job-notes-for-obsidian/requirements-runtime.txt`.

PySpark 4.2 requires Java 17 or newer. Set `JAVA_HOME` and put its `bin`
directory first on `PATH`; do not rely on a GUI application's inherited shell
state. The runtime gate itself is offline and never installs or downloads
packages.

This file pins the direct packages exercised by the marked examples; it is not
a hash-locked transitive dependency lockfile. Preserve the validated
interpreter/platform details in the test report, run `python -m pip check`, and
rerun both marked examples after any fresh resolution or platform change.

Run from the Skills source repository:

```bash
SOLVENOTES_VAULT_ROOT=/absolute/path/to/notes \
SOLVENOTES_PYTHON_BIN=/absolute/path/to/solvenotes-runtime/bin/python \
SOLVENOTES_RUNTIME_REVIEWED=1 \
JAVA_HOME=/absolute/path/to/jdk-17 \
PATH="/absolute/path/to/jdk-17/bin:$PATH" \
  bash skill/solvenotes-vault-maintainer/scripts/dev_check.sh vault-runtime
```

For a synchronized installed mirror, keep the same environment variables but
use its flat entry point instead:

```bash
bash /absolute/path/to/.codex/skills/solvenotes-vault-maintainer/scripts/dev_check.sh \
  vault-runtime
```

The preflight reports the selected interpreter and package versions. The
runtime checker then executes each marked block in its own temporary working
directory with a bounded process tree. Each block defaults to 180 seconds via
`SOLVENOTES_RUNTIME_EXAMPLE_TIMEOUT`; the complete runtime step has a separate
3600-second default via `SOLVENOTES_RUNTIME_GATE_TIMEOUT`. Both must be finite
positive numbers, and the complete-gate budget must not be smaller than the
per-example budget. The complete budget is still an aggregate safety cutoff;
if it expires, the outer runner reports `TIMEOUT` and may stop the checker
before its summary line. Set either only to a reviewed value. A valid result
includes one `PASS` line per block and ends with:

```text
python_runtime_examples marked_blocks=N executed=N failures=0
```

PySpark local mode starts a Java gateway that binds a loopback socket. If a
host sandbox rejects that bind with `java.net.SocketException: Operation not
permitted` followed by `JAVA_GATEWAY_EXITED`, the packages have not thereby
failed validation: rerun the same reviewed command with explicit permission
for local loopback execution. Do not weaken the dependency gate or relabel the
failure as a missing PySpark/Java installation.

The current dependency baseline follows the official
[PyTorch ONNX exporter](https://docs.pytorch.org/docs/stable/onnx.html),
[ONNX Runtime CPU install](https://onnxruntime.ai/docs/install/), and
[PySpark installation](https://spark.apache.org/docs/latest/api/python/getting_started/install.html)
contracts. Refresh the pinned file intentionally and rerun both the Skill tests
and real marked examples before changing it.
