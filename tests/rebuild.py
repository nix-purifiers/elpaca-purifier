from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
subprocess.run(
    [
        "nix",
        "build",
        "--rebuild",
        "--no-link",
        str(repo) + "#checks." + system + ".environment.builds",
    ],
    check=True,
)
print("Native Elpaca autoloads, byte compilation and documentation rebuilt identically")
