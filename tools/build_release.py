"""Build a local text-only ZIP strictly from Git tracked, reviewed source."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from release_check import ROOT,candidates,scan
import subprocess


def main():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    paths=sorted(p for p in paths if p)
    if not paths:
        raise SystemExit('Stage reviewed source with git add before building.')
    errors=scan(ROOT,paths,ROOT/'.private_reference')
    if errors:raise SystemExit('\n'.join(errors))
    folder=ROOT/'dist';folder.mkdir(exist_ok=True)
    dest=folder/'tank-arena-lab-0.1.0.zip'
    manifest={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for name in paths:z.write(ROOT/name,'tank-arena-lab/'+name)
        z.writestr('tank-arena-lab/RELEASE_MANIFEST.json',json.dumps(manifest,indent=2))
    print(f'Built {dest.name}: {len(paths)} verified source files; no upload.')


if __name__=='__main__':main()
