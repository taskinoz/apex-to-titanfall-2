"""Read source material constants by DXBC reflection, not a guessed CPU layout.

Supports the unpatched decompressed v8/v15 packs used by these previews.
Other versions must go through an upstream loader rather than reuse offsets.
"""
import struct
from extract_native_material import NativePak


class ApexMaterials(NativePak):
    def __init__(self, path):
        d=self.data=path.read_bytes()
        if d[:4]!=b'RPak' or struct.unpack_from('<H',d,4)[0]!=8 or struct.unpack_from('<H',d,6)[0]&0x8100 or struct.unpack_from('<I',d,80)[0]:
            raise ValueError('Expected decompressed, unpatched v8 source pack')
        a,b,segments,pages=struct.unpack_from('<4H',d,72)
        descriptors,assets,refs,relations=struct.unpack_from('<4I',d,84)
        at=128+a+b+segments*16
        heads=list(struct.iter_unpack('<3I',d[at:at+pages*12]));at+=pages*12+descriptors*8
        self.assets=[]
        for i in range(assets):
            r=d[at+i*80:at+(i+1)*80]
            self.assets.append(dict(guid=struct.unpack_from('<Q',r)[0],header=struct.unpack_from('<2I',r,16),
                cpu=struct.unpack_from('<2I',r,24),size=struct.unpack_from('<I',r,68)[0],
                version=struct.unpack_from('<I',r,72)[0],type=r[76:80].decode()))
        at+=assets*80+refs*8+relations*4;self.pages=[]
        for _,_,n in heads:self.pages.append((at,n));at+=n
        if at!=len(d):raise ValueError('Source pack page extent mismatch')
        self.index={a['guid']:a for a in self.assets}
        self.materials={self.string(struct.unpack_from('<2I',d,self.address(a['header'])+24)).replace('\\','/').rsplit('/',1)[-1]:a
            for a in self.assets if a['type']=='matl' and a['version']==15}

    def constants(self, name):
        if name not in self.materials:
            # Exported folder names are lower case; pack strings keep authored case (e.g. _BM_01).
            name=next(k for k in self.materials if k.lower()==name.lower())
        a=self.materials[name];d=self.data;h=self.address(a['header'])
        s=self.index[struct.unpack_from('<Q',d,h+88)[0]]
        if s['version']!=11:raise ValueError('Unsupported source shader set')
        ps=self.index[struct.unpack_from('<Q',d,self.address(s['header'])+56)[0]]
        if ps['version']!=12:raise ValueError('Unsupported source shader image')
        at=self.address(ps['cpu']);ptr=struct.unpack_from('<2I',d,at);size=struct.unpack_from('<I',d,at+8)[0]
        start=self.address(ptr);dx=d[start:start+size]
        fields=reflect(dx)
        c=self.address(a['cpu']);ptr=struct.unpack_from('<2I',d,c);length=struct.unpack_from('<I',d,c+8)[0]
        start=self.address(ptr);cpu=d[start:start+length]
        if len(cpu)!=length:raise ValueError('Truncated source material constants')
        values={}
        for n,(offset,count) in fields.items():
            if offset+count>len(cpu):raise ValueError('Source constant exceeds CPU buffer')
            if count%4==0:values[n]=list(struct.unpack_from('<'+'f'*(count//4),cpu,offset))
        return values,fields


def reflect(dx):
    if dx[:4]!=b'DXBC' or struct.unpack_from('<I',dx,24)[0]!=len(dx):raise ValueError('Invalid source DXBC')
    fields={}
    for i in range(struct.unpack_from('<I',dx,28)[0]):
        at=struct.unpack_from('<I',dx,32+i*4)[0];length=struct.unpack_from('<I',dx,at+4)[0]
        if at+8+length>len(dx):raise ValueError('DXBC chunk exceeds image')
        if dx[at:at+4]!=b'RDEF':continue
        r=dx[at+8:at+8+length];count,offset=struct.unpack_from('<2I',r)
        string=lambda o:r[o:r.index(0,o)].decode()
        for j in range(count):
            no,n,vo,size=struct.unpack_from('<4I',r,offset+j*24)
            if string(no)!='CBufUberStatic':continue
            for k in range(n):
                no,start,length=struct.unpack_from('<3I',r,vo+k*40)
                fields[string(no)]=(start,length)
    if not fields:raise ValueError('Missing source static constant reflection')
    return fields
