"""Read-only bounded disassembly of the installed native engine."""
import sys
from pathlib import Path
import capstone,pefile
p=pefile.PE(sys.argv[1],fast_load=True)
lo,hi=(int(x,0) for x in sys.argv[2:4]);base=p.OPTIONAL_HEADER.ImageBase
cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
out='\n'.join(f'{i.address-base:#x} {i.mnemonic} {i.op_str}' for i in cs.disasm(p.get_data(lo,hi-lo),base+lo))
path=Path('logs')/f'native-range-{lo:#x}.txt';path.write_text(out);print(path)
