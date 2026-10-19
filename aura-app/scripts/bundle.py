"""Package tested source + built UI. Never package databases, secrets, or media."""
from pathlib import Path
import hashlib
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'aura-app'
if not (APP/'dist/index.html').exists():
    raise SystemExit('Run npm run build first')
out=APP/'release'
out.mkdir(exist_ok=True)
archive=out/'AURA-Companion-0.2.0-preview.zip'
files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
# Only tracked source, excluding CI metadata. Builds add the compiled frontend.
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name in files:
        if not name or name.startswith('.git'):
            continue
        p=ROOT/name
        if p.is_file():
            z.write(p,'AURA-Companion/'+name)
    for p in (APP/'dist').rglob('*'):
        if p.is_file():z.write(p,'AURA-Companion/'+str(p.relative_to(ROOT)))
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(archive.with_suffix('.zip.sha256')).write_text(f'{digest}  {archive.name}\n')
print(archive)
