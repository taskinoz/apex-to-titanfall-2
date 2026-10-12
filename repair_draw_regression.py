"""Undo 0.1.18 draw experiments while retaining the recovered map content."""
import hashlib,json,mmap,shutil,struct
from pathlib import Path
from compact_preview_bsp import compact
from extract_native_material import NativePak
from preview_visibility import validate_visibility
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT/'output/phase-runner'
PORTAL_MATERIALS={
    'ts_brushed_metal03_destroyed_bm_02',
    'metal_worn_tileable_01_to_icelandic_moss_01_bm',
    'white_floor_tile_mendoko_01_to_icelandic_moss_01_bm',
    'beacon_wires_01','stasis_trim_02','trim_metal_01',
    'beacon_metal_panel_grey_02_vc','desertlands_snow_04_wld_b2t',
}

def restore_material_draw_state(path):
    path=Path(path);pak=NativePak(path)
    changes=[]
    for asset in pak.assets:
        if asset['type']!='matl':continue
        spec,_=pak.material(asset)
        name=spec['name'].rsplit('/',1)[-1]
        basename=name[:-8] if name.endswith('_colpass') else name
        if basename not in PORTAL_MATERIALS:continue
        offset=pak.address(asset['header'])+102
        flags=struct.unpack_from('<H',pak.data,offset)[0]
        if flags not in (2,6):raise ValueError('Unexpected portal material draw state')
        if flags==2:changes.append(dict(name=spec['name'],offset=offset,before=2,after=6))
    if len(changes)!=16:raise ValueError('Expected both native passes for eight portal materials')
    old_hash=hashlib.sha256(pak.data).hexdigest()
    # All asset pointers, textures, shaders and material bindings stay intact.
    # The archive from 0.1.18 retains the original asset pack for comparison.
    del pak
    with path.open('r+b') as f,mmap.mmap(f.fileno(),0) as data:
        for c in changes:struct.pack_into('<H',data,c['offset'],c['after'])
        data.flush();new_hash=hashlib.sha256(data).hexdigest()
    return dict(changes=changes,changed_materials=16,changed_bytes=16,
        previous_sha256=old_hash,restored_sha256=new_hash,
        original_native_rasterizer_flags='0x6',all_other_rpak_bytes_unchanged=True)

def build():
    source=PROJECT/'preview-draw-safe/mp_phase_runner_preview.bsp'
    reference=PROJECT/'preview-welded/mp_phase_runner_preview.bsp'
    output=PROJECT/'preview-draw-restored/mp_phase_runner_preview.bsp'
    def read_lumps(path,ids):
        with path.open('rb') as f:
            h=f.read(2064);result={}
            for i in ids:
                o,n,_,_=struct.unpack_from('<4I',h,16+i*16);f.seek(o);result[i]=f.read(n)
            return result
    restored=read_lumps(reference,(0x51,0x77,0x78,0x79))
    validation=validate_visibility(restored[0x77],restored[0x78],restored[0x79],restored[0x51])
    compaction=compact(source,output,restored)
    status=json.loads(source.with_name('source-build.json').read_text())
    status.pop('conservative_draw_bounds',None);status.pop('portal_render_settings',None)
    status['draw_regression_repair']=dict(restored_geometric_mesh_bounds=True,
        restored_spatial_visibility=True,validation=validation,
        vertex_geometry_terrain_rocks_and_physics_unchanged=True,
        prior_user_feedback='Portals and other props disappear in 0.1.18.',
        visual_verified=False,
        limitation='Reverts the two 0.1.18 draw experiments; earlier distance/angle pop-in may remain. Client verification is required.')
    status['draw_regression_repair']['material_repair']=restore_material_draw_state(PROJECT/'world-materials/build/phase_runner_world.rpak')
    status['visibility_rebuild']=validation;status['final_compaction']=compaction
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,output.parent/p.name)
    shutil.copy2(source.with_suffix('.stbsp'),output.with_suffix('.stbsp'))
    print(json.dumps(status['draw_regression_repair'],indent=2))

if __name__=='__main__':build()
