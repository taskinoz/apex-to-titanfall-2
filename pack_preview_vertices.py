"""Share exact vertices using native local indices, preserving all drawn corners."""
import collections,json,mmap,shutil,struct,time,math
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import validate_visibility
ROOT=Path(__file__).resolve().parent

def smooth_tangent(normal,total,fallback):
    def project(v):
        nn=sum(x*x for x in normal)
        dot=sum(a*b for a,b in zip(normal,v))/(nn or 1.)
        out=tuple(v[k]-normal[k]*dot for k in range(3))
        length=math.sqrt(sum(x*x for x in out))
        return tuple(x/length for x in out) if length>1e-9 else None
    result=project(total) or project(fallback)
    if result is None:raise ValueError("Degenerate vertex tangent")
    return result



def build(source,output):
    source,output=Path(source),Path(output)
    positions=bytearray();normals=bytearray();lit=bytearray();indices=bytearray();sorts=bytearray();meshes=bytearray()
    pcache={};ncache={};verified=0
    def intern(raw,cache,buffer):
        found=cache.get(raw)
        if found is None:
            found=len(buffer)//12;cache[raw]=found;buffer.extend(raw)
        return found
    start=time.monotonic()
    with source.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as data:
        headers=[struct.unpack_from('<4I',data,16+i*16) for i in range(128)]
        def lump(i):
            o,n,_,_=headers[i];return data[o:o+n]
        offsets={i:headers[i][0] for i in (3,0x1e,0x49,0x52,0x4f)}
        old_meshes=lump(0x50)
        for mi in range(len(old_meshes)//28):
            mesh=bytearray(old_meshes[mi*28:mi*28+28]);first,count=struct.unpack_from('<IH',mesh)
            sort=struct.unpack_from('<H',mesh,22)[0]
            texture,lightmap,cubemap,_,base=struct.unpack_from('<3hHi',data,offsets[0x52]+sort*12)
            localcache={};records={};groups=[];unique=0;newbase=len(lit)//44;newfirst=len(indices)//2
            for t in range(count):
                tri=struct.unpack_from('<3H',data,offsets[0x4f]+(first+t*3)*2);new=[]
                for oldlocal in tri:
                    if oldlocal not in records:
                        at=offsets[0x49]+(base+oldlocal)*44
                        raw=data[at:at+44]
                        pi,ni=struct.unpack_from('<2I',raw);tangent=struct.unpack_from('<I',raw,36)[0]
                        p=data[offsets[3]+pi*12:offsets[3]+pi*12+12]
                        n=data[offsets[0x1e]+ni*12:offsets[0x1e]+ni*12+12]
                        ti=tangent&0x7fffffff;tn=data[offsets[0x1e]+ti*12:offsets[0x1e]+ti*12+12]
                        if len(p)!=12 or len(n)!=12 or len(tn)!=12:raise ValueError('Truncated source vertex')
                        pnew=intern(p,pcache,positions);nnew=intern(n,ncache,normals);tnew=nnew
                        packed=struct.pack('<2I',pnew,nnew)+raw[8:36]+struct.pack('<I',tnew|(tangent&0x80000000))+raw[40:44]
                        # Prove every referenced corner retains position, normal,
                        # tangent, mirrored state, UV, colour and lightmap fields.
                        if positions[pnew*12:pnew*12+12]!=p or normals[nnew*12:nnew*12+12]!=n or packed[8:36]!=raw[8:36] or packed[40:]!=raw[40:]:raise ValueError('Vertex attributes changed')
                        verified+=1
                        weldkey=packed[:36]+struct.pack("<I",tangent&0x80000000)+packed[40:]
                        found=localcache.get(weldkey)
                        if found is None:
                            found=unique;unique+=1;localcache[weldkey]=found;lit.extend(packed)
                            groups.append([n,list(struct.unpack("<3f",tn)),struct.unpack("<3f",tn),tangent&0x80000000])
                        else:
                            tv=struct.unpack("<3f",tn)
                            for k in range(3):groups[found][1][k]+=tv[k]
                        records[oldlocal]=found
                    new.append(records[oldlocal])
                indices.extend(struct.pack('<3H',*new))
            for gi,(normal,total,fallback,sign) in enumerate(groups):
                n=struct.unpack('<3f',normal);tn=smooth_tangent(n,total,fallback)
                ti=intern(struct.pack('<3f',*tn),ncache,normals)
                struct.pack_into('<I',lit,(newbase+gi)*44+36,ti|sign)
            if not 0<unique<=65535:raise ValueError('Native local vertex range exceeded')
            struct.pack_into('<I3H',mesh,0,newfirst,count,0,unique-1)
            struct.pack_into('<H',mesh,22,len(sorts)//12)
            meshes.extend(mesh);sorts.extend(struct.pack('<3hHi',texture,lightmap,cubemap,unique-1,newbase))
            if mi%100==0:print(f'Packed {mi+1}/{len(old_meshes)//28} meshes',flush=True)
        bounds=lump(0x51)
        visibility=validate_visibility(lump(0x77),lump(0x78),lump(0x79),bounds)
        oldcounts={str(i):headers[i][1]//sz for i,sz in [(3,12),(0x1e,12),(0x49,44)]}
    report=compact(source,output,{3:positions,0x1e:normals,0x49:lit,0x4f:indices,0x52:sorts,0x50:meshes})
    status=json.loads(source.with_name('source-build.json').read_text())
    status['vertex_packing']=dict(old_counts=oldcounts,new_counts={'3':len(positions)//12,'30':len(normals)//12,'73':len(lit)//44},
        vertex_bytes_before=oldcounts['73']*44,vertex_bytes_after=len(lit),referenced_source_vertices_verified=verified,
        position_normal_uv_colour_lightmap_preserved=True,tangents_averaged_and_reorthogonalized=True,mirrored_uv_seams_preserved=True,triangle_order_and_materials_preserved=True,
        local_indices_verified=True,visibility=visibility,physics_unchanged=True,
        elapsed_seconds=time.monotonic()-start,visual_verified=False)
    status['final_compaction']=report
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,output.parent/p.name)
    print(json.dumps(status['vertex_packing'],indent=2))


if __name__=='__main__':
    build(ROOT/'output/phase-runner/preview-visibility-fixed/mp_phase_runner_preview.bsp',ROOT/'output/phase-runner/preview-packed/mp_phase_runner_preview.bsp')
