"""Convert the bundled IBM Plex WOFF files to TTF for the PDF exporter (ReportLab reads TrueType only).

Dev-time only (needs fonttools). The TTF files are committed; run this only when the fonts change.
"""

from pathlib import Path

from fontTools.ttLib import TTFont

root = Path(__file__).resolve().parents[1] / "src"
src = root / "rvs_gui" / "assets" / "fonts"
dst = root / "rvs_core" / "exporters" / "fonts"
dst.mkdir(parents=True, exist_ok=True)
for name in ("IBMPlexSans-Regular", "IBMPlexSans-SemiBold", "IBMPlexSans-Italic", "IBMPlexMono-Regular"):
    font = TTFont(src / f"{name}.woff")
    font.flavor = None
    font.save(dst / f"{name}.ttf")
    print("wrote", dst / f"{name}.ttf")

# Small Latin subsets for the self-contained HTML export (embedded as data URIs).
from fontTools import subset  # noqa: E402

UNICODES = [*range(0x20, 0x7F), *range(0xA0, 0x100), 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026,
            0x2190, 0x2191, 0x2192, 0x2193, 0x2264, 0x2265, 0x00D7, 0x2212, 0x2260, 0x2248, 0x00B0, 0x00B1]  # fmt: skip
for name in ("IBMPlexSans-Regular", "IBMPlexSans-SemiBold", "IBMPlexSans-Italic", "IBMPlexMono-Regular"):
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["kern", "liga"]
    font = subset.load_font(str(src / f"{name}.woff"), opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    subset.save_font(font, str(dst / f"{name}.subset.woff"), opts)
    print("wrote", dst / f"{name}.subset.woff")
