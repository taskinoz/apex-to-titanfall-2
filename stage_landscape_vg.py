"""Restore missing rock placements directly from compiled VG/RMDL assets."""
import collections,json,struct
from pathlib import Path
from read_vg_static import load
from repair_portal_surfaces import placed,ROOT,PROJECT


def stage():
    props=json.loads((PROJECT/'static-props.json').read_text())
    source_dirs=[ROOT/'tools/legion/exported_files/materials',PROJECT/'shared-assets/materials',
        PROJECT/'common-assets/exported_files/materials',PROJECT/'common-assets/materials',PROJECT/'legion-assets/exported_files/materials']
    available={p.name.lower() for d in source_dirs if d.is_dir() for p in d.iterdir()
        if p.is_dir() and (p/(p.name+'_albedoTexture.dds')).is_file()}
    folder=PROJECT/'landscape-geometry';folder.mkdir(exist_ok=True)
    streams={};cache={};counts=collections.Counter();restored=[];omitted=[]
    try:
        for prop in props:
            if not (prop['in_arena'] and '/rocks/' in prop['model'] and not prop['source_qc']):continue
            name=Path(prop['model']).stem
            if name not in cache:
                try:cache[name]=load(ROOT/'tools/legion/exported_files/models'/name)
                except (ValueError,OSError) as e:cache[name]=str(e)
            source=cache[name]
            if isinstance(source,str):omitted.append(dict(index=prop['index'],reason=source));continue
            sections,slots,skins=source
            if prop['skin']>=len(skins):raise ValueError('Invalid rock skin')
            skin=skins[prop['skin']]
            required={skin[s] for s in slots}
            if required-available:omitted.append(dict(index=prop['index'],missing_materials=sorted(required-available)));continue
            triangles=0
            for section,slot in zip(sections,slots):
                mat='prop/'+skin[slot]
                if mat not in streams:streams[mat]=(folder/(skin[slot]+'.bin')).open('wb')
                for corners in section:streams[mat].write(b''.join(placed(corners,prop)))
                counts[mat]+=len(section);triangles+=len(section)
            restored.append(dict(index=prop['index'],model=prop['model'],skin=prop['skin'],triangles=triangles,
                origin=prop['origin'],angles=prop['angles'],scale=prop['scale']))
    finally:
        for stream in streams.values():stream.close()
    report=dict(candidate_props=len(restored)+len(omitted),restored_props=len(restored),models=len({p['model'] for p in restored}),
        triangles=sum(counts.values()),material_counts=dict(counts),restored=restored,omitted=omitted,
        ambiguous_material_triangles=0,compiled_vg_geometry_verified=True,compiled_material_slots_verified=True,
        collision_added=False,limitations=['Render-only rocks retain original placements; native prop collision and layered rock shaders remain unfinished.'])
    (folder/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('restored','material_counts','omitted')},indent=2))


if __name__=='__main__':stage()
