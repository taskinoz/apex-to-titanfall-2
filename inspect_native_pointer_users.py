"""Read-only RIP-relative users in a bounded native data-address range."""
import bisect,sys
from pathlib import Path
import capstone,pefile
pe=pefile.PE(sys.argv[1]);lo=int(sys.argv[2],0);hi=lo+int(sys.argv[3],0);base=pe.OPTIONAL_HEADER.ImageBase
cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);cs.detail=True
entries=sorted((e.struct.BeginAddress,e.struct.EndAddress) for e in pe.DIRECTORY_ENTRY_EXCEPTION);starts=[x[0] for x in entries]
s=next(s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text');d=s.get_data();refs=[];functions=set()
for off in range(len(d)-7):
    if d[off] not in (0x48,0x4c,0x0f,0xf3):continue
    for ins in cs.disasm(d[off:off+12],base+s.VirtualAddress+off,count=1):
        targets=[ins.address+ins.size+o.mem.disp-base for o in ins.operands if o.type==capstone.CS_OP_MEM and o.mem.base==capstone.x86.X86_REG_RIP]
        if any(lo<=t<hi for t in targets):
            at=s.VirtualAddress+off;refs.append((hex(at),ins.mnemonic,ins.op_str));i=bisect.bisect_right(starts,at)-1
            if i>=0 and entries[i][0]<=at<entries[i][1]:functions.add(entries[i])
out=['References: '+str(refs)]
for a,b in sorted(functions):
    out.append('\nFUNCTION '+hex(a)+' '+hex(b));out.extend(hex(ins.address-base)+' '+ins.mnemonic+' '+ins.op_str for ins in cs.disasm(pe.get_data(a,b-a),base+a))
path=Path('logs')/f'native-pointer-{lo:#x}.txt';path.write_text('\n'.join(out));print(path,refs)
