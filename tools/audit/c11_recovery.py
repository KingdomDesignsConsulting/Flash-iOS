#!/usr/bin/env python3
"""Offline archive verification only. Never discovers, starts or stops a service.

Manifest roles bind to archive paths, sizes, modes and hashes. This establishes
byte preservation, not truth of deployment attestations or source provenance.
Only a trusted independently captured manifest is an authentication anchor.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile

MAX_PACKAGE_BYTES = 64 * 1024 * 1024  # Small model-free packages only; not cache archives.

REQUIRED_ROLES = {'executable', 'shader', 'launcher', 'configuration', 'model_metadata',
                  'runtime_dependency', 'warm_state_inventory', 'warm_tools_inventory'}
GATES = ('launcher_verified', 'environment_complete', 'startup_unambiguous',
         'source_recovery_policy_accepted', 'model_verified', 'checkpoint_policy_verified',
         'cache_archives_verified', 'process_identity_recheck_required',
         'rollback_steps_complete')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe_name(name):
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and str(p) == name and '\\' not in name

def verify(manifest, archive, complete=False, free_bytes=None):
    """Return verified bytes keyed by relative path; fail before any extraction."""
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('archive must be a regular non-symlink file')
    if archive.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError('archive exceeds small-rehearsal limit')
    if digest(archive.read_bytes()) != manifest.get('archive_sha256'):
        raise ValueError('archive hash mismatch')
    records = manifest.get('artifacts')
    if not isinstance(records, list) or not records:
        raise ValueError('no artifacts')
    expected = {}
    for item in records:
        name = item.get('path', '')
        if not safe_name(name) or name in expected:
            raise ValueError('unsafe/duplicate artifact path')
        if not isinstance(item.get('role'), str) or not item['role']:
            raise ValueError('missing artifact role')
        if not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256', ''))):
            raise ValueError('invalid artifact digest')
        if type(item.get('bytes')) is not int or item['bytes'] < 0:
            raise ValueError('invalid artifact size')
        if type(item.get('mode')) is not int or item['mode'] & ~0o777:
            raise ValueError('unsafe file permissions')
        expected[name] = item
    total = sum(x['bytes'] for x in records)
    if total > MAX_PACKAGE_BYTES:
        raise ValueError('expanded package exceeds small-rehearsal limit')
    if free_bytes is not None and free_bytes < total * 2 + 1024 * 1024:
        raise ValueError('insufficient staging disk space')
    if complete:
        if not REQUIRED_ROLES <= {x['role'] for x in records}:
            raise ValueError('missing rollback dependency role')
        if not all(manifest.get('gates', {}).get(k) is True for k in GATES):
            raise ValueError('unresolved deployment/recovery gate')
        for key in ('expected_source_commit', 'candidate_commit'):
            if not re.fullmatch('[0-9a-f]{40}', str(manifest.get(key, ''))):
                raise ValueError('unresolved source/candidate commit')
        if manifest.get('source_evidence_commit') != manifest['expected_source_commit']:
            raise ValueError('source evidence mismatch')
    verified = {}
    with tarfile.open(archive, 'r:*') as tf:
        for member in tf:
            if member.name in verified or member.name not in expected or not member.isfile():
                raise ValueError('unexpected/duplicate/nonregular archive member')
            item = expected[member.name]
            if member.size != item['bytes'] or member.mode != item['mode']:
                raise ValueError('archive size/mode mismatch')
            stream = tf.extractfile(member)
            content = stream.read(item['bytes'] + 1)
            if len(content) != item['bytes'] or digest(content) != item['sha256']:
                raise ValueError('artifact hash mismatch')
            verified[member.name] = content
    if verified.keys() != expected.keys():
        raise ValueError('incomplete archive')
    return verified

def restore(manifest, archive, destination, complete=False, fault_after=None):
    """Publish into a new disposable directory only; no overlays, no tar extract."""
    if destination.exists() or destination.is_symlink():
        raise ValueError('destination must not exist')
    parent = destination.parent
    if parent.resolve() != parent or not parent.is_dir():
        raise ValueError('destination parent must be a canonical existing directory')
    verified = verify(manifest, archive, complete, shutil.disk_usage(parent).free)
    stage = Path(tempfile.mkdtemp(prefix='.c11-recovery-', dir=parent))
    try:
        for n, item in enumerate(manifest['artifacts']):
            p = stage / item['path']
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as f:
                f.write(verified[item['path']])
            p.chmod(item['mode'])
            if digest(p.read_bytes()) != item['sha256']:
                raise ValueError('restoration readback mismatch')
            if fault_after == n:
                raise OSError('injected partial restoration failure')
        # Recheck before publication. Not a concurrent hostile-filesystem tool.
        if destination.exists() or destination.is_symlink():
            raise ValueError('destination appeared during staging')
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--archive', required=True, type=Path)
    p.add_argument('--restore-to', type=Path)
    p.add_argument('--require-complete', action='store_true')
    a = p.parse_args()
    try:
        if a.manifest.is_symlink():
            raise ValueError('manifest symlink rejected')
        m = json.loads(a.manifest.read_text())
        if a.restore_to:
            restore(m, a.archive, a.restore_to, a.require_complete)
        else:
            verify(m, a.archive, a.require_complete)
    except (ValueError, OSError, tarfile.TarError, KeyError, TypeError) as e:
        print('FAIL:', e)
        return 1
    print('PASS: offline artifact bytes/modes/roles; NOT service rollback or provenance authorization')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
