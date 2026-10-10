"""Regenerate tests/golden (run after an intentional output change; review the diff!).

Both projects: a manifest of SHA-256 hashes of every output. minimal10 also stores its CSV/JSON outputs in full."""

import hashlib
import json
import shutil

from golden_support import GOLDEN, outputs_for  # type: ignore[import-not-found]  # tests/ is on sys.path via PYTHONPATH

for name in ("minimal10", "satellite300"):
    files = outputs_for(name)
    target = GOLDEN / name
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    manifest = {fname: hashlib.sha256(data).hexdigest() for fname, data in files.items()}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if name == "minimal10":  # small text outputs are also stored in full, so a diff shows what changed
        for fname, data in files.items():
            if fname.endswith((".csv", ".json")):
                (target / fname).write_bytes(data)
    print(f"{name}: {len(files)} outputs")
