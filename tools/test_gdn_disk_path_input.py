#!/usr/bin/env python3
"""No-model regression for the diagnostic checkpoint-name failure."""
from pathlib import Path
import subprocess,tempfile
R=Path(__file__).resolve().parents[1];source=(R/'metal_infer/warm_state_cache.inc').read_text();a=source.index('static NSString *warm_state_zstd_path');b=source.index('static uint64_t warm_hash_bytes',a)
diagnostic=(R/'metal_infer/session_disk_oracle.inc').read_text();guard='if (!warm_state_identity_path(path) || !warm_state_zstd_path(warm_state_identity_path(path))) return 2;'
if diagnostic.index(guard)>diagnostic.index('reset_delta_net_state()'):raise RuntimeError('validation must precede state advancement')
code='#import <Foundation/Foundation.h>\n'+source[a:b]+'''\nint main(){@autoreleasepool{NSArray *paths=@[@"/private/tmp/gdn-new-profile.state",@"/private/tmp/flash-gdn-diagnostic-0000000000000001.state",@"/private/tmp/not-state"];for(int i=0;i<3;i++){NSString*p=paths[i];int valid=warm_state_identity_path(p)&&warm_state_zstd_path(warm_state_identity_path(p));if(valid!=(i==1))return 1;}return 0;}}'''
with tempfile.TemporaryDirectory(prefix='gdn-path-test-') as d:
 p=Path(d);(p/'test.m').write_text(code);subprocess.run(['clang','-fobjc-arc','-framework','Foundation',str(p/'test.m'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('PASS: three path cases and validation-before-state source guard')
