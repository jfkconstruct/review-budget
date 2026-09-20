"""Inline demo-data.json into demo.template.html and write demo.html.

    python projects/review-budget/export_demo.py --replicates 2000
    python projects/review-budget/build_demo.py

Single file on purpose: the demo is a link in an application, so it has to open from
a file:// path, an S3 bucket, or a static host without a fetch() that CORS will block.
The template stays hand-editable and the data stays regenerable; this joins them.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARK = "/*__DEMO_DATA__*/"

def main():
    tpl = (HERE / "demo.template.html").read_text(encoding="utf-8")
    data = (HERE / "demo-data.json").read_text(encoding="utf-8")
    if MARK not in tpl:
        raise SystemExit(f"{MARK} not found in demo.template.html")
    if "</script" in data:
        raise SystemExit("data would close the script tag early")
    out = HERE / "demo.html"
    out.write_text(tpl.replace(MARK, data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")

if __name__ == "__main__":
    main()
