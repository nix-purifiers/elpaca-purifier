import hashlib
import json
import os
from pathlib import Path
import tempfile

from .common import load, original_environment, run
from .layout import configure, launch


def realize(root, companion, native):
    data = load(companion, native)
    sdk = os.environ["ELPACA_PURIFIER_SDK"]
    home = Path(
        original_environment().get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    )
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    generation = hashlib.sha256(companion.read_bytes() + sdk.encode()).hexdigest()[:20]
    state = home / "elpaca-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    profile = state / "environment-profile"
    if not profile.exists():
        expression = (
            "import "
            + json.dumps(sdk + "/lib/elpaca-purifier/pkgs/build-elpaca-project/realize.nix")
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";nativeLockFile="
            + json.dumps(str(native))
            + ";sdk="
            + json.dumps(sdk)
            + ";}"
        )
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(profile),
            ]
        )
    output = Path(json.loads(profile.read_text())["output"])
    manifest = json.loads(output.read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Elpaca SDK differs from the lock")
    return state, data, manifest


def execute(root, companion, native, args):
    state, data, manifest = realize(root, companion, native)
    with tempfile.TemporaryDirectory(prefix="invocation-", dir=state) as temporary:
        env = configure(state / "session", Path(temporary), manifest, data)
        env.update(
            ELPACA_PURIFIER_PROJECT=str(root),
            ELPACA_PURIFIER_LOCK=str(companion),
            ELPACA_PURIFIER_NATIVE_LOCK=str(native),
        )
        return launch(
            os.environ["ELPACA_PURIFIER_EMACS"],
            env,
            ["--init-directory", str(root), *args],
        )
