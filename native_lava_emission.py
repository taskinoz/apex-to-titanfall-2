"""Add source-masked HDR emission to the retained native world blend shader.

Only cloned native sample/arithmetic instructions are inserted. Existing blend,
lighting, fog, motion/depth outputs and vertex shaders remain intact. Container
hash padding follows Microsoft's public DirectXShaderCompiler DxilHash design;
it is a format checksum, not a security hash.
"""
import ctypes
import math
import re
import struct


def checksum(data):
    n=len(data);end=n//64*64;tail=data[end:]
    blocks=[data[i:i+64] for i in range(0,end,64)]
    if len(tail)<56:
        blocks.append(struct.pack('<I',n*8)+tail+b'\x80'+bytes(55-len(tail))+struct.pack('<I',n*2|1))
    else:
        blocks.extend([tail+b'\x80'+bytes(63-len(tail)),struct.pack('<I',n*8)+bytes(56)+struct.pack('<I',n*2|1)])
    state=[0x67452301,0xefcdab89,0x98badcfe,0x10325476]
    shifts=([7,12,17,22]*4+[5,9,14,20]*4+[4,11,16,23]*4+[6,10,15,21]*4)
    for block in blocks:
        words=struct.unpack('<16I',block);a,b,c,d=state
        for i in range(64):
            if i<16:f,g=(b&c)|(~b&d),i
            elif i<32:f,g=(b&d)|(c&~d),(5*i+1)%16
            elif i<48:f,g=b^c^d,(3*i+5)%16
            else:f,g=c^(b|~d),(7*i)%16
            v=(a+f+int(abs(math.sin(i+1))*2**32)+words[g])&0xffffffff;s=shifts[i]
            a,d,c,b=d,c,b,(b+((v<<s)|(v>>(32-s))))&0xffffffff
        state=[(x+y)&0xffffffff for x,y in zip(state,(a,b,c,d))]
    return struct.pack('<4I',*state)


def chunks(dx):
    if dx[:4]!=b'DXBC' or len(dx)!=struct.unpack_from('<I',dx,24)[0]:raise ValueError('Invalid DXBC extent')
    if dx[4:20]!=checksum(dx[20:]):raise ValueError('Invalid DXBC checksum')
    count=struct.unpack_from('<I',dx,28)[0];result=[]
    for offset in struct.unpack_from('<'+'I'*count,dx,32):
        tag,size=struct.unpack_from('<4sI',dx,offset)
        if offset+8+size>len(dx):raise ValueError('Invalid shader chunk')
        result.append((tag,dx[offset+8:offset+8+size]))
    return result


def container(rows):
    result=bytearray(b'DXBC'+bytes(16)+struct.pack('<3I',1,0,len(rows))+bytes(4*len(rows)))
    for i,(tag,payload) in enumerate(rows):
        struct.pack_into('<I',result,32+4*i,len(result))
        result.extend(struct.pack('<4sI',tag,len(payload))+payload)
    struct.pack_into('<I',result,24,len(result));result[4:20]=checksum(result[20:]);return bytes(result)


def disassembly(dx):
    library=ctypes.WinDLL('d3dcompiler_47.dll');fn=library.D3DDisassemble
    fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)];fn.restype=ctypes.c_long
    blob=ctypes.c_void_p()
    if fn(dx,len(dx),0,None,ctypes.byref(blob)):raise ValueError('D3DDisassemble rejected shader')
    table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    pointer=ctypes.WINFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p)(table[3])(blob)
    size=ctypes.WINFUNCTYPE(ctypes.c_size_t,ctypes.c_void_p)(table[4])(blob)
    text=ctypes.string_at(pointer,size).decode().rstrip('\0')
    ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(blob)
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(('//','{'))][1:]


def instructions(payload):
    words=list(struct.unpack('<'+'I'*(len(payload)//4),payload));result=[];i=2
    if words[1]!=len(words):raise ValueError('Invalid shader token extent')
    while i<len(words):
        n=(words[i]>>24)&127
        if words[i]&0x7ff==53:n=words[i+1]  # CUSTOMDATA
        if n<1 or i+n>len(words):raise ValueError('Invalid shader instruction extent')
        result.append(words[i:i+n]);i+=n
    return words[:2],result


def operands(tokens):
    i=1;extended=bool(tokens[0]&0x80000000)
    while extended:
        extended=bool(tokens[i]&0x80000000);i+=1
    while i<len(tokens):
        start=i;token=tokens[i];kind=(token>>12)&255;dimensions=(token>>20)&3;i+=1
        extended=bool(token&0x80000000)
        while extended:extended=bool(tokens[i]&0x80000000);i+=1
        indices=[]
        for axis in range(dimensions):
            representation=(token>>(22+3*axis))&7
            if representation!=0:raise ValueError('Only immediate operand indices supported in emission fragment')
            indices.append(i);i+=1
        if kind==4:i+=1 if token&3==1 else 4  # immediate32
        elif kind==5:raise ValueError('Unexpected immediate64 operand')
        yield start,kind,indices


def remap(tokens,temps=None,resources=None):
    out=list(tokens)
    for at,kind,indices in operands(tokens):
        if kind==0 and temps and tokens[indices[0]] in temps:out[indices[0]]=temps[tokens[indices[0]]]
        if kind==7 and resources and tokens[indices[0]] in resources:out[indices[0]]=resources[tokens[indices[0]]]
    return out


def emission_bindings(payload):
    """Retain native reflection data and describe the two new texture bindings."""
    out=bytearray(payload);count,offset=struct.unpack_from('<2I',out,8)
    records=[list(struct.unpack_from('<8I',out,offset+i*32)) for i in range(count)]
    textures={r[5]:r for r in records if r[1]==2}
    if 4 in textures or 27 in textures:raise ValueError('Emission bindings already present')
    for slot,name,source in ((4,b'lavaLayer0Emissive\0',0),(27,b'lavaLayer1Emissive\0',23)):
        entry=list(textures[source]);entry[0]=len(out);entry[5]=slot;out.extend(name)
        position=next((i for i,r in enumerate(records) if r[1]==2 and r[5]>slot),None)
        if position is None:raise ValueError('Native resource order changed')
        records.insert(position,entry)
    out.extend(bytes((-len(out))%4));table=len(out)
    for record in records:out.extend(struct.pack('<8I',*record))
    struct.pack_into('<2I',out,8,len(records),table);return bytes(out)


def patch(dx,hdr):
    if b'CBufUberDynamicDebug\0' in dx:
        return dx,dict(debug_variant_preserved=True)
    rows=chunks(dx);hdrrows=chunks(hdr)
    code=next(p for t,p in rows if t in (b'SHEX',b'SHDR'))
    _,hcode=instructions(next(p for t,p in hdrrows if t in (b'SHEX',b'SHDR')))
    htext=disassembly(hdr);header,ops=instructions(code);text=disassembly(dx)
    if len(ops)!=len(text) or len(hcode)!=len(htext):raise ValueError('Disassembly/token instruction alignment changed')
    def one(lines,predicate):
        ids=[i for i,line in enumerate(lines) if predicate(line)]
        if len(ids)!=1:raise ValueError('Native shader anchor is not unique: '+str(ids))
        return ids[0]
    decl=one(text,lambda s:s.startswith('dcl_temps '));n=int(text[decl].split()[1])
    weight=one(text,lambda s:s=='add_sat r0.z, r0.z, r0.w')
    start=one(text,lambda s:s.startswith('sample_indexable') and ' t0.' in s)
    second_sample=one(text,lambda s:s.startswith('sample_indexable') and ' t23.' in s)
    subtract=one(text,lambda s:s=='add r2.xyz, -r1.xyzx, r2.xyzx')
    blend=one(text,lambda s:s=='mad r1.xyz, r0.zzzz, r2.xyzx, r1.xyzx')
    # Same placement as native HDR: after diffuse compression, before native fog.
    finish=one(text,lambda s:bool(re.fullmatch(r'mul r0.xyz, r0.xyzx, r\d+\.xxxx',s)))
    resource=one(htext,lambda s:s.startswith('dcl_resource_texture2d ') and s.endswith(' t4'))
    multiply=one(htext,lambda s:s=='mul r1.xyz, r1.xyzx, cb0[10].xyzx')
    # Save the exact blend weight before the native lighting code reuses r0.z.
    blend_operands=list(operands(ops[blend]));weight_header=ops[blend][blend_operands[1][0]]
    destination=(ops[start][list(operands(ops[start]))[0][0]]&~0xf0)|0x10
    capture=[0x05000036,destination,n+2,weight_header,0]
    fragment=[]
    for token in (ops[i] for i in (start,second_sample,subtract,blend)):
        changed=remap(token,{0:n+2,1:n,2:n+1},{0:4,23:27})
        for at,kind,indices in operands(changed):
            if kind==0 and changed[indices[0]]==n+2:changed[at]&=~0xff0  # weight.xxxx
        fragment.append(changed)
    fragment.append(remap(hcode[multiply],{1:n}))
    # add r0.xyz, r0.xyzx, rN.xyzx; native operand encodings come from the blend add.
    plain=ops[blend];plain_parts=list(operands(plain));src=plain[plain_parts[-1][0]:plain_parts[-1][0]+2]
    dest=plain[plain_parts[0][0]:plain_parts[0][0]+2]
    addition=[0x07000000|(ops[subtract][0]&0x7ff),dest[0],0,src[0],0,src[0],n]
    fragment.append(addition)
    second=list(hcode[resource])
    for at,kind,indices in operands(second):
        if kind==7:second[indices[0]]=27;break
    extra_declarations=[hcode[resource],second]
    new=[]
    for i,tokens in enumerate(ops):
        if i==decl:new.extend(extra_declarations);tokens=[tokens[0],n+3]
        new.append(tokens)
        if i==weight:new.append(capture)
        if i==finish:new.extend(fragment)
    flat=header+[w for instruction in new for w in instruction];flat[1]=len(flat)
    result=container([(tag,struct.pack('<'+'I'*len(flat),*flat) if tag in (b'SHEX',b'SHDR')
                       else emission_bindings(payload) if tag==b'RDEF' else payload) for tag,payload in rows])
    chunks(result);disassembly(result)
    return result,dict(original_temps=n,added_temps=3,added_instructions=len(fragment)+1,blend_weight_preserved=True,emission_before_native_fog=True)


def patch_msw(data,hdr):
    pixel_start,vertex_start=struct.unpack_from('<2I',data,29)
    count=data[pixel_start+7];block=bytearray(data[pixel_start:pixel_start+16+count*24]);proof=[]
    for i in range(count):
        original=pixel_start+16+i*24;size,relative=struct.unpack_from('<2I',data,original)
        if size>=len(data):continue  # retained aliases/absent variants
        dx=data[original+relative:original+relative+size]
        result,record=patch(dx,hdr);record['variant']=i;proof.append(record)
        dest=16+i*24;struct.pack_into('<2I',block,dest,len(result),len(block)-dest);block.extend(result)
    header=bytearray(data[:pixel_start]);struct.pack_into('<H',header,21,28)
    struct.pack_into('<I',header,33,len(header)+len(block))
    return bytes(header)+bytes(block)+data[vertex_start:],proof


def validate_pixel_shaders(shaders):
    """Ask a stock D3D11 software device to compile each candidate pixel shader."""
    lib=ctypes.WinDLL('d3d11.dll');create=lib.D3D11CreateDevice
    create.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,
                     ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
    create.restype=ctypes.c_long;device=ctypes.c_void_p();context=ctypes.c_void_p()
    hr=create(None,5,None,0,None,0,7,ctypes.byref(device),None,ctypes.byref(context))
    if hr:raise ValueError('D3D11 software device failed: '+hex(hr&0xffffffff))
    def release(obj):
        v=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(v[2])(obj)
    try:
        v=ctypes.cast(device,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        fn=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(v[15])
        for dx in shaders:
            output=ctypes.c_void_p();hr=fn(device,dx,len(dx),None,ctypes.byref(output))
            if hr:raise ValueError('D3D11 rejected pixel shader: '+hex(hr&0xffffffff))
            release(output)
    finally:release(context);release(device)
