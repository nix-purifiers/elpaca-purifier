import json
import os
from pathlib import Path
import subprocess


def alias(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.resolve() != Path(target).resolve():
            raise ValueError(
                "Private Elpaca source differs from the Nix SDK: " + str(path)
            )
    else:
        path.symlink_to(target, target_is_directory=True)


def configure(state, invocation, manifest, data):
    state.mkdir(parents=True, exist_ok=True)
    invocation.mkdir(parents=True, exist_ok=True)
    core = Path(manifest["core"])
    for directory in ("repos", "sources", "builds"):
        alias(state / "elpaca" / directory / "elpaca", core)
    for recipe in data["recipes"]:
        alias(
            state / "elpaca/repos" / recipe["repo"],
            Path(manifest["tree"]) / recipe["repo"],
        )
        alias(
            state / "elpaca/builds" / recipe["build"],
            Path(manifest["builds"]) / recipe["build"],
        )
    env = dict(os.environ)
    if "ELPACA_PURIFIER_ORIGINAL_ENV" not in env:
        env["ELPACA_PURIFIER_ORIGINAL_ENV"] = json.dumps(
            {
                name: env.get(name)
                for name in (
                    "EMACSLOADPATH",
                    "XDG_CACHE_HOME",
                    "XDG_DATA_HOME",
                    "XDG_STATE_HOME",
                )
            }
        )
    status = invocation / "status.json"
    status.unlink(missing_ok=True)
    env.update(
        ELPACA_PURIFIER_STATE=str(state),
        ELPACA_PURIFIER_STATUS=str(status),
        ELPACA_PURIFIER_PREPARED_LOCK=manifest["native"],
        ELPACA_PURIFIER_SELECTION=manifest["selection"],
        XDG_CACHE_HOME=str(state / "cache"),
        XDG_DATA_HOME=str(state / "data"),
        XDG_STATE_HOME=str(state / "state"),
    )
    helper = Path(__file__).parent.parent / "lisp/activate.el"
    site = invocation / "site-lisp"
    site.mkdir(exist_ok=True)
    (site / "site-start.el").write_text(
        "(load " + json.dumps(str(helper), ensure_ascii=False) + " nil t)\n"
    )
    env["EMACSLOADPATH"] = str(site) + os.pathsep + str(core) + os.pathsep
    env["GIT_OPTIONAL_LOCKS"] = "0"
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    for source in Path(manifest["tree"]).iterdir():
        env["GIT_CONFIG_KEY_" + str(count)] = "safe.directory"
        env["GIT_CONFIG_VALUE_" + str(count)] = str(source.resolve())
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def launch(binary, env, args):
    flags = list(args)
    if "-Q" in flags or "--quick" in flags:
        helper = Path(__file__).parent.parent / "lisp/activate.el"
        flags = ["--eval", "(setq after-init-time nil)", "--load", str(helper), *flags]
    if "--batch" in flags:
        flags += ["--eval", "(progn (elpaca-wait) (elpaca-process-queues))"]
    result = subprocess.call([str(binary), *flags], env=env)
    status = Path(env["ELPACA_PURIFIER_STATUS"])
    if not status.exists():
        return result or 1
    valid = json.loads(status.read_text()).get("valid")
    return result if valid else result or 1
