"""Mark the packages that are installed but not part of the release bundle in a CycloneDX SBOM (in place).

    python scripts/sbom_post.py dist/rvs-sbom.cdx.json

The SBOM tool lists everything pip installed (Doorstop pulls in `requests`, `urllib3`, ... that the bundle excludes, see
packaging/rvs.spec). Each such component gets the property ``rvs:in-bundle`` = ``false`` so a reader is not misled. The
file is rewritten with sorted keys, so it is byte-identical for identical input.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_licences import EXCLUDED_FROM_BUNDLE  # noqa: E402


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: sbom_post.py SBOM.cdx.json", file=sys.stderr)
        return 2
    path = Path(argv[0])
    bom = json.loads(path.read_text(encoding="utf-8"))
    excluded = {_normalise(n) for n in EXCLUDED_FROM_BUNDLE}
    marked = 0
    for component in bom.get("components", []):
        if _normalise(str(component.get("name", ""))) in excluded:
            props = [p for p in component.get("properties", []) if p.get("name") != "rvs:in-bundle"]
            props.append({"name": "rvs:in-bundle", "value": "false"})
            component["properties"] = sorted(props, key=lambda p: (p["name"], p["value"]))
            marked += 1
    path.write_text(
        json.dumps(bom, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"marked {marked} component(s) as not in the bundle in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
