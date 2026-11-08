#!/usr/bin/env python3
"""Build one self-contained HTML file, usable offline or on the preview host."""
from pathlib import Path
here = Path(__file__).resolve().parent
html = (here / 'shell.html').read_text()
html = html.replace('/* STYLES */', (here / 'style.css').read_text())
html = html.replace('/* SCRIPT */', (here / 'app.js').read_text())
(here.parent / 'workflow-studio-poc.html').write_text(html)
print('Built docs/design/workflow-studio-poc.html')
