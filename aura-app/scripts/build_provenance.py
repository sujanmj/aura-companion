"""Bind generated preview output to the source inputs used for its build."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]


def checked_file(root, relative):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts:
        raise ValueError('Unsafe package path')
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlink is not permitted: {relative}')
    if not path.is_file():
        raise ValueError(f'Missing regular file: {relative}')
    return path


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(root, kind):
    if kind == 'web':
        directories = ['aura-app/src']
        names = ['aura-app/index.html', 'aura-app/package.json', 'aura-app/package-lock.json',
                 'aura-app/tsconfig.json', 'aura-app/vite.config.ts']
    elif kind == 'native':
        directories = ['aura-app/macos/AURACompanion/Sources']
        names = ['aura-app/macos/AURACompanion/Info.plist',
                 'aura-app/macos/AURACompanion/Entitlements.plist',
                 'aura-app/scripts/build-macos-app.sh']
    else:
        raise ValueError('Unknown build kind')
    names.append('aura-app/scripts/build_provenance.py')
    for directory in directories:
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            raise ValueError('Missing source directory or symlink')
        names.extend(path.relative_to(root).as_posix() for path in base.rglob('*') if path.is_file() or path.is_symlink())
    return {name: digest_file(checked_file(root, name)) for name in sorted(names)}


def output_files(root, directory, excluded=()):
    base = root / directory
    if not base.is_dir() or base.is_symlink():
        raise ValueError('Missing build directory or symlink')
    result = {}
    for path in sorted(base.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in build output')
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative not in excluded:
                result[relative] = digest_file(checked_file(root, relative))
    return result


def write_provenance(root, kind, directory):
    name = (Path(directory) / 'build-provenance.json').as_posix()
    content = {'format': 'aura-build-provenance-v1', 'kind': kind, 'inputs': inputs(root, kind)}
    if kind == 'web':
        content['outputs'] = output_files(root, directory, (name,))
        if f'{directory}/index.html' not in content['outputs']:
            raise ValueError('Build the web interface first')
    else:
        # Written before codesigning; final signed-file hashes go in release manifest.
        output_files(root, directory)
    (root / name).write_text(json.dumps(content, indent=2) + '\n')


def verify_provenance(root, kind, directory):
    name = (Path(directory) / 'build-provenance.json').as_posix()
    content = json.loads(checked_file(root, name).read_text())
    if (content.get('format') != 'aura-build-provenance-v1'
            or content.get('kind') != kind or content.get('inputs') != inputs(root, kind)):
        raise ValueError(f'Stale {kind} build: rebuild before packaging')
    if kind == 'web' and content.get('outputs') != output_files(root, directory, (name,)):
        raise ValueError('Web build output changed after building')


if __name__ == '__main__':
    write_provenance(ROOT, sys.argv[1], sys.argv[2])
