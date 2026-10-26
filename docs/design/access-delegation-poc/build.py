#!/usr/bin/env python3
"""Embed the editable JavaScript into the standalone HTML document."""
from pathlib import Path

here = Path(__file__).resolve().parent
html = here.parent / "access-delegation-poc.html"
text = html.read_text()
before, rest = text.split("<script>", 1)
_, after = rest.split("</script>", 1)
script = (here / "app.js").read_text()
if "</script" in script.lower():
    raise SystemExit("JavaScript contains an unsafe closing script tag")
html.write_text(before + "<script>\n" + script + "</script>" + after)
print(f"Built {html.name}: {html.stat().st_size:,} bytes")
