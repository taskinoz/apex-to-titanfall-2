"""Read-only native draw metadata references; never modifies game binaries."""
import argparse,bisect,struct
from pathlib import Path
import capstone,pefile

def main():
 p=argparse.ArgumentParser();p.add_argument('module');p.add_argument('target',type=lambda x:int(x,0));p.add_argument('--function',action='store_true');a=p.parse_args()
 pe=pefile.PE(a.module);base=pe.OPTIONAL_HEADER.ImageBase
 cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);cs.detail=True
 entries=sorted((e.struct.BeginAddress,e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION);starts=[x[0] for x in entries]
 functions=set();refs=[]
 if a.function:
  functions.add(entries[bisect.bisect_right(starts,a.target)-1])
 else:
  section=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text');data=section.get_data();rva=section.VirtualAddress
  # Search common RIP-relative load/LEA encodings, then validate each instruction.
  for off in range(len(data)-7):
   if data[off] not in (0x48,0x4c,0x0f,0xf3):continue
   for ins in cs.disasm(data[off:off+12],base+rva+off,count=1):
    if any(o.type==capstone.CS_OP_MEM and o.mem.base==capstone.x86.X86_REG_RIP and ins.address+ins.size+o.mem.disp==base+a.target for o in ins.operands):
     at=rva+off;refs.append(hex(at));i=bisect.bisect_right(starts,at)-1
     if i>=0 and entries[i][0]<=at<entries[i][1]:functions.add(entries[i])
 out=['References: '+str(refs)]
 for lo,hi in sorted(functions):
  out.append('\nFUNCTION '+hex(lo)+' '+hex(hi))
  out.extend(hex(ins.address-base)+' '+ins.mnemonic+' '+ins.op_str for ins in cs.disasm(pe.get_data(lo,hi-lo),base+lo))
 target=Path('logs')/('native-reader-'+Path(a.module).stem+'-'+hex(a.target)+'.txt');target.write_text('\n'.join(out));print(target,len(functions),refs)
if __name__=='__main__':main()
