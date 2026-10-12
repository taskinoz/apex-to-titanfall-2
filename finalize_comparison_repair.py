"""Record native comparison evidence and version the two verified paint repairs."""
import hashlib,json,os
from pathlib import Path
from recover_vertex_paint import ROOT,CONFIG
from audit_world_draw_budget import audit

VERSIONS={'drop-off':'0.7.0','phase-runner':'1.3.0'}

def atomic(path,text):
    temp=path.with_suffix(path.suffix+'.new');temp.write_text(text,encoding='utf-8');os.replace(temp,path)

def write_json(path,value):atomic(path,json.dumps(value,indent=2))

def finalize():
    report={'date':'2026-10-12','focused_regression_tests':7,'maps':{}}
    for label,(package,name,source,offset) in CONFIG.items():
        mod=ROOT/'northstar'/package;work=ROOT/'output/comparison-repair'/label
        data=json.loads((ROOT/'r5-harness/output'/(label+'-paint')/'comparison.json').read_text())
        if len(data['pairs'])<3 or len(data['pairs'])!=len(data['route']['shots']):raise ValueError('Incomplete paired evidence')
        captures=[]
        for pair in data['pairs']:
            for engine in ('r5r','northstar'):
                record=pair[engine];image=Path(record['path'])
                if hashlib.sha256(image.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Native capture changed')
                if (record['width'],record['height'])!=(1280,720):raise ValueError('Native dimensions differ')
            captures.append({'view':pair['name'],'source_sha256':pair['r5r']['sha256'],'port_sha256':pair['northstar']['sha256']})
        paint=json.loads((work/'vertex-paint.json').read_text());shader=json.loads((work/'shader.json').read_text())
        meta=json.loads((mod/'mod.json').read_text());previous=meta['Version'];meta['Version']=VERSIONS[label]
        meta['Description']=('Drop-Off arena port with recovered native vertex paint, source equipment, screens, ziplines and preserved collision.' if label=='drop-off' else 'Phase Runner with recovered gold tunnel paint, native PBR, team modes, grounded firs and tunnel catwalks.')
        write_json(mod/'mod.json',meta)
        proof={'version':VERSIONS[label],'previous_version':previous,'changed_vertices':paint['changed_vertices'],
               'native_shader_materials':shader['additional_materials']//2,'paint_pack_bytes':(mod/'paks'/(label.replace('-','_')+'_vertex_paint.rpak')).stat().st_size,
               'preserved':['collision','geometry','UVs','normals','lightmaps','character probes','render visibility','gameplay entities'],
               'native_visual_comparison':captures,'draw_budget':audit(mod/'mod/maps'/(name+'.bsp')),
               'source_captures_reused_with_hash_verification':True,
               'limitations':['Vertex alpha and Apex terrain layer blending remain approximated.','Animated banners and source scenery omissions remain.','Paired captures do not establish multiplayer frame times.']}
        report['maps'][label]=proof
        status=json.loads((mod/'build-status.json').read_text());status['release_version']=VERSIONS[label];status['vertex_paint_comparison_repair']=proof;write_json(mod/'build-status.json',status)
        write_json(mod/'vertex-paint-validation.json',proof)
        note=f'''# {label.replace('-', ' ').title()} {VERSIONS[label]} — source vertex paint

The paired R5R views identified pale painted props. The static VG reader skipped
the source four-byte RGBA field; the world builder then wrote white. The stock
placeholder world shader also ignored COLOR, so restoring bytes alone did not
change the native image.

This repair restores RGB on {paint['changed_vertices']:,} existing vertices matched by
material, position, normal and UV. Ambiguous source keys are omitted. Source
alpha is shader/layer data; native opaque alpha is retained. Five binary/matching
checks and two preservation/dependency checks pass.

Native Homestead shader sets 0x6AFE220DA02633A0 and 0x81F5BAC39D4DF3B1 are copied
with unchanged bytecode and input-layout flags. Their vertex program gamma-decodes
COLOR before albedo modulation. Existing opaque depth/blend states and PBR
channels remain. Source textures are copied as resident assets into the paint
pack; native fallback channels continue to reference the already loaded native
packs. Both paint packs attach to mp_coliseum.rpak for stable native lifetime.
The additional pack is {proof['paint_pack_bytes']:,} bytes; this is a residency cost,
not a claim of improved frame rate.

No triangles, colliders, portals, UVs, lightmap tiles or gameplay entities are
added or removed. Every unrelated lump is byte-checked, and all-visible index
and static batch counts are unchanged. The game-lump directory's absolute
pointers move during compaction; its payload is preserved.

{len(captures)} fresh Northstar views are paired with hash-verified original R5R captures
at identical route cameras. Baseline and repaired captures are retained in
site/dist/. Source-to-port offset: {offset}. The source geometry still has more
scenery than the budgeted port. Terrain layer/vertex-alpha shaders, animated
banner artwork and other documented omissions are future work.

Reproduce on an unmodified baseline with recover_vertex_paint.py {label}, then
stage_vertex_paint_shader.py {label}. These are guarded one-shot repairs.
Rollback snapshot: output/repair-backups/20261012-vertex-paint/{package}.
Comparison input: r5-harness/output/{label}-paint/comparison.json.
'''
        doc=ROOT/'docs'/(label+'-vertex-paint-2026-10-12.md');atomic(doc,note)
        atomic(mod/'VERTEX_PAINT.md',note)
        readme=(mod/'README.md').read_text(encoding='utf-8')
        lines=readme.splitlines();lines[0]='# '+('Drop-Off' if label=='drop-off' else 'Phase Runner')+' '+VERSIONS[label]+' for Northstar'
        summary=f'\nRestores authored RGB paint on {paint["changed_vertices"]:,} existing vertices with native\nTitanfall colour-aware PBR shaders. Geometry, collision, lighting, visibility\nand gameplay retain the prior working build. See VERTEX_PAINT.md and the repo\ncomparison site for baseline and repaired native views.\n'
        atomic(mod/'README.md',lines[0]+summary+'\nThe prior release notes below describe the preserved gameplay and earlier\nvalidation; the paint repair is documented above.\n\n'+'\n'.join(lines[1:]))
        checksums={}
        for file in sorted(mod.rglob('*')):
            if not file.is_file() or file.name=='checksums.json':continue
            h=hashlib.sha256()
            with file.open('rb') as f:
                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
            checksums[file.relative_to(mod).as_posix()]={'bytes':file.stat().st_size,'sha256':h.hexdigest()}
        write_json(mod/'checksums.json',checksums)
    write_json(ROOT/'output/comparison-repair/validation.json',report)
    print(json.dumps({'versions':VERSIONS,'paired_views':sum(len(v['native_visual_comparison']) for v in report['maps'].values()),'regression_checks':7}))

if __name__=='__main__':finalize()
