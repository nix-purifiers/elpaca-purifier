import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import original_environment, run
from .runtime import execute, realize


def locate(project=None, lock=None, native=None, flags=()):
    selected = project or os.environ.get("ELPACA_PURIFIER_PROJECT")
    for index, flag in enumerate(flags):
        if flag.startswith("--init-directory="):
            selected = flag.split("=", 1)[1]
        elif flag == "--init-directory" and index + 1 < len(flags):
            selected = flags[index + 1]
    if not selected:
        legacy = Path.home() / ".emacs.d"
        xdg = (
            Path(
                original_environment().get(
                    "XDG_CONFIG_HOME", str(Path.home() / ".config")
                )
            )
            / "emacs"
        )
        selected = legacy if legacy.exists() or not xdg.exists() else xdg
    root = Path(selected).expanduser().resolve()
    companion = Path(
        lock
        or os.environ.get("ELPACA_PURIFIER_LOCK", root / "elpaca-purifier.lock.json")
    ).resolve()
    native_file = Path(
        native or os.environ.get("ELPACA_PURIFIER_NATIVE_LOCK", root / "elpaca-lock.el")
    ).resolve()
    return root, companion, native_file


def main_impl():
    args = sys.argv[1:]
    if args[:1] == ["--native"]:
        flags = args[1:]
        root, companion, native = locate(flags=flags)
        if not companion.exists():
            print(
                "elpaca-purifier: no lockfile; using ordinary impure Emacs/Elpaca resolution",
                file=sys.stderr,
            )
            return subprocess.call(
                [os.environ["ELPACA_PURIFIER_EMACS"], *flags],
                env=original_environment(),
            )
        info = any(value in ("--version", "--help", "-h") for value in flags)
        bare_quick = any(
            value in ("-Q", "--quick", "-q", "--no-init-file") for value in flags
        ) and not any(
            value in ("-l", "--load", "--eval", "-f", "--funcall") for value in flags
        )
        if info or bare_quick:
            return subprocess.call(
                [os.environ["ELPACA_PURIFIER_EMACS"], *flags],
                env=original_environment(),
            )
        return execute(root, companion, native, flags)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--native-lock", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag", default="v0.1.0")
    opts, rest = parser.parse_known_args(args)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    root, companion, native = locate(opts.project, opts.lock, opts.native_lock)
    if opts.action == "lock":
        config = (opts.config or root / "init.el").resolve()
        capture(root, companion, native, config, opts.update)
    elif opts.action == "prefetch":
        realize(root, companion, native)
    elif opts.action == "exec":
        if not rest:
            raise ValueError("Pass a command after --")
        if Path(rest[0]).name == "emacs":
            return execute(root, companion, native, rest[1:])
        realize(root, companion, native)
        env = original_environment()
        env.update(
            ELPACA_PURIFIER_PROJECT=str(root),
            ELPACA_PURIFIER_LOCK=str(companion),
            ELPACA_PURIFIER_NATIVE_LOCK=str(native),
        )
        env["PATH"] = (
            os.environ["ELPACA_PURIFIER_SDK"] + "/bin" + os.pathsep + env["PATH"]
        )
        return subprocess.call(rest, env=env)
    else:
        realize(root, companion, native)
        expression = (
            "import "
            + json.dumps(
                os.environ["ELPACA_PURIFIER_SDK"]
                + "/lib/elpaca-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";nativeLockFile="
            + json.dumps(str(native))
            + ";}"
        )
        output = Path(
            run(
                [
                    "nix",
                    "build",
                    "--impure",
                    "--no-link",
                    "--print-out-paths",
                    "--expr",
                    expression,
                ]
            ).strip()
        )
        archive = output / "emacs-config.tar.gz"
        if opts.action == "bundle":
            print(archive)
        else:
            subprocess.run(
                [
                    os.environ["ELPACA_PURIFIER_GH"],
                    "release",
                    "upload",
                    opts.tag,
                    str(archive),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )
    return 0


def main():
    try:
        raise SystemExit(main_impl())
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print("elpaca-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
