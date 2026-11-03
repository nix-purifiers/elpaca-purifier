import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)

with tempfile.TemporaryDirectory(prefix="elpaca proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "configuration"
    shutil.copytree(repo / "examples/minimal", root)
    ambient = root / "elpaca/repos/f/preserve.txt"
    ambient.parent.mkdir(parents=True)
    ambient.write_text("existing checkout\n")
    env = dict(
        os.environ,
        XDG_CACHE_HOME=str(temp / "cache"),
        ELPACA_PURIFIER_PROJECT=str(root),
        EMACSLOADPATH="/nonexistent/poison",
    )

    def call(name, *args, success=True, extra=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=root,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    result_file = temp / "result.json"
    assertion = (
        "(progn (require 'json) (require 'f) (with-temp-file "
        + json.dumps(str(result_file))
        + " (insert (json-encode (list (cons 'answer purifier-answer) (cons 'source (file-truename (symbol-file 'f-filename))))))))"
    )

    def editor(extra=None):
        result_file.unlink(missing_ok=True)
        call(
            "emacs",
            "-Q",
            "--batch",
            "--load",
            str(root / "init.el"),
            "-f",
            "elpaca-wait",
            "--eval",
            assertion,
            extra=extra,
        )
        data = json.loads(result_file.read_text())
        assert data["source"].startswith("/nix/store/"), data
        return data["answer"]

    init = root / "init.el"
    original = init.read_text()
    companion, native = root / "elpaca-purifier.lock.json", root / "elpaca-lock.el"
    before = companion.read_bytes(), native.read_bytes()
    for answer in [42, 43, 42]:
        init.write_text(
            original.replace("purifier-answer 42", "purifier-answer " + str(answer))
        )
        assert editor() == answer
    assert before == (companion.read_bytes(), native.read_bytes())
    assert ambient.read_text() == "existing checkout\n"
    upstream_expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {};in (p.emacsPackagesFor p.emacs-nox).elpaca.src"
    )
    upstream = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--no-link",
                "--print-out-paths",
                "--expr",
                upstream_expression,
            ],
            text=True,
        ).strip()
    )
    installer = next(
        block.split("\n", 1)[1]
        for block in (upstream / "README.md").read_text().split("```")
        if block.startswith("emacs-lisp\n(defvar elpaca-installer-version")
    )
    init.write_text(installer + "\n" + original)
    assert editor() == 42
    init.write_text(
        original
        + '\n(add-hook \'elpaca-after-init-hook (lambda () (unless (= purifier-answer 42) (error "Native startup failed")) (kill-emacs 0)) t)\n'
    )
    call("emacs", "--fg-daemon=elpaca-purifier-proof")
    init.write_text(original)
    profiles = list((temp / "cache/elpaca-purifier").glob("*/*/environment-profile"))
    assert len(profiles) == 1
    profile = profiles[0]
    assert str(sdk) in subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    output = Path(json.loads(profile.read_text())["output"])
    manifest = json.loads(output.read_text())
    assert not Path(manifest["builds"]).stat().st_mode & 0o222
    persistent = profile.parent / "session/state/preserve"
    persistent.parent.mkdir(parents=True, exist_ok=True)
    persistent.write_text("editor state")
    assert editor() == 42 and persistent.read_text() == "editor state"
    init.write_text(
        original.replace(
            "(elpaca f", '(elpaca (f :host github :repo "fixture/changed" :inherit nil)'
        )
    )
    denied = call("emacs", "-Q", "--batch", "--load", str(init), success=False)
    assert "Nix-resolved" in denied.stderr, denied
    init.write_text(original)
    denied = call(
        "emacs",
        "-Q",
        "--batch",
        "--load",
        str(init),
        "-f",
        "elpaca-wait",
        "--eval",
        "(elpaca-fetch 'f)",
        success=False,
    )
    assert "Nix-resolved" in denied.stderr, denied
    call(
        "emacs",
        "-Q",
        "--batch",
        "--load",
        str(init),
        "-f",
        "elpaca-wait",
        "--eval",
        '(let ((default-directory (elpaca<-repo-dir (elpaca-get \'f)))) (unless (= (length (car (process-lines "git" "log" "-1" "--format=%H"))) 40) (error "Native Git metadata failed")))',
    )

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        program = (
            "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:"
            + str(server.server_port)
            + "/').read().decode())"
        )
        network = (
            "(with-temp-buffer (unless (zerop (call-process "
            + json.dumps(sys.executable)
            + ' nil t nil "-c" '
            + json.dumps(program)
            + ')) (error "Root networking failed")) (write-region (point-min) (point-max) '
            + json.dumps(str(result_file))
            + "))"
        )
        call("emacs", "-Q", "--batch", "--load", str(init), "--eval", network)
        assert result_file.read_text().strip() == "42"
    finally:
        server.shutdown()
        server.server_close()
    external_companion, external_native = temp / "companion.json", temp / "native.el"
    companion.rename(external_companion)
    native.rename(external_native)
    external = {
        "ELPACA_PURIFIER_LOCK": str(external_companion),
        "ELPACA_PURIFIER_NATIVE_LOCK": str(external_native),
    }
    assert editor(extra=external) == 42
    archive = Path(call("elpaca-purifier", "bundle", extra=external).stdout.strip())
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as released:
        released.extractall(consumer, filter="data")
    assert (consumer / "elpaca/builds/f/f.elc").stat().st_mode & 0o200
    assert (consumer / "elpaca/repos/f/.git/config").stat().st_mode & 0o200
    native_origin = subprocess.check_output(
        ["git", "-C", str(consumer / "elpaca/repos/f"), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    assert native_origin == next(
        entry["git"]["url"]
        for entry in json.loads(external_companion.read_text())["entries"]
        if entry["path"] == "f"
    )
    expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {};in p.emacs-nox"
    )
    ordinary = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--no-link",
                "--print-out-paths",
                "--expr",
                expression,
            ],
            text=True,
        ).strip()
    )
    ordinary_env = dict(os.environ, XDG_CACHE_HOME=str(temp / "consumer-cache"))
    ordinary_env.pop("EMACSLOADPATH", None)
    result = subprocess.run(
        [
            ordinary / "bin/emacs",
            "--init-directory",
            str(consumer),
            "-Q",
            "--batch",
            "-L",
            str(consumer / "elpaca/repos/elpaca"),
            "--load",
            str(consumer / "init.el"),
            "-f",
            "elpaca-wait",
            "--eval",
            '(progn (require \'f) (unless (and (equal (f-filename "/fixture/42") "42") (file-in-directory-p (symbol-file \'f-filename) default-directory)) (error "Native consumer failed")))',
        ],
        cwd=consumer,
        env=ordinary_env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result
    fake = temp / "fake-gh"
    published = temp / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath("
        + repr(str(published))
        + ").write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake.chmod(0o755)
    call(
        "elpaca-purifier",
        "publish",
        "--tag",
        "v-proof",
        extra=dict(external, ELPACA_PURIFIER_GH=str(fake)),
    )
    assert json.loads(published.read_text()) == [
        "release",
        "upload",
        "v-proof",
        str(archive),
        "--clobber",
    ]
    fallback = temp / "fallback"
    fallback.mkdir()
    result = call(
        "emacs", "--version", extra={"ELPACA_PURIFIER_PROJECT": str(fallback)}
    )
    assert "ordinary impure" in result.stderr
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    direct_env = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/elpaca-purifier"),
        ELPACA_PURIFIER_PROJECT=str(fallback),
        ELPACA_PURIFIER_EMACS=str(fake),
    )
    result = subprocess.run(
        ["python3", "-m", "elpaca_purifier.cli", "--native"],
        env=direct_env,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result

print(
    "Native Elpaca source edits, recipe guards, readonly Git and builds, networking, native source consumer, publication and fallback passed"
)
