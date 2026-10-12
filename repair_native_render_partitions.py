"""Sort within native opaque / transparent world ranges, preserving geometry."""
import struct
from audit_world_draw_budget import static_draw_key
from preview_visibility import validate_visibility
from repair_preview_index_padding import validate_index_padding
def reorder(l):
    n=len(l[0x50])//28
    if len(l[0xe])!=32 or struct.unpack_from('<2I',l[0xe],24)!=(0,n) or l.get(0x64,b''):raise ValueError('Unsupported model/CSM references')
    records=[l[0x50][i*28:i*28+28] for i in range(n)]
    if any(struct.unpack_from('<I',r,24)[0]&0x600!=0x200 for r in records):raise ValueError('Unsupported vertex format')
    order=sorted(range(n),key=lambda i:(bool(struct.unpack_from('<I',records[i],24)[0]&0x10),static_draw_key(records[i])))
    inverse=[0]*n
    for new,old in enumerate(order):inverse[old]=new
    refs=[inverse[i] for i, in struct.iter_unpack('<H',l[0x78])]
    opaque=sum(not bool(struct.unpack_from('<I',r,24)[0]&0x10) for r in records);level=bytearray(l[0x7b]);struct.pack_into('<3I',level,0,opaque,opaque,n)
    changes={0x50:b''.join(records[i] for i in order),0x51:b''.join(l[0x51][i*32:i*32+32] for i in order),
        0x78:struct.pack('<'+'H'*len(refs),*refs),0x7b:level}
    validate_visibility(l[0x77],changes[0x78],l[0x79],changes[0x51]);validate_index_padding(changes[0x50],l[0x4f],l[0x52])
    return changes,order,inverse
