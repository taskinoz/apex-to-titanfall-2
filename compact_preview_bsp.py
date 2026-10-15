"""Compact active BSP lumps and relocate absolute game-lump directory offsets."""
import hashlib,json,shutil,struct
from pathlib import Path
from package_northstar import validate_bsp
ROOT=Path(__file__).resolve().parent

def relocate_game_lump(payload,old,offset):
    """Rebase absolute game-lump directory offsets from `old` to `offset`."""
    payload=bytearray(payload);n=len(payload);count=struct.unpack_from('<I',payload)[0]
    if 4+16*count>n:raise ValueError('Truncated game-lump directory')
    for j in range(count):
        at=4+j*16;ptr,length=struct.unpack_from('<2I',payload,at+8)
        if length:
            if not old<=ptr or ptr+length>old+n:raise ValueError('External game-lump payload cannot be relocated')
            struct.pack_into('<I',payload,at+8,ptr+offset-old)
    return bytes(payload)

def compact(source,output,replacements=None):
    source,output=Path(source),Path(output)
    replacements=dict(replacements or {})
    output.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as inp,output.open('wb') as out:
        header=bytearray(inp.read(2064));out.write(header)
        for i in range(128):
            old,n,v,pad=struct.unpack_from('<4I',header,16+i*16)
            if i in replacements:
                payload=replacements[i]
                out.write(bytes((-out.tell())%16));offset=out.tell()
                # Callers pass every lump read from the source; an unmodified
                # game lump still holds absolute offsets into the old file.
                if i==0x23 and payload:
                    inp.seek(old)
                    if n!=len(payload) or inp.read(n)!=bytes(payload):raise ValueError('Edited game-lump directories are unsupported')
                    payload=replacements[i]=relocate_game_lump(payload,old,offset)
                out.write(payload)
                struct.pack_into('<4I',header,16+i*16,offset,len(payload),v,pad)
                continue
            if not n:continue
            out.write(bytes((-out.tell())%16));offset=out.tell();inp.seek(old)
            if i==0x23:
                out.write(relocate_game_lump(inp.read(n),old,offset))
            else:
                remaining=n
                while remaining:
                    chunk=inp.read(min(8*1024*1024,remaining))
                    if not chunk:raise ValueError('Truncated BSP')
                    out.write(chunk);remaining-=len(chunk)
            struct.pack_into('<4I',header,16+i*16,offset,n,v,pad)
        out.seek(0);out.write(header)
    checks=validate_bsp(output)
    with source.open('rb') as a,output.open('rb') as b:
        ha=a.read(2064);hb=b.read(2064)
        for i in range(128):
            oa,n,_,_=struct.unpack_from('<4I',ha,16+i*16);ob,nn,_,_=struct.unpack_from('<4I',hb,16+i*16)
            if i in replacements:
                b.seek(ob)
                if nn!=len(replacements[i]) or b.read(nn)!=replacements[i]:raise ValueError('Replacement lump changed')
                continue
            if n!=nn:raise ValueError('Lump length changed')
            if i==0x23 or not n:continue
            a.seek(oa);b.seek(ob);remaining=n
            while remaining:
                take=min(8*1024*1024,remaining)
                if a.read(take)!=b.read(take):raise ValueError(f'Lump {i} changed')
                remaining-=take
    report=dict(original_bytes=source.stat().st_size,compact_bytes=output.stat().st_size,non_game_lumps_byte_identical=not replacements,unchanged_lumps_byte_verified=True,replaced_lumps=sorted(replacements),game_lump_offsets_relocated=True,checks=checks)
    return report

def build():
    source=ROOT/'output/phase-runner/preview-faces/mp_phase_runner_preview.bsp'
    output=ROOT/'output/phase-runner/preview-compact/mp_phase_runner_preview.bsp'
    report=compact(source,output)
    status=json.loads(source.with_name('source-build.json').read_text());status['compaction']=report
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,output.parent/p.name)
    print(json.dumps(report,indent=2))
if __name__=='__main__':build()
