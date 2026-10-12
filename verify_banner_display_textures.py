"""Verify scoped texture/UV changes against the preserved stable packages."""
import hashlib,json,struct
from restore_banner_display_textures import ROOT,CONFIG,DT,np,image_dds
from repair_preview_index_padding import read_lumps,validate_index_padding
from optimize_preview_textures import dds
from audit_world_draw_budget import audit
from extract_native_material import NativePak

def verify(map_id):
    package,mapname,_,_=CONFIG[map_id];mod=ROOT/'northstar'/package;work=ROOT/'output/banner-display-repair'/map_id
    backup=ROOT/'output/banner-display-repair/backups'/package
    relative='mod/maps/'+mapname+'.bsp';old=read_lumps(backup/relative,range(128));new=read_lumps(mod/relative,range(128))
    receipt=json.loads((work/'receipt.json').read_text());allowed={2,35,43,44,82}|({73} if map_id=='drop-off' else set())
    changed=[i for i in range(128) if old[i]!=new[i]];assert set(changed)<=allowed
    before=np.frombuffer(old[73],DT);after=np.frombuffer(new[73],DT)
    assert len(before)==len(after)
    for field in DT.names:
        if field!='uv':assert np.array_equal(before[field],after[field]),field
    uv=np.any(before['uv']!=after['uv'],axis=1)
    assert int(uv.sum())==receipt['banner_vertices']
    if uv.any():assert np.isfinite(after['uv'][uv]).all() and after['uv'][uv].min()>=0 and after['uv'][uv].max()<=1
    # Entire collision, world, render submission and all lighting/PVS buffers
    # are covered by this comparison, apart from documented pointer relocation.
    oldheader=(backup/relative).read_bytes();newheader=(mod/relative).read_bytes();game=bytearray(new[35])
    oo=struct.unpack_from('<I',oldheader,16+35*16)[0];no=struct.unpack_from('<I',newheader,16+35*16)[0]
    for i in range(struct.unpack_from('<I',old[35])[0]):
        at=4+i*16;p,n=struct.unpack_from('<2I',game,at+8)
        if n:struct.pack_into('<I',game,at+8,p-no+oo)
    assert bytes(game)==old[35]
    a=(backup/relative).with_suffix('.stbsp').read_bytes();b=(mod/relative).with_suffix('.stbsp').read_bytes()
    def block(raw,i):
        o,n=struct.unpack_from('<2Q',raw,168+i*16);return raw[o:o+n*(24 if i in (1,4) else 1)]
    for i in (2,3,4,5):assert block(a,i)==block(b,i)
    assert block(b,0).startswith(block(a,0)) and block(b,1).startswith(block(a,1))
    for f in (work/'assets').rglob('*_albedo.dds'):
        info=dds(f.read_bytes());assert info['mips']==int(np.log2(max(info['width'],info['height'])))+1
        assert info['format']==99;assert image_dds(f).getbbox()
    padding=validate_index_padding(new[80],new[79],new[82]);budget=audit(mod/relative);previous=audit(backup/relative)
    for field in ('native_padded_indices','static_batch_runs','meshes'):assert budget[field]==previous[field]
    result=dict(map=map_id,changed_lumps=changed,banner_vertices=int(uv.sum()),unchanged_geometry_collision_visibility_lighting=True,full_srgb_mip_chains=True,streaming_columns_preserved=True,index_padding=padding,draw_budget=budget,rpak_sha256=hashlib.sha256((mod/'paks'/(map_id.replace('-','_')+'_banner_displays.rpak')).read_bytes()).hexdigest())
    (work/'validation.json').write_text(json.dumps(result,indent=2));print(map_id,'verified:',int(uv.sum()),'UV vertices;',budget['native_padded_indices'],'indices;',budget['static_batch_runs'],'batches')

if __name__=='__main__':
    for map_id in CONFIG:verify(map_id)
