import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "configuration"
    shutil.copytree(repo / "examples/minimal", root)
    companion = root / "elpaca-purifier.lock.json"
    original = json.loads(companion.read_text())

    def inspect():
        expression = (
            "let f=builtins.getFlake "
            + json.dumps(str(repo))
            + ";lock=f.lib.elpaca-purifier.readLock {src=/. + "
            + json.dumps(str(root))
            + ";};in {inherit(lock)problems outputs;}"
        )
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    assert inspect()["problems"] == []
    assert inspect()["outputs"]["packages"] == ["default", "environment", "project"]
    (root / "init.el").write_text("(setq source-edit 43)\n")
    assert inspect()["problems"] == []
    companion.unlink()
    assert inspect()["problems"]
    for mutate in [
        lambda d: d.update(purifier="other"),
        lambda d: d["entries"][0].update(path="../escape"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["entries"][0]["git"].update(rev="invalid"),
        lambda d: d["recipes"][0].update(repo="../escape"),
        lambda d: d["recipes"][0].update(build="../escape"),
        lambda d: d.update(sdk=None),
    ]:
        data = copy.deepcopy(original)
        mutate(data)
        companion.write_text(json.dumps(data))
        assert inspect()["problems"]
    companion.write_text(json.dumps(original))
    (root / "elpaca-lock.el").write_text("nil\n")
    assert inspect()["problems"]
print("Elpaca lock errors and output names validated without IFD")
