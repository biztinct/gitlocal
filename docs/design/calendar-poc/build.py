#!/usr/bin/env python3
"""Build the dependency-free, sample-data calendar design preview."""
from pathlib import Path

here = Path(__file__).resolve().parent
template = (here / 'shell.html').read_text()
css = (here / 'style.css').read_text()
js = (here / 'app.js').read_text()
assert '</script' not in js.lower()
assert '</style' not in css.lower()
output = here.parent / 'calendar-poc.html'
output.write_text(template.replace('/* STYLE */', css).replace('/* APP */', js))
print(f'Built {output.name}: {output.stat().st_size:,} bytes')
