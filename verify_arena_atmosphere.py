"""Check source constants, colour space and native material contracts independently."""
import hashlib,json,struct,sys
from new_arena_ports import folder,CONFIG
from extract_native_material import NativePak
from repair_environment_lighting import entities


def require_bindings(spec,kind):
    needed={'0','4'} if 'unlit' in kind else {'0','1','2','3'}
    if 'HDR emission' in kind:needed|={'4','11'}
    if 'opaque water' in kind:needed|={'15','18','19'}
    if not needed<=spec['$textures'].keys():raise ValueError('Incomplete native shader texture contract: '+spec['name'])


def verify(ident):
    out=folder(ident);receipt=json.loads((out/'atmosphere-materials.json').read_text());mapping=json.loads((out/'materials/mapping.json').read_text())['materials']
    pak_path=out/'materials/build'/(ident.replace('-','_')+'_world.rpak');pak=NativePak(pak_path)
    materials={}
    for a in pak.assets:
        if a['type']=='matl':
            s,u=pak.material(a);materials[s['name']]=(s,u)
    for row in receipt['materials']:
        r=mapping[row['material']];s,u=materials[r['name']];require_bindings(s,row['kind'])
        if int(s['glueFlags2'],16)&2:raise ValueError('Unverified vertex palette binding enabled: '+s['name'])
        if 'source_albedo_tint' in row:
            if any(abs(a-b)>1e-6 for a,b in zip(struct.unpack_from('<3f',u,96),row['source_albedo_tint'])):raise ValueError('Source albedo tint mismatch')
        if 'HDR emission' in row['kind']:
            if any(abs(a-b)>1e-6 for a,b in zip(struct.unpack_from('<3f',u,160),row['source_emissive_tint'])):raise ValueError('Source emissive tint mismatch')
        if 'opaque water' not in row['kind']:
            d=(out/'materials/assets'/r['textures']['0']).with_suffix('.dds').read_bytes()
            if d[84:88]!=b'DX10' or struct.unpack_from('<I',d,128)[0] not in (72,75,78,99):raise ValueError('Colour texture must have an explicit sRGB format')
        if 'opaque water' in row['kind']:
            for slot in ('1','15','18','19'):
                d=(out/'materials/assets'/r['textures'][slot]).with_suffix('.dds').read_bytes()
                if d[84:88]!=b'DX10' or struct.unpack_from('<I',d,128)[0]!=83:raise ValueError('Campaign normal/distortion encoding changed')
            if not any(abs(v)>0 for v in struct.unpack_from('<2f',u,16)):raise ValueError('Campaign scrolling transform missing')
    bsp=out/(CONFIG[ident]['target']+'.bsp');fog=[e for e in entities(bsp) if e.get('classname')=='env_fog_controller']
    if fog!=[receipt['fog']['native']]:raise ValueError('Native fog controller differs from receipt')
    result=dict(materials_checked=len(receipt['materials']),shader_texture_contracts=True,source_tints=True,
        explicit_srgb_colour=True,source_fog=True,campaign_bc5_water=ident=='firing-range',
        bsp_sha256=hashlib.sha256(bsp.read_bytes()).hexdigest(),material_pack_sha256=hashlib.sha256(pak_path.read_bytes()).hexdigest())
    (out/'atmosphere-validation.json').write_text(json.dumps(result,indent=2));print(ident,'material/fog contracts passed',flush=True)


if __name__=='__main__':verify(sys.argv[1])
