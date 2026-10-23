"""Fail closed on protected content in Git candidates or a release directory."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BLOCKED={'.exe','.dll','.assets','.ress','.resource','.pdf','.zip','.png','.jpg','.jpeg','.wav','.mp3','.mp4','.unity','.asset','.pem','.key','.log'}
# Byte encodings prevent the scanner from tripping its own literal brand filter.
BRANDS=[bytes.fromhex('7373616679').decode(), bytes.fromhex('ebb0b0ed8ab8ec8bb8ed94bc').decode()]


def candidates(root):
    p=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=root,capture_output=True,check=True)
    return sorted(set(n for n in p.stdout.decode('utf-8').split('\0') if n))


def scan(root:Path,paths:list[str],private:Path|None=None):
    errors=[]
    reference_maps=[]
    if private and private.exists():
        for p in (private/'stages').glob('*.json'):
            try:
                spec=json.loads(p.read_text(encoding='utf-8'))
                reference_maps.append(spec['rows'])
                reference_maps.extend(v['rows'] for v in spec.get('variants',[]) if 'rows' in v)
            except (KeyError,ValueError):pass
    def map_key(rows):return tuple(' '.join(r.split()) for r in rows)
    known={map_key(rows) for rows in reference_maps}
    for name in paths:
        path=Path(name)
        parts=[x.lower() for x in path.parts]
        if any(x in ('.private_reference','runs','node_modules','.venv','__pycache__','.git') for x in parts):
            errors.append(f'{name}: private/runtime directory')
        if path.suffix.lower() in BLOCKED or path.name.lower().startswith(('level0','level1','level2','level3','level4')):
            errors.append(f'{name}: prohibited binary/media/reference format')
        full=root/path
        if full.is_symlink():
            errors.append(f'{name}: symlinks are not permitted in releases');continue
        if not full.is_file():
            errors.append(f'{name}: missing candidate');continue
        data=full.read_bytes()
        if data[:2]==b'MZ' or bytes.fromhex('556e6974794653') in data or len(data)>2_000_000:
            errors.append(f'{name}: executable/asset signature or excessive size')
        try:content=data.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'{name}: non-text file');continue
        if any(term in content.lower() or term in name.lower() for term in BRANDS):
            errors.append(f'{name}: original branding')
        if re.search(r'\b[A-Z]{4}(?:-[A-Z]{4}){3}\b',content):
            errors.append(f'{name}: possible authentication key')
        if re.search(r'(?i)(?:team_key|api_key|access_token|password)\s*[:=]\s*[\"\x27][^\"\x27\s]{6,}',content):
            errors.append(f'{name}: possible credential assignment')
        if full.suffix=='.json':
            try:
                payload=json.loads(content)
                if 'rows' in payload and map_key(payload['rows']) in known:
                    errors.append(f'{name}: matches a private reference map')
                if isinstance(payload,dict) and payload.get('format')=='tank-arena-replay-v1':
                    errors.append(f'{name}: run/replay data must stay local')
            except ValueError:pass
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,help='Inspect every file of a built release directory')
    args=p.parse_args()
    root=args.directory.resolve() if args.directory else ROOT
    paths=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()] if args.directory else candidates(root)
    errors=scan(root,paths,ROOT/'.private_reference')
    if errors:
        print('\n'.join(errors));raise SystemExit(1)
    print(f'PASS: {len(paths)} text-only release candidates; no protected-content signatures detected.')
    print('Scope: signatures + known local map matches; not a proof of content ownership.')


if __name__=='__main__':main()
