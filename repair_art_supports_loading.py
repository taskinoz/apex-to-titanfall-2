"""Embed a uniquely identified decal shader to remove a sibling-pak dependency."""
import json,os,shutil,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from extract_world_glass_shader import extract
from extract_native_material import NativePak
from build_phase_runner_presentation import guid
from finalize_lighting_release import digest
SOURCE=ROOT/'output/phase-runner/art-support-materials'
PROJECT=ROOT/'output/phase-runner/art-support-loading-materials'
PACKAGE=ROOT/'northstar/PhaseRunner.ArtSupportsLoadingRelease'

def build():
    shutil.copytree(SOURCE/'assets',PROJECT/'assets',dirs_exist_ok=True)
    manifest=json.loads((SOURCE/'build.json').read_text());manifest['assetsDir']=str(PROJECT/'assets');manifest['outputDir']=str(PROJECT/'build')
    shaderpath='shaderset/phase_runner_road_decal.rpak';target=(PROJECT/'assets'/shaderpath).with_suffix('.msw')
    proof=extract(target);raw=bytearray(target.read_bytes())
    ps=guid('shader/phase_runner_road_decal_pixel.rpak');vs=guid('shader/phase_runner_road_decal_vertex.rpak');struct.pack_into('<2Q',raw,5,ps,vs);target.write_bytes(raw)
    material=PROJECT/'assets/material/world/phase_runner_preview/decals_asphalt_road_dirty_01_alpha_wld.json'
    spec=json.loads(material.read_text());old=spec['shaderSet'];spec['shaderSet']=shaderpath;material.write_text(json.dumps(spec,indent=2))
    manifest['files'].insert(0,dict(_type='shds',_path=shaderpath));(PROJECT/'build.json').write_text(json.dumps(manifest,indent=2))
    r=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(PROJECT/'build.json')],capture_output=True,text=True);(PROJECT/'build.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Shader rebuild failed')
    p=PROJECT/'build/phase_runner_art_supports.rpak';pak=NativePak(p);assets={a['guid']:a for a in pak.assets}
    if any(g not in assets for g in (ps,vs,guid(shaderpath))):raise ValueError('Embedded shader missing')
    for f in (ROOT/'northstar/PhaseRunner.ArtSupportsRelease').rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(ROOT/'northstar/PhaseRunner.ArtSupportsRelease');dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        actual=p if rel.as_posix()=='paks/phase_runner_art_supports.rpak' else f
        if dest.exists():dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    meta=json.loads((PACKAGE/'mod.json').read_text());meta['Version']='0.1.44';meta['Description']='Phase Runner art supports with an independent native decal shader.';(PACKAGE/'mod.json').write_text(json.dumps(meta,indent=2))
    proof.update(old_external_shader=old,new_embedded_shader=hex(guid(shaderpath)),new_pixel_guid=hex(ps),new_vertex_guid=hex(vs),material_only_repair=True,geometry_and_collision_unchanged=True,rpak_sha256=digest(p))
    (PROJECT/'repair.json').write_text(json.dumps(proof,indent=2));(PACKAGE/'loading-repair.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2),flush=True)
if __name__=='__main__':build()
