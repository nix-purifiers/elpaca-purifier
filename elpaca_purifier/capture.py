import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

from .common import original_environment, run
from .layout import alias


def capture(root, companion, native, config, update=False):
    if companion.exists() and not update:
        from .runtime import execute

        if execute(root, companion, native, ["-Q", "--batch", "--load", str(config)]):
            raise ValueError("Locked Elpaca configuration failed verification")
        return
    with tempfile.TemporaryDirectory(prefix="elpaca-capture-") as temporary:
        state = Path(temporary)
        core = Path(os.environ["ELPACA_PURIFIER_CORE"])
        for directory in ("repos", "sources", "builds"):
            alias(state / "elpaca" / directory / "elpaca", core)
        private_lock = state / "elpaca-lock.el"
        if native.exists() and not update:
            private_lock.write_bytes(native.read_bytes())
        resolution = state / "resolution.json"
        env = original_environment()
        env.pop("EMACSLOADPATH", None)
        env.update(
            ELPACA_PURIFIER_STATE=str(state),
            ELPACA_PURIFIER_PROJECT=str(root),
            ELPACA_PURIFIER_CONFIG=str(config),
            ELPACA_PURIFIER_PREPARED_LOCK=str(private_lock),
            ELPACA_PURIFIER_RESOLUTION=str(resolution),
            XDG_CACHE_HOME=str(state / "cache"),
        )
        resolver = Path(__file__).parent.parent / "lisp/resolve.el"
        run(
            [
                os.environ["ELPACA_PURIFIER_EMACS"],
                "-Q",
                "--batch",
                "-L",
                str(core),
                "--load",
                str(resolver),
            ],
            env=env,
        )
        resolved = json.loads(resolution.read_text())
        entries, recipes = [], []
        seen = set()
        for item in resolved:
            for key in ("name", "repoKey", "build"):
                if not re.fullmatch(r"[A-Za-z0-9_.+-]+", item[key]) or item[key] in (
                    ".",
                    "..",
                ):
                    raise ValueError("Unsupported Elpaca directory name")
            if item["repoKey"] in seen:
                raise ValueError("Shared Elpaca repositories need a provider")
            seen.add(item["repoKey"])
            repo = Path(item["repo"])
            url = run(["git", "-C", str(repo), "remote", "get-url", "origin"]).strip()
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Use public HTTPS Git packages")
            rev = run(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()
            raw = subprocess.check_output(
                ["git", "-C", str(repo), "cat-file", "commit", rev]
            )
            tree = run(["git", "-C", str(repo), "ls-tree", "-r", rev])
            if any(line.startswith("160000 ") for line in tree.splitlines()):
                raise ValueError("Git submodules need a package provider")
            fetched = json.loads(
                run(
                    [
                        os.environ["ELPACA_PURIFIER_PREFETCH_GIT"],
                        "--url",
                        url,
                        "--rev",
                        rev,
                    ],
                    env=original_environment(),
                )
            )
            entries.append(
                dict(
                    path=item["repoKey"],
                    hash=fetched["hash"],
                    git=dict(
                        url=url,
                        rev=rev,
                        submodules=False,
                        leaveDotGit=True,
                        commitObject=dict(
                            object=base64.b64encode(raw).decode(), gitlinks=[]
                        ),
                    ),
                )
            )
            recipes.append(
                dict(
                    name=item["name"],
                    repo=item["repoKey"],
                    build=item["build"],
                    recipe=item["recipe"],
                )
            )
        data = dict(
            version=1,
            purifier="elpaca",
            sdk=os.environ["ELPACA_PURIFIER_SDK_VERSION"],
            native=private_lock.read_text(),
            recipes=recipes,
            entries=entries,
        )
        candidate = state / "elpaca-purifier.lock.json"
        candidate.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        from .runtime import execute

        if execute(
            root, candidate, private_lock, ["-Q", "--batch", "--load", str(config)]
        ):
            raise ValueError("Nix-delivered Elpaca packages failed verification")
        for target, payload in (
            (native, private_lock.read_bytes()),
            (companion, candidate.read_bytes()),
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = target.with_name(target.name + ".tmp")
            staged.write_bytes(payload)
            staged.replace(target)
