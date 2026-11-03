import json
import os
import subprocess


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    return result.stdout


def original_environment():
    env = dict(os.environ)
    for name, value in json.loads(
        env.pop("ELPACA_PURIFIER_ORIGINAL_ENV", "{}")
    ).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    for name in (
        "ELPACA_PURIFIER_STATE",
        "ELPACA_PURIFIER_STATUS",
        "ELPACA_PURIFIER_PREPARED_LOCK",
        "ELPACA_PURIFIER_SELECTION",
    ):
        env.pop(name, None)
    return env


def load(companion, native):
    data = json.loads(companion.read_text())
    if data.get("sdk") != os.environ["ELPACA_PURIFIER_SDK_VERSION"]:
        raise ValueError("Elpaca SDK changed; run elpaca-purifier lock --update")
    if data.get("native") != native.read_text():
        raise ValueError(
            "Native Elpaca lock changed; run elpaca-purifier lock --update"
        )
    return data
