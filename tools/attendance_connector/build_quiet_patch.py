"""Build a small, deterministic Windows task repair package; no credentials."""
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
output = ROOT.parents[1] / 'pb_clock/static/downloads/Payobook-Quiet-Sync-Patch-1.zip'
output.parent.mkdir(parents=True, exist_ok=True)
files = [ROOT / 'Schedule.ps1', *sorted((ROOT / 'quiet_patch').iterdir())]
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        text = path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\n', '\r\n')
        data = text.encode('utf-8-sig' if path.suffix == '.ps1' else 'utf-8')
        info = zipfile.ZipInfo(path.name, date_time=(2026, 11, 19, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, data)
print(output)
print(hashlib.sha256(output.read_bytes()).hexdigest())
