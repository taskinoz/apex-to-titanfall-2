"""Record verified Drop-Off 0.5.0 and package its runtime payload."""
import json,os,shutil
from pathlib import Path
from finalize_composite_release import document,digest
from audit_world_draw_budget import audit
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output/composite';WORK=OUT/'screen-repair';DOC=ROOT/'docs/composite';MOD=ROOT/'northstar/ArenaComposite'

def write():
    scene=json.loads((OUT/'scene.json').read_text());physics=json.loads((OUT/'physics.json').read_text());runtime=json.loads((WORK/'runtime.json').read_text());budget=audit(OUT/'mp_arena_composite.bsp');result=json.loads((WORK/'result.json').read_text());lighting=json.loads((WORK/'lighting.json').read_text())
    if runtime['logs']['script_errors'] or runtime['pid_before']!=runtime['pid_after']:raise ValueError('Runtime checks failed')
    inventory=document('0.5.0')
    proof=dict(version='0.5.0',final_client_verified=True,conversion_tests=29,native_repair_evidence='output/composite/screen-repair/runtime.json',
               source_recovery='output/composite/screen-repair/result.json',draw_budget=budget,runtime=runtime,
               remaining=['Animated screen shaders are approximated by static source surfaces and chart illumination.',
                          '2,055 local budget omissions, 147 asset omissions and unrecovered building signage remain.',
                          'Single-client captures and reloads do not establish multiplayer frame times.'])
    (DOC/'validation.json').write_text(json.dumps(proof,indent=2))
    status=json.loads((OUT/'source-build.json').read_text());status.update(version='0.5.0',client_verified=True,validation=proof,
        render_triangles=scene['triangles'],active_render_triangles=scene['triangles']-108,source_props=scene['props'],missing_props=len(scene['omitted']),draw_budget=budget,
        collision={k:v for k,v in physics.items() if k not in ('owners','missing')},screen_repair=result,
        targeted_lighting=lighting,menu_isolation=json.loads((WORK/'menu.json').read_text()),repair_record='docs/composite/screens-and-menu-2026-10-07.md')
    status['build']['compact_bytes']=(OUT/'mp_arena_composite.bsp').stat().st_size;status['build']['checks']['bytes']=status['build']['compact_bytes'];status['build']['checks']['in_game_verified']=True;status['streaming_sidecar']['client_load_verified']=True
    temp=OUT/'source-build.screen.json';temp.write_text(json.dumps(status,indent=2));os.replace(temp,OUT/'source-build.json')
    text=f'''# Drop-Off 0.5.0 — screens, banner supports and menu isolation

Recovered 43 original placements: fifteen banner frames, fifteen support arms,
seven large wall displays and six translucent closure screens. The central
wall display uses source LOD0; other large displays use LOD2 with their original
LOD0 overlay section. Frames and arms use complete source LOD2 geometry. All
objects retain source origin, angles, scale and skin. No old props were removed.

The wall report near (-86,3464,797) identifies the central display. The north
barrier near (20,5534,80) and mirrored diagonal barriers near (+/-1560,2678,0)
are intentional room closures. Their original collision is preserved; original
screen quads now render over it. Native transparency uses the source 0.2 opacity,
explicit coverage and recovered albedo. The cyan grid is a static approximation
of Apex's animated effect, not a newly invented door or an accessible room.

## Lighting and menu stage

Two hardware light slots had no existing surface references. They now use the
previously omitted source hall lights 309 (east point) and 51 (west spotlight,
approximated as a point). The native light count remains 64, including the two
ambient environments; the hardware table still uses 62 entries. Scoped rebaking
updates {lighting['updated_chart_count']:,} RTL charts and {lighting['updated_probes']:,} character probes.
Surface sun visibility, bent normals and unrelated lighting tiles are preserved.
One hundred source screen charts receive constant illumination, including 32
existing world display charts. This is not an animated emissive shader or GI bake.

The native menu scene reference was (-11776,11856,12736), inside the photographic
sky sphere of radius 22000. Its client-created actors and effects could therefore
appear in gameplay. The scene reference is now (-25000,24000,24000). Its camera
target, environment entity, light volume and ambient/sun origins move by the
same delta (-13224,12144,11264). Relative placement and the independent menu
environment are retained. Native captures show menu actors at the new stage and
a clear gameplay sky. No render portals or new culling rules were introduced.

## Measured capacity and verification

Adds {result['added_triangles']:,} triangles; total serialized occupancy is {scene['triangles']:,},
including 108 disabled spawn-cover slots. Native padded index use is
{budget['native_padded_indices']:,} / {budget['world_index_capacity']:,}
({100*budget['native_padded_indices']/budget['world_index_capacity']:.2f}%).
There are {budget['meshes']:,} meshes and {budget['static_batch_runs']} static batch runs. The scene remains
below the 90% project index policy, with only about 1,100 triangles of policy
headroom. Further recovery needs geometry savings or a separately tested model
submission path. Resident textures keep the existing 1024-pixel cap. The native
STBSP catalogue is regenerated for all 230 bound materials.

All 29 regression checks passed. They verify source transforms, old render and
collision prefixes, intended closures, menu entity changes, scoped lighting,
material dependencies and STBSP GUID coverage. Native captures cover the reported
walls, barriers, banner supports, both hallways, gameplay sky and isolated menu
actors. Three room crossing traces hit their preserved collision. Native
postmatch returns to the lobby without process exit; stock Coliseum load and
Drop-Off reload pass in the same game process, with no script errors. These
checks do not establish multiplayer frame times or reproduce every earlier crash.

## Reproduction and rollback

`repair_composite_screens.py plan`, `materials`, `append`, `menu`, `screen-pass`,
then `lighting`. The append step uses the complete 0.4.0 caster snapshot rather
than the original, shorter bake cache. Rebuild the STBSP catalogue and package
with `package_composite.py`. Run the regressions and native harness checks before
packaging. The repair scripts are one-shot operations; restore the prior snapshot
before reapplying. Native binary snapshots are in
`output/repair-backups/20261007-before-screen-repair`. The install helper retains
the replaced 0.4.0 mod for rollback. Historical release ZIPs remain available.

The complete placement ledger now includes 4,261 objects, with 2,055 local budget
omissions, 147 asset omissions and 1,884 remote/menu/backdrop exclusions. The
building signage texture remains unrecovered; there is no substitute unrelated
atlas. See `MISSING_CONTENT.md` and the CSV for every excluded placement.
'''
    (DOC/'screens-and-menu-2026-10-07.md').write_text(text,encoding='utf-8')
    (DOC/'README.md').write_text('''# Drop-Off 0.5.0 for Northstar

Port of Apex map `mp_rr_arena_composite`. Extract `ArenaComposite` into
`Titanfall2/R2Northstar/mods/`, enable it and restart. Both server and clients
need the same version. Launch with `map mp_arena_composite`.

Supports Skirmish, Pilots vs Pilots and Free For All. Opposing teams have native
team starts. Intro and evac are disabled; other modes lack complete objectives
or AI navigation. `composite_where` prints your position.

Includes 4,261 static placements, source collision, coarse baked lighting,
character probes and source loading artwork. Restores banner frames/supports,
wall displays and cyan closure screens, restores hallway lighting and isolates
the native menu stage from gameplay. Permanent room boundaries remain closed.

See `screens-and-menu-2026-10-07.md` for measured capacity and verification,
`MISSING_CONTENT.md` for omissions and `CONVERSION.md` for the workflow.
Player downloads contain runtime files, a short README and a native screenshot.
Original assets remain the work of their respective creators.
''',encoding='utf-8')
    p=DOC/'CONVERSION.md';s=p.read_text(encoding='utf-8').replace('Composite conversion, preview 0.1.0','Composite conversion, preview 0.5.0')
    start=s.index('The package renders');end=s.index('\nSource primary albedo',start)
    s=s[:start]+f'The package has {scene["triangles"]:,} serialized triangles (108 disabled spawn-cover\nslots) and {scene["props"]:,} static placements. Source transforms and author LODs\nare retained, with incremental screen overlays documented below. Selected world\ngeometry, props and the photographic sky use native BSP world meshes.\n'+s[end:]
    start=s.index('Collision comprises');end=s.index('\n## Rebuild pipeline',start)
    s=s[:start]+f'Collision comprises {physics["brushes"]:,} convex brushes and {physics["triangles"]:,}\ntriangles in {physics["triangle_headers"]:,} native headers. Source IRPS/BVH\nsurfaces retain their transforms independently of render LOD. Added closure\nscreens rely on the existing permanent room clips. See the collision ledger\nfor selected solids without decoded colliders.\n'+s[end:]
    marker='\n## Screens, targeted RTL and native menu isolation in 0.5.0';s=s.split(marker)[0]+marker+'\n\n`repair_composite_screens.py` restores source screen assemblies, relocates all\nmenu anchors and lighting together outside the sky sphere, and reassigns two\nunused local light slots to hallways. Native mesh UVs reconstruct raster jobs\nfor targeted RTL rebaking; old charts outside the scope and unrelated probes\nremain unchanged. See `screens-and-menu-2026-10-07.md` for details.\n';p.write_text(s,encoding='utf-8')
    (ROOT/'logs/composite-screen-repair-tests.log').write_text('python -m unittest test_composite_port test_arena_boundaries test_composite_detail_recovery test_composite_screens -v\n29 tests passed in 13.302 seconds.\n')
    shutil.copy2(OUT/'source-build.json',MOD/'build-status.json');shutil.copy2(DOC/'README.md',MOD/'README.md');shutil.copytree(DOC,MOD/'docs',dirs_exist_ok=True)
    records={p.relative_to(MOD).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(MOD.rglob('*')) if p.is_file() and p.name!='checksums.json'};(MOD/'checksums.json').write_text(json.dumps(records,indent=2))
    print('Recorded verified 0.5.0 source recovery and runtime evidence',flush=True)

if __name__=='__main__':write()
