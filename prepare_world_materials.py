"""Stage recovered Apex DDS images with native TF2 world material templates."""
import collections
import json
import shutil
import struct
from pathlib import Path
from extract_native_material import NativePak

ROOT = Path(__file__).resolve().parent


def prepare():
    counts = collections.Counter()
    material = ''
    for line in (ROOT/'output/phase-runner/mp_rr_arena_phase_runner.obj').open():
        if line.startswith('usemtl '):
            material = line.split()[1]
        elif line.startswith('f ') and not material.startswith('tools/'):
            counts[material] += len(line.split())-3
    sources = [ROOT/'output/phase-runner/terrain-atlas/materials',ROOT/'tools/legion/exported_files/materials',
               ROOT/'output/phase-runner/shared-assets/materials',
               ROOT/'output/phase-runner/common-assets/exported_files/materials',
               ROOT/'output/phase-runner/common-assets/materials',
               ROOT/'output/phase-runner/legion-assets/exported_files/materials']
    project = ROOT/'output/phase-runner/world-materials'
    assets = project/'assets'
    pak = NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
    primary = next(a for a in pak.assets if a['guid'] == 0x92424EA716974A64)
    spec, uber = pak.material(primary)
    colpass = next(a for a in pak.assets if a['guid'] == 0x1F8E00B988C71BBB)
    color_spec, color_uber = pak.material(colpass)
    files = []
    mapped = {}
    prop_report = ROOT/'output/phase-runner/prop-geometry/report.json'
    prop_counts = json.loads(prop_report.read_text())['material_counts'] if prop_report.is_file() else {}
    for report_name in ('support-geometry','area-detail-geometry','missing-section-geometry','broad-geometry','portal-geometry','landscape-geometry'):
        support_report=ROOT/'output/phase-runner'/report_name/'report.json'
        if support_report.is_file():
            for name,count in json.loads(support_report.read_text())['material_counts'].items():
                prop_counts[name]=prop_counts.get(name,0)+count
    atlas_report=ROOT/'output/phase-runner/terrain-atlas/report.json'
    if atlas_report.is_file():prop_counts.update(json.loads(atlas_report.read_text())['material_counts'])
    for material, triangles in sorted(counts.items()) + sorted(prop_counts.items()) + [('sky/phase_runner_sky',0)]:
        basename = material.rsplit('/', 1)[-1]
        images = next((source/basename for source in sources
                       if (source/basename/(basename+'_albedoTexture.dds')).is_file()),None)
        if images is None:
            continue
        diffuse = images/(basename+'_albedoTexture.dds')
        raw = diffuse.read_bytes()
        if raw[:4] != b'DDS ' or len(raw) < 128:
            raise ValueError(f'Invalid DDS: {diffuse}')
        height, width = struct.unpack_from('<2I', raw, 12)
        textures = {}
        for slot, semantic in [(0,'albedo'),(1,'normal'),(2,'gloss'),(3,'spec')]:
            image = images/(basename+'_'+semantic+'Texture.dds')
            if not image.is_file():
                continue
            path = f'texture/phase_runner_preview/{basename}_{semantic}.rpak'
            target = (assets/path).with_suffix('.dds')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, target)
            files.append({'_type':'txtr','_path':path,'$disableStreaming':True})
            textures[str(slot)] = path
        world_name = f'world/phase_runner_preview/{basename}'
        primary_path = f'material/{world_name}_wld.rpak'
        color_path = f'material/{world_name}_colpass_wld.rpak'
        for path, template, buffer in [(color_path,color_spec,color_uber),(primary_path,spec,uber)]:
            new = dict(template)
            # RePak's shared JSON representation uses eight render targets;
            # its v12 writer retains the first four native TF2 targets.
            new['blendStates'] = template['blendStates'] + ['0x0']*4
            new['name'] = world_name + ('_colpass' if path == color_path else '')
            new['width'], new['height'] = width, height
            new['$textures'] = dict(template['$textures']) | textures
            if path == primary_path:
                new['$colpassMaterial'] = color_path
            target = assets/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.with_suffix('.json').write_text(json.dumps(new, indent=2))
            target.with_suffix('.uber').write_bytes(buffer)
            files.append({'_type':'matl','_path':path})
        if triangles:
            mapped[material] = dict(name=world_name,triangles=triangles,width=width,height=height)
    report = dict(source_triangles=sum(counts.values()),source_materials=len(counts),
                  recovered_triangles=sum(mapped[m]['triangles'] for m in counts if m in mapped),
                  recovered_materials=sum(m in mapped for m in counts),materials=mapped,
                  prop_materials=sum(m in mapped for m in prop_counts),
                  prop_textured_triangles=sum(mapped[m]['triangles'] for m in prop_counts if m in mapped),
                  missing={m:n for m,n in counts.items() if m not in mapped},
                  limitation='Native TF2 world shader approximation; Apex blend/layer shaders are not reproduced.')
    project.mkdir(parents=True, exist_ok=True)
    (project/'mapping.json').write_text(json.dumps(report, indent=2))
    manifest = dict(version=7,name='phase_runner_world',keepDevOnly=True,
                    assetsDir=str(assets),outputDir=str(project/'build'),
                    compressLevel=0,hasDynamicLibrary=False,
                    files=list({entry['_path']:entry for entry in files}.values()))
    (project/'build.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('materials','missing')}, indent=2))


if __name__ == '__main__':
    prepare()
