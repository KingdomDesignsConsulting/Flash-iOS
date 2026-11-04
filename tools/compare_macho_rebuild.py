#!/usr/bin/env python3
"""Read-only arm64 Mach-O build comparison; UUID/signature are metadata only.
A normalized match is not a full-file hash match or a cache compatibility key.
"""
import argparse,hashlib,json,pathlib,struct

def describe(path):
 data=path.read_bytes();b=bytearray(data);assert len(b)>=32 and struct.unpack_from('<I',b)[0]==0xfeedfacf
 count,commands_size=struct.unpack_from('<II',b,16);assert 32+commands_size<=len(b);at=32;sections={};uuid=None;signature=None
 for _ in range(count):
  assert at+8<=32+commands_size;cmd,size=struct.unpack_from('<II',b,at);assert size>=8 and at+size<=32+commands_size
  if cmd==0x1b:
   assert size>=24;uuid=data[at+8:at+24].hex();b[at+8:at+24]=bytes(16)
  if cmd==0x1d:
   assert size>=16;offset,length=struct.unpack_from('<II',b,at+8);assert offset+length<=len(b);signature=dict(offset=offset,bytes=length);b[offset:offset+length]=bytes(length)
  if cmd==0x19:
   assert size>=72;n=struct.unpack_from('<I',b,at+64)[0];assert 72+n*80<=size
   for i in range(n):
    start=at+72+i*80;name=data[start:start+16].split(b'\0')[0].decode();seg=data[start+16:start+32].split(b'\0')[0].decode();length=struct.unpack_from('<Q',b,start+40)[0];offset=struct.unpack_from('<I',b,start+48)[0];kind=struct.unpack_from('<I',b,start+64)[0]&255;zero=kind in (1,12,18)
    if not zero:assert offset+length<=len(data)
    sections[seg+','+name]=dict(bytes=length,zerofill=zero,sha256=None if zero else hashlib.sha256(data[offset:offset+length]).hexdigest())
  at+=size
 assert at==32+commands_size and uuid and signature
 return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),uuid=uuid,signature=signature,normalized_sha256=hashlib.sha256(b).hexdigest(),sections=sections)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('original',type=pathlib.Path);p.add_argument('rebuild',type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);a=p.parse_args();left=describe(a.original);right=describe(a.rebuild);report=dict(original=left,rebuild=right,whole_file_exact=left['sha256']==right['sha256'],all_sections_exact=left['sections']==right['sections'],normalized_payload_exact=left['normalized_sha256']==right['normalized_sha256'],exclusions='Only LC_UUID 16-byte value and embedded code-signature payload; does not modify either file or cache identity')
 with a.out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print('REBUILD_PAYLOAD_EXACT',report['normalized_payload_exact'],'WHOLE_FILE_EXACT',report['whole_file_exact'])
if __name__=='__main__':main()
