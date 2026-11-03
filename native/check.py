import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from elpaca_purifier.layout import configure, launch

root, state, manifest_file, data_file, binary, config = sys.argv[1:7]
root, state = Path(root), Path(state)
manifest = json.loads(Path(manifest_file).read_text())
data = json.loads(Path(data_file).read_text())
env = configure(state / "session", state / "invocation", manifest, data)
args = [
    "--init-directory",
    str(root),
    "-Q",
    "--batch",
    "--load",
    str(root / config),
    "--eval",
    "(progn (elpaca-wait) (elpaca-process-queues))",
    *sys.argv[7:],
]
raise SystemExit(launch(binary, env, args))
