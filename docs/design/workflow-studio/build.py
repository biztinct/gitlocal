#!/usr/bin/env python3
"""Build the product UI as one offline-capable HTML artifact."""
import base64
from pathlib import Path
HERE = Path(__file__).resolve().parent

def render():
    style = (HERE / 'style.css').read_text().replace('/* FONT */', base64.b64encode((HERE / 'InterVariable.woff2').read_bytes()).decode())
    style = '/* Embedded Inter font licence:\n' + (HERE / 'Inter-OFL.txt').read_text().replace('*/', '* /') + '\n*/\n' + style
    script = '\n'.join((HERE / name).read_text() for name in ('ui.js', 'forms-model.js', 'model.js', 'integration-model.js', 'modules-model.js', 'flow-model.js', 'research.js', 'forms-ui.js', 'modules-ui.js', 'flow-ui.js', 'app.js'))
    return (HERE / 'shell.html').read_text().replace('/* STYLES */', style).replace('/* SCRIPT */', script)

if __name__ == '__main__':
    (HERE.parent / 'workflow-studio-poc.html').write_text(render())
    print('Built docs/design/workflow-studio-poc.html')
