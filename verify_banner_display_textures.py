"""Verify scoped texture/UV changes against the preserved stable packages."""
import hashlib,json,struct
from restore_banner_display_textures import ROOT,CONFIG,DT,np,image_dds
from repair_preview_index_padding import read_lumps,validate_index_padding
from optimize_preview_textures import dds
from audit_world_draw_budget import audit
from extract_native_material import NativePak
from build_phase_runner_presentation import guid
from optimize_preview_textures import FORMATS

def verify(map_id):
    package,mapname,_,_=CONFIG[map_id];mod=ROOT/'northstar'/package;work=ROOT/'output/banner-display-repair'/map_id
    backup=ROOT/'output/banner-display-repair/backups'/package
    relative='mod/maps/'+mapname+'.bsp';old=read_lumps(backup/relative,range(128));new=read_lumps(mod/relative,range(128))
    receipt=json.loads((work/'receipt.json').read_text());allowed={2,35,43,44,82}|({73} if map_id=='drop-off' else set())
    atlas=json.loads((work/'display-atlas.json').read_text())
    allowed.add(73)
    changed=[i for i in range(128) if old[i]!=new[i]];assert set(changed)<=allowed
    before=np.frombuffer(old[73],DT);after=np.frombuffer(new[73],DT)
    assert len(before)==len(after)
    for field in DT.names:
        if field!='uv':assert np.array_equal(before[field],after[field]),field
    staged=read_lumps(work/'before-display-atlas.bsp',range(128));expected=np.frombuffer(staged[73],DT)['uv'].copy();ids=atlas['all_console_vertices'];expected[ids,0]=(expected[ids,0]+1)/4
    for key,value in atlas['front_vertices'].items():expected[int(key)]=value
    assert np.array_equal(expected,after['uv'])
    uv=np.any(before['uv']!=after['uv'],axis=1)
    assert int(uv.sum())==receipt['banner_vertices']+len(ids)
    assert np.isfinite(after['uv'][uv]).all()
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
    for channels in atlas['auxiliary'].values():
        source=(work/'assets'/channels['original']).read_bytes();expanded=(work/'assets'/channels['expanded']).read_bytes();s=dds(source);e=dds(expanded)
        assert (e['width'],e['height'],e['format'])==(s['width']*4,s['height'],s['format'])
        assert e['mips']==int(np.log2(max(e['width'],e['height'])))+1
        top=np.frombuffer(source[s['offset']:s['offset']+s['top_bytes']],'u1').reshape(s['height']//4,s['width']//4,FORMATS[s['format']][1])
        assert np.tile(top,(1,4,1)).tobytes()==expanded[e['offset']:e['offset']+e['top_bytes']]
    pak=NativePak(mod/'paks'/(map_id.replace('-','_')+'_banner_displays.rpak'));material_pack=NativePak(mod/'paks'/('composite_world.rpak' if map_id=='drop-off' else 'phase_runner_world.rpak'));known={a['guid'] for a in pak.assets}|{a['guid'] for a in material_pack.assets}
    for name in ('common','coliseum'):known.update(a['guid'] for a in NativePak(ROOT/'inputs/tf2-rpak-work'/(name+'.raw.rpak')).assets)
    for asset in pak.assets:
        if asset['type']=='matl':
            spec,buffer=pak.material(asset)
            for ref in [spec['shaderSet'],*spec['$textures'].values(),*[spec[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]:assert not int(ref,16) or int(ref,16) in known,ref
    padding=validate_index_padding(new[80],new[79],new[82]);budget=audit(mod/relative);previous=audit(backup/relative)
    for field in ('native_padded_indices','meshes'):assert budget[field]==previous[field]
    assert budget['static_batch_runs']<=previous['static_batch_runs']
    result=dict(map=map_id,changed_lumps=changed,banner_vertices=receipt['banner_vertices'],console_uv_vertices=len(ids),frozen_front_faces=len(atlas['front_faces']),geometry_collision_visibility_lighting_preserved=True,full_srgb_mip_chains=True,streaming_columns_preserved=True,index_padding=padding,draw_budget=budget,resident_bytes=atlas['resident_bytes'],rpak_sha256=hashlib.sha256((mod/'paks'/(map_id.replace('-','_')+'_banner_displays.rpak')).read_bytes()).hexdigest())
    (work/'validation.json').write_text(json.dumps(result,indent=2));print(map_id,'verified:',int(uv.sum()),'UV vertices;',budget['native_padded_indices'],'indices;',budget['static_batch_runs'],'batches')

if __name__=='__main__':
    for map_id in CONFIG:verify(map_id)
