"""Stage structural prop meshes at their original Apex placements.

This bakes static meshes into the diagnostic BSP rather than compiling new MDLs.
Lost SMD material bindings use the first QC skin material as an explicit preview
approximation. It does not synthesize bounding-box collision for open structures.
"""
import collections
import json
import math
import re
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def rotation(angles):
    p,y,r=map(math.radians,angles)
    cp,sp,cy,sy,cr,sr=math.cos(p),math.sin(p),math.cos(y),math.sin(y),math.cos(r),math.sin(r)
    return ((cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr),
            (sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr),
            (-sp,cp*sr,cp*cr))


def transform(point,matrix,origin=(0.,0.,0.),scale=1.):
    return tuple(sum(matrix[k][j]*point[j] for j in range(3))*scale+origin[k] for k in range(3))


def material_basename(name):
    name=name.replace('\\','/').rsplit('/',1)[-1].lower()
    return re.sub(r'_(rgdp|rgdc|rgdu|rgde|sknp|sknc|sknu|wldp|wldc)$','',name)


def load_mesh(qc_path,missing_only=False):
    qc=Path(qc_path)
    text=qc.read_text()
    references=re.findall(r'\bstudio\s+"([^"]+\.smd)"',text)
    if not references:
        raise ValueError(f'No static mesh in {qc}')
    families=re.findall(r'"[^"\n]+"\s*\{\s*((?:"[^"\n]+"\s*)+)\}',text)
    skins=[[material_basename(m) for m in re.findall(r'"([^"]+)"',row)] for row in families]
    if not skins:
        skins=[['default_material']]
    meshes=[]
    for reference in references:
        # Bodygroup references identify highest detail. Lower LOD replacements
        # are not included again as separate overlapping geometry.
        lines=(qc.parent/reference).read_text().splitlines()
        starts=[i+1 for i,line in enumerate(lines) if line=='triangles']
        if not starts: raise ValueError(f'No triangle sections in {reference}')
        for section,start in enumerate(starts):
            end=lines.index('end',start)
            if (end-start)%4:
                raise ValueError(f'Incomplete SMD triangle records in {reference}')
            if missing_only and section==0: continue
            for off in range(start,end,4):
                material=material_basename(lines[off])
                corners=[tuple(map(float,line.split()[1:9])) for line in lines[off+1:off+4]]
                meshes.append((material,corners))
    return meshes,skins


def stage(phase_structures=False,support_structures=False,area_details=False,missing_sections=False,broad_restore=False):
    placements=json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
    excluded={'foliage','rocks','desertlands','levels_terrain','decals'}
    candidates=[p for p in placements if p['in_arena'] and p['source_qc']
                and p['solid_mode'] in (6,7,2) and p['model'].split('/')[1].lower() not in excluded]
    if phase_structures:
        candidates=[p for p in placements if p['in_arena'] and p['source_qc']
                    and '/levels_terrain/mp_rr_phase_runner/' in p['model']
                    and p['solid_mode'] in (6,7,2) and 'godrays' not in p['model']]
    if support_structures:
        candidates=[p for p in placements if p['in_arena'] and p['source_qc'] and
                    (('/desertlands/' in p['model'] and any(w in p['model'] for w in ('construction_bldg','industrial_crane')))
                     or '/mp_rr_canyonlands/rig_frame' in p['model'])]
    if area_details:
        restored=set()
        for previous in ('prop-geometry','phase-structure-geometry','support-geometry'):
            restored.update(p['index'] for p in json.loads((ROOT/'output/phase-runner'/previous/'report.json').read_text())['restored'])
        anchor=(-2213.,3026.,-1091.)
        candidates=[p for p in placements if p['in_arena'] and p['source_qc'] and p['index'] not in restored
                    and p['model'].split('/')[1].lower() not in {'foliage','decals'}
                    and p['model'] != 'mdl/containers/barrel.rmdl'  # Required blue-barrel albedo is unavailable.
                    and sum((p['origin'][k]-anchor[k])**2 for k in range(2)) < 4000.**2]
    else:
        anchor=(-761.369792,-4444.361979,-1024.)
    if missing_sections:
        restored=set()
        for previous in ('prop-geometry','phase-structure-geometry','support-geometry','area-detail-geometry'):
            restored.update(p['index'] for p in json.loads((ROOT/'output/phase-runner'/previous/'report.json').read_text())['restored'])
        candidates=[p for p in placements if p['index'] in restored and p['source_qc'] and '/robots/marvin/' not in p['model']]
    unavailable=[]
    if broad_restore:
        done=set()
        for previous in ('prop-geometry','phase-structure-geometry','support-geometry','area-detail-geometry'):
            done.update(p['index'] for p in json.loads((ROOT/'output/phase-runner'/previous/'report.json').read_text())['restored'])
        candidates=[p for p in placements if p['in_arena'] and p['source_qc'] and p['index'] not in done
                    and p['model'].split('/')[1].lower() not in {'foliage','decals'} and 'godrays' not in p['model'] and '/robots/marvin/' not in p['model']]
        source_dirs=[ROOT/'tools/legion/exported_files/materials',ROOT/'output/phase-runner/shared-assets/materials',
                     ROOT/'output/phase-runner/common-assets/exported_files/materials',ROOT/'output/phase-runner/common-assets/materials',
                     ROOT/'output/phase-runner/legion-assets/exported_files/materials']
        available_materials={p.name for d in source_dirs if d.is_dir() for p in d.iterdir() if p.is_dir() and (p/(p.name+'_albedoTexture.dds')).is_file()}
        available_materials.update(k.rsplit('/',1)[-1] for k in json.loads((ROOT/'output/phase-runner/world-materials/mapping.json').read_text())['materials'])
        def priority(p):
            if '/rocks/' not in p['model']:return (0,0.,sum(v*v for v in p['origin'][:2]))
            mesh,_=load_mesh(p['source_qc'])
            extent=[max(c[k] for _,vs in mesh for c in vs)-min(c[k] for _,vs in mesh for c in vs) for k in range(3)]
            return (1,-extent[0]*extent[1]*p['scale']**2,sum(v*v for v in p['origin'][:2]))
        candidates.sort(key=priority)
    else:
        candidates.sort(key=lambda p:('/rocks/' in p['model'] if area_details else False,sum((p['origin'][k]-anchor[k])**2 for k in range(3))))
    output=ROOT/'output/phase-runner'/('broad-geometry' if broad_restore else 'missing-section-geometry' if missing_sections else 'area-detail-geometry' if area_details else 'support-geometry' if support_structures else ('phase-structure-geometry' if phase_structures else 'prop-geometry'))
    output.mkdir(parents=True,exist_ok=True)
    cache={}
    streams={}
    counts=collections.Counter()
    restored=[]
    omitted=[]
    triangles=0
    ambiguous_triangles=0
    budget=2700000 if broad_restore else 500000 if area_details else 750000
    try:
        for prop in candidates:
            if prop['model'] not in cache:
                cache[prop['model']]=load_mesh(prop['source_qc'],missing_only=missing_sections)
            mesh,skins=cache[prop['model']]
            if not mesh: continue
            if triangles+len(mesh)>budget:
                omitted.append(prop['index'])
                continue
            skin=skins[prop['skin']] if prop['skin']<len(skins) else skins[0]
            if broad_restore:
                required={skin[0] if name=='default_material' else (skin[skins[0].index(name)] if prop['skin'] and name in skins[0] and skins[0].index(name)<len(skin) else name) for name,_ in mesh}
                missing=required-available_materials
                if missing:
                    unavailable.append(dict(index=prop['index'],model=prop['model'],missing_materials=sorted(missing)))
                    continue
            matrix=rotation(prop['angles'])
            minimum=[float('inf')]*3
            maximum=[float('-inf')]*3
            batches=collections.defaultdict(bytearray)
            for name,corners in mesh:
                ambiguous=name=='default_material'
                if ambiguous:
                    name=skin[0]
                    ambiguous_triangles+=1
                elif prop['skin'] and name in skins[0]:
                    slot=skins[0].index(name)
                    if slot<len(skin): name=skin[slot]
                material='prop/'+name
                for vertex in corners:
                    position=transform(vertex[:3],matrix,prop['origin'],prop['scale'])
                    normal=transform(vertex[3:6],matrix)
                    length=math.sqrt(sum(v*v for v in normal))
                    if length<1e-6:
                        raise ValueError('Degenerate prop normal')
                    normal=tuple(v/length for v in normal)
                    for k in range(3):
                        minimum[k]=min(minimum[k],position[k]);maximum[k]=max(maximum[k],position[k])
                    batches[material].extend(struct.pack('<8f',*position,*normal,vertex[6],1-vertex[7]))
                counts[material]+=1
            for material,payload in batches.items():
                if material not in streams:
                    path=output/(material.rsplit('/',1)[-1]+'.bin')
                    streams[material]=path.open('wb')
                streams[material].write(payload)
            triangles+=len(mesh)
            restored.append(dict(index=prop['index'],model=prop['model'],triangles=len(mesh),
                                 bounds=[minimum,maximum],origin=prop['origin'],angles=prop['angles'],scale=prop['scale']))
    finally:
        for stream in streams.values(): stream.close()
    report=dict(candidate_props=len(candidates),restored_props=len(restored),
        models=len({p['model'] for p in restored}),source_models_examined=len(cache),
        triangles=triangles,triangle_budget=budget,omitted_for_budget=len(omitted),
        ambiguous_material_triangles=ambiguous_triangles,material_counts=dict(counts),
        restored=restored,collision_added=False,omitted_for_materials=unavailable,
        limitations=['Baked structural prop render geometry only; native model compilation remains unfinished.',
                     'Lost default_material bindings approximate the first original QC skin material.',
                     *(['Truncated Marvin exports are excluded from section restoration.'] if missing_sections else []),
                     ('Foliage, decals, unavailable meshes/materials and placements exceeding the render budget are omitted.' if broad_restore else 'Foliage, decals, blue barrels without textures, unavailable meshes and placements exceeding the area budget are omitted.' if area_details else 'Foliage, rock/terrain props and unavailable source meshes are not included in this pass.')])
    (output/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('restored','material_counts')},indent=2))


if __name__=='__main__':
    stage()
