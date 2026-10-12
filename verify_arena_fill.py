"""Independently check additive scenery against the last playable map payloads."""
import collections
import json
import struct
from pathlib import Path

from build_arena_fill import CONFIG, ROOT, OUT, MAXIMUM, protected_spawns
from package_player_mods import digest, runtime_files
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY
from build_center_detail import active
from restore_banner_display_textures import image_dds


def records(data, size):
    assert len(data)%size==0
    return collections.Counter(data[i:i+size] for i in range(0,len(data),size))


def verify(ident):
    config=CONFIG[ident];work=OUT/ident
    baseline=work/'baseline';candidate=OUT/'candidates'/config['package']
    before=baseline/'mod/maps'/(config['map']+'.bsp');after=candidate/'mod/maps'/before.name
    old=read_lumps(before,tuple(range(128)));new=read_lumps(after,tuple(range(128)))
    report=json.loads((work/'result.json').read_text());plan=json.loads((work/'plan.json').read_text())
    checks=[]
    def check(condition,label):
        if not condition:raise ValueError(label)
        checks.append(label)
    check(digest(before)==report['baseline_bsp_sha256'],'Baseline package signature')
    check(digest(after)==report['bsp_sha256'],'Candidate package signature')
    modified={2,3,5,0xe,0x1e,0x23,0x2b,0x2c,0x42,0x44,0x45,0x49,0x4f,0x50,0x51,0x52,
              0x53,0x55,0x56,0x57,0x58,0x59,0x5a,0x60,0x61,0x62,0x69,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f}
    for key in set(range(128))-modified:
        check(old[key]==new[key],f'Untouched lump {key:02x}')
    def relative_game_lump(path, payload):
        with path.open('rb') as stream: header=stream.read(2064)
        base=struct.unpack_from('<I',header,16+0x23*16)[0];data=bytearray(payload)
        for i in range(struct.unpack_from('<I',data)[0]):
            at=4+i*16;offset,length=struct.unpack_from('<2I',data,at+8)
            if length:struct.pack_into('<I',data,at+8,offset-base)
        return data
    check(relative_game_lump(before,old[0x23])==relative_game_lump(after,new[0x23]),'Game-lump contents preserved after absolute-pointer relocation')
    for key in (2,3,0x1e,0x2b,0x2c,0x42,0x44,0x45,0x49,0x4f,0x52,0x53,0x60,0x62,0x69,0x7c,0x7e,0x7f):
        check(new[key][:len(old[key])]==old[key],f'Original attribute/collision/light/shadow prefix {key:02x}')
    oldpairs=collections.Counter(old[0x50][i:i+28]+old[0x51][i//28*32:i//28*32+32] for i in range(0,len(old[0x50]),28))
    newpairs=collections.Counter(new[0x50][i:i+28]+new[0x51][i//28*32:i//28*32+32] for i in range(0,len(new[0x50]),28))
    check(not (oldpairs-newpairs),'Every old mesh, attribute reference and geometric bound retained')
    oldactive,newactive=active(old),active(new)
    first=len(old[0x45])//44;last=len(new[0x45])//44
    check(newactive==oldactive|{(0x40,i) for i in range(first,last)},'Old collision exclusions retained exactly')
    check(new[0]==old[0],'No additional gameplay entities or altered spawn/objective definitions')
    check(new[0x65]==old[0x65] and new[0x66]==old[0x66] and new[0x67]==old[0x67] and new[0x68]==old[0x68], 'Character lighting and probe tree retained')
    validate_index_padding(new[0x50],new[0x4f],new[0x52]);checks.append('Native padded index bounds')
    visibility=validate_visibility(new[0x77],new[0x78],new[0x79],new[0x51]);checks.append('Complete native visibility-reference coverage')
    budget=audit(after);fraction=budget['native_padded_indices']/WORLD_INDEX_CAPACITY
    check(.97<=fraction<=MAXIMUM,'97% target with at least 2.5% native index reserve')
    check(budget['static_batch_runs']<512,'Static batch reserve for dynamic-light splitting')
    check(budget['all_meshes_fit_simultaneously'] and budget['static_batches_fit_simultaneously'],'Entire map fits simultaneous world submission')
    check(all(r[3]<60000 for r in struct.iter_unpack('<3hHI',new[0x52])),'Conservative local vertex indexing')
    check(last<65000,'Collision primitive index reserve')
    selected={p['index'] for p in plan['placements']}
    check(len(selected)==len(plan['placements']),'No duplicate recovered source placements')
    check(all(p['origin'][:2]==p['source_origin'][:2] for p in plan['placements']),'Original horizontal source coordinates')
    check(all(abs(p['origin_adjustment'][2])<=51 for p in plan['placements']),'Ground-contact adjustment bounded and documented')
    check(all(not p['collision_triangles'] for p in plan['placements'] if p['foliage'] and p['source_solid']==0),'Decorative foliage cannot block players or AI')
    import numpy as np
    payload=np.load(work/'addition.npz');physical=payload['collision'];payload.close();cursor=0
    protected=protected_spawns(old);overlaps=[]
    for p in plan['placements']:
        count=p['collision_triangles'];faces=physical[cursor:cursor+count];cursor+=count
        if not count:continue
        lo,hi=faces.min((0,1)),faces.max((0,1))
        if any(np.all(hi>=a) and np.all(lo<=b) for a,b in protected):overlaps.append(p['index'])
    check(not overlaps,'Full new colliders clear existing spawn and objective hulls: '+str(overlaps))
    basefiles={p.relative_to(baseline).as_posix():digest(p) for p in runtime_files(baseline)}
    candidatefiles={p.relative_to(candidate).as_posix():digest(p) for p in runtime_files(candidate)}
    mutable={'mod.json','paks/rpak.json','mod/maps/'+config['map']+'.bsp','mod/maps/'+config['map']+'.stbsp'}
    check(all(candidatefiles.get(name)==sha for name,sha in basefiles.items() if name not in mutable),'Existing scripts, loading art, minimaps and material packs retained')
    newfiles=set(candidatefiles)-set(basefiles)
    check(newfiles=={'paks/'+ident.replace('-','_')+'_fill.rpak'},'Only one new resident scenery package')
    for path in (work/'materials/assets/texture').rglob('*_albedo.dds'):
        raw=path.read_bytes();check(raw[84:88]==b'DX10' and struct.unpack_from('<I',raw,128)[0]==78,'sRGB authored albedo: '+path.name)
    result=dict(map=config['map'],version=report['target_version'],checks=len(checks),passed=checks,
        added_placements=plan['added_placements'],renderer=budget,visibility=visibility,
        entity_lump_byte_identical=True,world_fraction=fraction,remaining_native_indices=WORLD_INDEX_CAPACITY-budget['native_padded_indices'],
        native_runtime_verified=False,ai_navigation_added=False)
    (work/'binary-validation.json').write_text(json.dumps(result,indent=2))
    print(ident,len(checks),'checks passed; world occupancy',round(fraction*100,3),'%; remaining indices',result['remaining_native_indices'])
    return result


if __name__=='__main__':
    import sys
    for ident in sys.argv[1:] or CONFIG:verify(ident)
