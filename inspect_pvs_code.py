"""Read-only executable references for native PVS diagnostics."""
import struct
from pathlib import Path
import capstone,pefile
ROOT=Path(__file__).resolve().parent
def main():
 path=Path('D:/Games/Titanfall2/bin/x64_retail/client.dll');pe=pefile.PE(str(path));base=pe.OPTIONAL_HEADER.ImageBase;cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);cs.detail=True
 raw=path.read_bytes();strings={s:base+pe.get_rva_from_offset(raw.index(s.encode()+b'\0')) for s in ('pvs_extraCull','pvs_debug','PvsMaster','PvsCullAccessPath')};hits=[]
 # Locate RIP-relative instruction references; avoid disassembling data islands.
 text=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text');data=text.get_data();rva=text.VirtualAddress
 for off in range(len(data)-7):
  if data[off:off+2] not in (b'\x48\x8d',b'\x4c\x8d'):continue
  if data[off+2]&0xc7!=5:continue
  addr=base+rva+off+7+struct.unpack_from('<i',data,off+3)[0]
  for s,target in strings.items():
   if addr==target:hits.append((s,rva+off))
 out=['Strings: '+str({k:hex(v-base) for k,v in strings.items()})]
 for s,at in hits:
  out.append('\nReference '+s+' '+hex(at));begin=at-96
  for ins in cs.disasm(pe.get_data(begin,320),base+begin):out.append(hex(ins.address-base)+' '+ins.mnemonic+' '+ins.op_str)
 (ROOT/'logs/pvs-code-references.txt').write_text('\n'.join(out));print('\n'.join(out))
if __name__=='__main__':main()
