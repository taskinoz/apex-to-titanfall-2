"""Inspect placement, fallback materials and lighting without changing the map."""
import collections,json,struct
from pathlib import Path
from repair_preview_index_padding import read_lumps
from read_prop_physics import read_phy
from read_vg_static import load

ROOT=Path(__file__).resolve().parent
P=ROOT/'output/phase-runner'

def audit():
    src=P/'preview-index-repaired/mp_phase_runner_preview.bsp'
    ids=(0,1,2,3,5,0xe,0x2b,0x2c,0x36,0x37,0x49,0x50,0x51,0x52,0x53,0x62,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6a,0x6b,0x7a,0x7b,0x7c,0x7d,0x7e,0x7f)
    l=read_lumps(src,ids)
    native=read_lumps(ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp',ids)
    names=[l[0x2b][off:l[0x2b].index(0,off)].decode() for off, in struct.iter_unpack('<I',l[0x2c])]
    textures=[names[r[3]] for r in struct.iter_unpack('<3f6I',l[2])]
    report={'lumps':{hex(i):{'bytes':len(l[i]),'identical_to_coliseum':bool(l[i]) and l[i]==native[i]} for i in ids},'world_bounds':struct.unpack_from('<6f',l[0xe]),'cell_bsp_hex':l[0x6a].hex(),'entities':l[0].decode(errors='replace'),'fallback_meshes':[],'physics_models':[]}
    for mi in range(len(l[0x50])//28):
        first,count=struct.unpack_from('<IH',l[0x50],mi*28);si=struct.unpack_from('<H',l[0x50],mi*28+22)[0];tex=struct.unpack_from('<h',l[0x52],si*12)[0]
        if 'dev_gray' in textures[tex]:
            report['fallback_meshes'].append({'mesh':mi,'triangles':count,'material':textures[tex],'bounds':struct.unpack_from('<8f',l[0x51],mi*32)})
    placements=json.loads((P/'static-props.json').read_text());restored=set()
    for file in P.glob('*-geometry/report.json'):
        restored.update(r['index'] for r in json.loads(file.read_text()).get('restored',[]))
    models=collections.Counter(Path(p['model']).stem for p in placements if p['index'] in restored)
    for name,num in models.items():
        folder=ROOT/'tools/legion/exported_files/models'/name
        if not (folder/(name+'.phy')).is_file() or not (folder/(name+'.vg')).is_file():continue
        pieces=read_phy(folder/(name+'.phy'));pv=[v for piece in pieces for face in piece for v in face]
        sections,slots,skins=load(folder);rv=[v[:3] for sec in sections for face in sec for v in face]
        bounds=lambda vs:[[min(v[k] for v in vs) for k in range(3)],[max(v[k] for v in vs) for k in range(3)]]
        pb,rb=bounds(pv),bounds(rv)
        entry={'model':name,'placements':num,'physics_bounds':pb,'render_bounds':rb,'max_bounds_difference':max(abs(pb[i][k]-rb[i][k]) for i in range(2) for k in range(3)),'materials':skins[0]}
        report['physics_models'].append(entry)
    report['physics_models'].sort(key=lambda p:p['max_bounds_difference'],reverse=True)
    (P/'alignment-audit-0.1.22.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('entities','physics_models','fallback_meshes')},indent=2))
    print('Fallback:',report['fallback_meshes'][:12]);print('Physics:',report['physics_models'][:12])

if __name__=='__main__':audit()
