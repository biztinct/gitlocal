"""Reproducible offline package assembly from hash-pinned official inputs.

Run after downloading Python's embeddable runtime and building/downloading the
pinned pure-Python wheels into the input directory. No customer files included.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    locks=json.loads((ROOT/'build-inputs.json').read_text())
    for name, expected in locks.items():
        assert hashlib.sha256((a.inputs/name).read_bytes()).hexdigest()==expected, 'Input hash mismatch: '+name
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)
        runtime=stage/'runtime';runtime.mkdir()
        for name in locks:
            dest=runtime if name.endswith('.zip') else runtime/'Lib'/'site-packages'
            with zipfile.ZipFile(a.inputs/name) as z:z.extractall(dest)
        (runtime/'python313._pth').write_text('python313.zip\n.\nLib/site-packages\n..\nimport site\n')
        for name in ['connector.py','Setup.ps1','Install.cmd','README.txt','build-inputs.json']:
            # Windows PowerShell 5.1 otherwise interprets UTF-8 as the ANSI codepage.
            if name == 'Setup.ps1':
                (stage/name).write_text((ROOT/name).read_text(encoding='utf-8-sig'), encoding='utf-8-sig')
            else:
                (stage/name).write_bytes((ROOT/name).read_bytes())
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    info=zipfile.ZipInfo(str(path.relative_to(stage)),date_time=(2026,11,13,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,path.read_bytes())
        print(json.dumps({'file':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'bytes':a.output.stat().st_size}))
if __name__=='__main__':main()
