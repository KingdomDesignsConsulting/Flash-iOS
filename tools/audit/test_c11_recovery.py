#!/usr/bin/env python3
"""Synthetic adversarial checks. No production files or processes accessed."""
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import c11_recovery as c

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='c11-d8-')
        self.root = Path(self.tmp.name).resolve()
        self.archive = self.root / 'fixture.tar'
        self.m = {'artifacts': [], 'gates': dict.fromkeys(c.GATES, True),
                  'expected_source_commit': '1'*40, 'source_evidence_commit': '1'*40,
                  'candidate_commit': '2'*40}
        with tarfile.open(self.archive, 'w') as tf:
            for role in sorted(c.REQUIRED_ROLES):
                data = ('SYNTHETIC ONLY: '+role).encode()
                item = {'path': role, 'role': role, 'sha256': c.digest(data), 'bytes': len(data), 'mode': 0o600}
                self.m['artifacts'].append(item)
                t = tarfile.TarInfo(role); t.size=len(data); t.mode=0o600
                tf.addfile(t, io.BytesIO(data))
        self.m['archive_sha256'] = c.digest(self.archive.read_bytes())
    def tearDown(self):
        self.tmp.cleanup()
    def reject(self, mutation, **kwargs):
        m=copy.deepcopy(self.m); mutation(m)
        with self.assertRaises((ValueError, OSError, tarfile.TarError)):
            c.verify(m,self.archive,complete=True,**kwargs)
    def test_positive_roundtrip(self):
        dest=self.root/'restored'; c.restore(self.m,self.archive,dest,True)
        for a in self.m['artifacts']:
            self.assertEqual(c.digest((dest/a['path']).read_bytes()),a['sha256'])
            self.assertEqual((dest/a['path']).stat().st_mode & 0o777,a['mode'])
    def test_missing_executable(self): self.reject(lambda m:m['artifacts'].pop(next(i for i,a in enumerate(m['artifacts']) if a['role']=='executable')))
    def test_wrong_binary_hash(self): self.reject(lambda m:m['artifacts'][0].update(sha256='0'*64))
    def test_wrong_shader(self): self.reject(lambda m:next(a for a in m['artifacts'] if a['role']=='shader').update(sha256='0'*64))
    def test_missing_launcher(self): self.reject(lambda m:next(a for a in m['artifacts'] if a['role']=='launcher').update(role='other'))
    def test_symlink_archive(self):
        link=self.root/'link'; link.symlink_to(self.archive)
        with self.assertRaises(ValueError): c.verify(self.m,link)
    def test_missing_cache(self): self.reject(lambda m:next(a for a in m['artifacts'] if a['role']=='warm_state_inventory').update(role='other'))
    def test_corrupt_archive(self):
        self.archive.write_bytes(b'corrupt')
        self.reject(lambda m:None)
    def test_incomplete_archive(self):
        self.m['artifacts'].append(dict(self.m['artifacts'][0],path='absent'))
        self.reject(lambda m:None)
    def test_wrong_model(self): self.reject(lambda m:next(a for a in m['artifacts'] if a['role']=='model_metadata').update(sha256='0'*64))
    def test_checkpoint_gate(self): self.reject(lambda m:m['gates'].update(checkpoint_policy_verified=False))
    def test_environment_gate(self): self.reject(lambda m:m['gates'].update(environment_complete=False))
    def test_conflicting_launchers(self): self.reject(lambda m:m['gates'].update(startup_unambiguous=False))
    def test_wrong_source(self): self.reject(lambda m:m.update(expected_source_commit='3'*40))
    def test_stale_pid_procedure(self): self.reject(lambda m:m['gates'].update(process_identity_recheck_required=False))
    def test_missing_rollback_step(self): self.reject(lambda m:m['gates'].update(rollback_steps_complete=False))
    def test_disk_space(self): self.reject(lambda m:None,free_bytes=1)
    def test_partial_restore(self):
        dest=self.root/'restored'
        with self.assertRaises(OSError): c.restore(self.m,self.archive,dest,True,fault_after=1)
        self.assertFalse(dest.exists()); self.assertFalse(list(self.root.glob('.c11-recovery-*')))
    def test_traversal(self): self.reject(lambda m:m['artifacts'][0].update(path='../escape'))
    def test_duplicate_role_path(self): self.reject(lambda m:m['artifacts'].append(m['artifacts'][0]))
    def test_archive_link_member(self):
        with tarfile.open(self.archive,'a') as tf:
            t=tarfile.TarInfo('symlink');t.type=tarfile.SYMTYPE;t.linkname='/etc/passwd';tf.addfile(t)
        self.m['archive_sha256']=c.digest(self.archive.read_bytes())
        self.reject(lambda m:None)
    def test_archive_hardlink_member(self):
        with tarfile.open(self.archive,'a') as tf:
            t=tarfile.TarInfo('hardlink');t.type=tarfile.LNKTYPE;t.linkname='executable';tf.addfile(t)
        self.m['archive_sha256']=c.digest(self.archive.read_bytes())
        self.reject(lambda m:None)
    def test_existing_destination(self):
        dest=self.root/'existing';dest.mkdir()
        with self.assertRaises(ValueError):c.restore(self.m,self.archive,dest)
    def test_placeholder_source(self): self.reject(lambda m:m.update(expected_source_commit='MANDATORY'))
    def test_artifact_permissions(self): self.reject(lambda m:m['artifacts'][0].update(mode=0o4755))

if __name__=='__main__': unittest.main(verbosity=2)
