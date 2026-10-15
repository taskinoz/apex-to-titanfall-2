"""Decode static Season 3 VG geometry, using Legion's documented packed layout."""
import math
import struct
from pathlib import Path
from recover_model_slots import mesh_slots
from stage_prop_geometry import material_basename


def compiled_materials(data):
    slots,skin_indices=mesh_slots(data)
    count,offset=struct.unpack_from('<2i',data,208)
    names=[]
    for i in range(count):
        record=offset+i*12
        if record<0 or record+12>len(data):raise ValueError('Truncated compiled material table')
        at=record+struct.unpack_from('<i',data,record)[0]
        if not 0<=at<len(data):raise ValueError('Invalid compiled material name')
        names.append(material_basename(data[at:data.index(0,at)].decode()))
    return slots,[[names[index] for index in row] for row in skin_indices]


def packed_normal(value,legacy=False):
    axis=(value>>29)&3
    if axis==3:raise ValueError('Invalid packed normal axis')
    a=-255. if (value>>28)&1 else 255.
    b=float((value>>19)&511)-256.;c=float((value>>10)&511)-256.
    length=math.sqrt(a*a+b*b+c*c)
    normal=[0.,0.,0.]
    # Verified against the source static vertex shader (rib_giant_large_01 VS):
    # its movc swizzles yield axis 0 -> (a,b,c), 1 -> (c,a,b), 2 -> (b,c,a).
    # A swapped (a,c,b)/(b,a,c)/(c,b,a) reading was rejected: across 80 sampled
    # models it lowered median |normal . face normal| from 0.999 to 0.868.
    # `legacy` is retained only for call compatibility; both use this order.
    order=((a,b,c),(c,a,b),(b,c,a))
    normal[:]=[x/length for x in order[axis]]
    return tuple(normal)


def decode(rmdl,vg,lod_index=0,with_colors=False,legacy_normals=False):
    rmdl,vg=bytes(rmdl),bytes(vg)
    slots,skins=compiled_materials(rmdl)
    if len(vg)<160 or struct.unpack_from('<2I',vg)!=(0x47567430,1):raise ValueError('Unsupported VG version')
    h=struct.unpack_from('<18Q',vg,16)
    def extent(offset,length):
        if offset<160 or offset+length>len(vg):raise ValueError('VG buffer exceeds file bounds')
    mesh_offset,mesh_count=h[2:4];index_offset,index_count=h[4:6]
    vertex_offset,vertex_bytes=h[6:8];lod_offset,lod_count=h[12:14];strip_offset,strip_count=h[16:18]
    extent(mesh_offset,mesh_count*72);extent(index_offset,index_count*2)
    extent(vertex_offset,vertex_bytes);extent(lod_offset,lod_count*8);extent(strip_offset,strip_count*35)
    if not lod_count:raise ValueError('VG has no LOD')
    if not 0 <= lod_index < lod_count:raise ValueError('Invalid VG LOD selection')
    first,count,_=struct.unpack_from('<2hf',vg,lod_offset+lod_index*8)
    if first<0 or count!=len(slots) or first+count>mesh_count:raise ValueError('VG and compiled submeshes disagree')
    sections=[]
    for i in range(first,first+count):
        m=struct.unpack_from('<18I',vg,mesh_offset+i*72)
        flags,flags2,start,stride,vertices=m[:5];idx,indices=m[8:10];strip,nstrips=m[12:14]
        # Author-made lower LODs may omit a decorative material section.
        if indices==0 and nstrips==0:
            sections.append([]);continue
        if flags&0x5000==0x5000:raise ValueError('Skinned geometry requires bone transforms')
        # This vista has valid direct triangle-list buffers and no strip
        # table. Legion's exporter skips these sections; validate the full
        # index stream independently instead of discarding their geometry.
        if strip+nstrips>strip_count or (not nstrips and indices%3):raise ValueError('Invalid static triangle strips')
        if start+stride*vertices>vertex_bytes or idx+indices>index_count:raise ValueError('Submesh exceeds VG buffers')
        verts=[]
        for j in range(vertices):
            at=vertex_offset+start+j*stride;shift=0
            if flags&1:p=struct.unpack_from('<3f',vg,at);shift=12
            elif flags&2:
                a,b=struct.unpack_from('<2I',vg,at);shift=8
                p=((a&0x1fffff)/1024.-1024.,(((b&1023)<<11)+(a>>21))/1024.-1024.,(b>>10)/1024.-2048.)
            else:raise ValueError('Unsupported position encoding')
            n=packed_normal(struct.unpack_from('<I',vg,at+shift)[0],legacy_normals);shift+=4
            color=struct.unpack_from('<4B',vg,at+shift) if flags&0x10 else (255,255,255,255)
            if flags&0x10:shift+=4
            uv=struct.unpack_from('<2f',vg,at+shift);shift+=8
            if flags2&2:shift+=8
            if shift>stride or not all(math.isfinite(x) for x in p+n+uv):raise ValueError('Invalid static vertex')
            verts.append(p+n+(uv[0],1-uv[1])+(color if with_colors else ()))  # Match Legion SMD UV convention.
        faces=[];used=0
        if not nstrips:
            for off in range(0,indices,3):
                face=struct.unpack_from('<3H',vg,index_offset+(idx+off)*2)
                if any(v>=vertices for v in face):raise ValueError('VG triangle references missing vertex')
                faces.append([verts[v] for v in reversed(face)])
            used=indices
        for j in range(nstrips):
            at=strip_offset+(strip+j)*35
            nindices,relative,nverts,voffset=struct.unpack_from('<4i',vg,at)
            stripflags=vg[at+18]
            if not stripflags&1 or nindices%3 or relative<0 or relative+nindices>indices:
                raise ValueError('Unsupported or truncated triangle strip')
            for off in range(0,nindices,3):
                tri=struct.unpack_from('<3H',vg,index_offset+(idx+relative+off)*2)
                if any(v>=vertices for v in tri):raise ValueError('VG triangle references missing vertex')
                faces.append([verts[v] for v in reversed(tri)])  # Legion export winding.
            used+=nindices
        if used!=indices:raise ValueError('Uncovered VG triangle indices')
        sections.append(faces)
    return sections,slots,skins


def load(folder,lod_index=0,with_colors=False,legacy_normals=False):
    folder=Path(folder);name=folder.name
    return decode((folder/(name+'.rmdl')).read_bytes(),(folder/(name+'.vg')).read_bytes(),lod_index,with_colors,legacy_normals)
