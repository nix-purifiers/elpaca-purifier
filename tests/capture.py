import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="elpaca capture ") as temporary:
    temp = Path(temporary)
    root = temp / "configuration"
    shutil.copytree(repo / "examples/minimal", root)
    companion, native = root / "elpaca-purifier.lock.json", root / "elpaca-lock.el"
    companion.unlink()
    native.unlink()
    env = dict(
        os.environ,
        ELPACA_PURIFIER_PROJECT=str(root),
        XDG_CACHE_HOME=str(temp / "cache"),
    )

    def capture(*args, success=True):
        result = subprocess.run(
            [sdk / "bin/elpaca-purifier", "lock", *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    capture()
    data = json.loads(companion.read_text())
    assert {item["name"] for item in data["recipes"]} == {"f", "s", "dash"}
    assert len(data["entries"]) == 3 and data["native"] == native.read_text()
    assert not (root / "elpaca").exists()
    before = native.read_bytes(), companion.read_bytes()
    capture()
    assert before == (native.read_bytes(), companion.read_bytes())
    init = root / "init.el"
    original = init.read_text()
    init.write_text(original.replace("purifier-answer 42", "purifier-answer 43"))
    capture()
    assert before == (native.read_bytes(), companion.read_bytes())
    init.write_text(
        original.replace("(elpaca f", "(elpaca (f :build (list (quote unsupported)))")
    )
    denied = capture("--update", success=False)
    assert "provider" in denied.stderr, denied
    assert before == (native.read_bytes(), companion.read_bytes())
    init.write_text("(require 'elpaca)\n")
    capture("--update")
    data = json.loads(companion.read_text())
    assert data["entries"] == [] and data["recipes"] == []
    capture()
print(
    "Native Elpaca dependency capture, stable locks, rejected custom builds and empty profile passed"
)
