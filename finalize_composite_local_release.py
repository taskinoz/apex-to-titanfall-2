"""Document and package the verified 0.6 source repairs without touching Phase Runner."""
import json,os,shutil
from pathlib import Path
from audit_world_draw_budget import audit
from finalize_composite_release import document,digest
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output/composite';WORK=OUT/'local-repair';DOC=ROOT/'docs/composite';MOD=ROOT/'northstar/ArenaComposite'
def write():
 pending=False
 runtime=json.loads((WORK/'runtime.json').read_text())
 assert not runtime['logs']['script_errors'] and runtime['pid_before']==runtime['pid_after']
 tests=(ROOT/'logs/composite-local-repair-tests.log').read_text();assert 'Ran 35 tests' in tests and tests.rstrip().endswith('OK')
 scene=json.loads((OUT/'scene.json').read_text());physics=json.loads((OUT/'physics.json').read_text());budget=audit(OUT/'mp_arena_composite.bsp');inventory=document('0.6.0')
 proof=dict(version='0.6.0',final_client_verified=not pending,conversion_tests=35,native_repair_evidence=None if pending else 'output/composite/local-repair/runtime.json',source_recovery='output/composite/local-repair/result.json',draw_budget=budget,runtime=runtime,remaining=['Recovered containers and supports use complete source LOD3; source collision stays higher fidelity.', 'Four-texel charts remain elsewhere; this is not a full production lighting bake.', 'Single-client photographs and reloads do not establish multiplayer performance.'])
 (DOC/'validation.json').write_text(json.dumps(proof,indent=2))
 status=json.loads((OUT/'source-build.json').read_text());status.update(version='0.6.0',client_verified=not pending,validation=proof,render_triangles=scene['triangles'],active_render_triangles=scene['triangles']-132,source_props=scene['props'],missing_props=len(scene['omitted']),draw_budget=budget,local_repair=json.loads((WORK/'result.json').read_text()),orphan_lamp=json.loads((WORK/'orphan.json').read_text()),chart_gutters=json.loads((WORK/'gutters.json').read_text()),wall_lighting=[json.loads((WORK/(n+'.json')).read_text()) for n in ('walls','walls-small','wall-pages')],repair_record='docs/composite/local-repairs-2026-10-07.md')
 status['build']['compact_bytes']=(OUT/'mp_arena_composite.bsp').stat().st_size;status['build']['checks']['bytes']=status['build']['compact_bytes'];status['build']['checks']['in_game_verified']=not pending;status['streaming_sidecar']['client_load_verified']=not pending
 temp=OUT/'source-build.local.json';temp.write_text(json.dumps(status,indent=2));os.replace(temp,OUT/'source-build.json')
 (DOC/'local-repairs-2026-10-07.md').write_text(f'''# Drop-Off 0.6.0 — source attachments and wall lighting

## Reported locations

| Report | Source diagnosis | Repair |
| --- | --- | --- |
| Lamp (-8,2273,66) | Placement 5093 was attached to shield 4924, removed in 0.2.0. Its bounds were contained in the shield assembly; no wall exists at this height. | Disable exactly 24 lamp draw and shadow triangles. It was non-solid. |
| Floating boxes (-438,132,130) | Air units, tall panels and generator sit above the omitted mounted server unit 2914. | Restore the complete source server body at its original transform, plus mirrored support 2916. |
| Invisible object (-19,1962,-59) | Source world collision outlines stacked containers 5287 and 5288, but neither visual was included. | Restore both container visuals at their original transforms; retain their existing collider. |
| Jagged wall shadows (-1917,631,192) | Native fullbright removes the marks. Sparse four-texel charts sample trim shadows at triangle vertices and spread them across large panels. | Rebake 1,302 large painted-wall triangles with 32x32 charts and 948 smaller triangles with 16x16 charts at both control entrances. |

All four recovered objects use complete source LOD3, adding 910 triangles. No
new duplicate collider is added. Every collision stream, grid, entity, world
light and character probe is byte-identical to 0.5.0. Original geometry,
albedo UVs, normals and tangent frames survive; only scoped wall lightmap UVs
and the 24 orphan lamp indices change. Room closures and source ziplines remain.

## Lightmap correction

Baseline padding used a global nearest-sample expansion, allowing adjacent
triangle charts to supply gutter samples. Correct all allocated 4x4 chart
gutters from the six valid samples inside that same chart. Original valid
samples remain byte-identical. This alone did not remove the wall artifacts.

For vertical research-station painted-metal panels within 1,200 units of
(-1917,631,600) or (1917,631,600), large triangles of area greater than 1,000
get 32x32 charts (351 raster samples each). Triangles of area 100..1,000 get
16x16 charts (105 samples each). Other materials and smaller triangles retain
their existing chart resolution. Sun, sky and local-light receivers are baked
against the complete current opaque scene. Receiver pixels lie slightly inside
the triangle rather than exactly at a shared vertex. Gutters stay within each
new chart. Existing lights, probes and other chart interiors are retained.

The new charts occupy spare space on atlas page three: large charts begin at
pixel row 1248; small charts begin at row 1920. No existing allocation overlaps
them. Native material sorts store the lightmap page per mesh, so affected
meshes are split by page and the original triangle indices are repartitioned
with native pair padding. Vertex UV changes alone are insufficient and were
rejected by the in-game verification. Reserved chart rectangles are recorded
in `output/composite/local-repair/wall-scope.npz`; future append operations
reject overlapping allocations. Total page count and texture memory stay fixed.

## Capacity and verification

{scene['props']:,} source placements; {scene['triangles']:,} serialized triangle slots;
{scene['triangles']-132:,} active triangles. The 132 disabled slots comprise 108
temporary spawn covers and 24 orphan lamp triangles. Native padded index use is
{budget['native_padded_indices']:,} / {budget['world_index_capacity']:,}
({100*budget['native_padded_indices']/budget['world_index_capacity']:.3f}%).
The project 90% policy leaves about 200 triangles, depending on mesh padding.
There are {budget['meshes']:,} meshes and {budget['static_batch_runs']} static batch runs.
Further substantial recovery requires geometry savings. The STBSP catalogue
covers 231 native materials; resident texture cap stays at 1024 pixels.

35 regression tests passed. Tests protect the complete old active triangle set,
exact orphan selection, source transforms, every collision stream, lights,
probes, valid old lighting samples, isolated gutters, atlas allocation,
correct native page bindings, material dependencies and submission budgets.
Native screenshots inspect all reported locations and both control entrances.
Three collision rays contact the preserved source colliders. Postmatch returns
to the lobby; stock Coliseum and Drop-Off reload in the same game process with
no script errors. These are single-client checks, not multiplayer performance
measurements. Coarse lighting, source shader approximations and missing assets
elsewhere remain documented in the inventory.

## Reproduction and rollback

Run `repair_composite_local.py` with `plan`, `materials`, `orphan`, `append`,
`gutters`, `walls`, `wall-pages`, `walls-small`, then `wall-pages` again. These
are staged one-shot operations; restore the 0.5.0 backup before reapplying.
Regenerate STBSP, package the mod, run the five regression suites and
`verify_composite_local_runtime.py`, then finalize and make the clean player ZIP.
The binary and configuration snapshot is
`output/repair-backups/20261007-before-local-repair`. The installed 0.5.0 mod
is also retained by the install helper. Historical ZIP releases are preserved.

Player distribution contains runtime mod files, a short README and a native
screenshot. Development scripts and ledgers remain in the workspace. Phase
Runner is not rebuilt or reinstalled in this release.
''',encoding='utf-8')
 (DOC/'README.md').write_text('''# Drop-Off 0.6.0 for Northstar

Port of Apex map `mp_rr_arena_composite`. Extract `ArenaComposite` into
`Titanfall2/R2Northstar/mods/`, enable it and restart. Server and clients need
the same version. Launch with `map mp_arena_composite`.

Supports Skirmish, Pilots vs Pilots and Free For All. Opposing teams have native
team starts. Intro and evac are disabled; other modes lack full objectives or
AI navigation. `composite_where` prints your position.

Restores missing equipment supports and stacked tank containers, removes the
orphan light and rebakes control-entrance wall panels. Source collision remains
unchanged. Includes the prior banner supports, screens, loading art, safety
volumes, native character lighting and source zipline pairs.

See `local-repairs-2026-10-07.md`, `MISSING_CONTENT.md` and `CONVERSION.md` for
capacity, omissions and reproduction. Original assets remain the work of their
respective creators.
''',encoding='utf-8')
 p=DOC/'CONVERSION.md';s=p.read_text(encoding='utf-8').replace('preview 0.5.0','preview 0.6.0').replace('941,236 serialized triangles (108 disabled spawn-cover\nslots) and 4,261 static placements','942,146 serialized triangles (108 disabled spawn-cover\nslots and 24 orphan lamp slots) and 4,264 static placements').replace('Charts have four texels per triangle.','Most charts have four texels per triangle; 2,250 control-entrance wall\ntriangles use 16x16 or 32x32 charts.')
 s=s.split('\n## Local source attachments and chart allocation in 0.6.0')[0]+'''
## Local source attachments and chart allocation in 0.6.0

`repair_composite_local.py` restores four source objects, suppresses one orphan
lamp and repairs chart gutters. Native fullbright distinguishes material faults
from lighting faults; sparse vertex-edge ray samples explain the triangular
wall artifacts. High-resolution receivers use spare atlas rectangles, with
inset raster samples and gutters confined to their own charts. Split native
mesh/material-sort groups by atlas page; changing vertex UVs alone binds the
wrong page. Repartition indices with native odd-triangle pair padding, rebuild
conservative visibility/bounds and audit both index and batch limits.

Check atlas rectangle reservations before appending receivers. Collider source
ownership can reside in world BVH rather than the omitted static-prop table;
compare actual triangle bounds and native rays before adding duplicate hulls.
See `local-repairs-2026-10-07.md` for exact scope and retained evidence.
''';p.write_text(s,encoding='utf-8')
 shutil.copy2(OUT/'source-build.json',MOD/'build-status.json');shutil.copy2(DOC/'README.md',MOD/'README.md');shutil.copytree(DOC,MOD/'docs',dirs_exist_ok=True)
 records={p.relative_to(MOD).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(MOD.rglob('*')) if p.is_file() and p.name!='checksums.json'};(MOD/'checksums.json').write_text(json.dumps(records,indent=2))
 print('Recorded verified 0.6.0 source repairs and runtime evidence',flush=True)
if __name__=='__main__':write()
