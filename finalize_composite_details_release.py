"""Document the measured 0.4.0 source-detail recovery without rebaking old data."""
import json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output/composite';WORK=OUT/'detail-recovery';DOC=ROOT/'docs/composite';MOD=ROOT/'northstar/ArenaComposite'

def write():
    from finalize_composite_release import document,digest
    from audit_world_draw_budget import audit
    document();scene=json.loads((OUT/'scene.json').read_text());recovery=json.loads((WORK/'result.json').read_text());runtime=json.loads((WORK/'runtime.json').read_text());budget=audit(OUT/'mp_arena_composite.bsp')
    proof=dict(version='0.4.0',final_client_verified=True,conversion_tests=23,
               harness_tests=7,harness_tests_note='Harness unchanged; previous seven harness checks passed.',
               native_repair_evidence='output/composite/detail-recovery/runtime.json',
               source_detail_recovery='output/composite/detail-recovery/result.json',
               draw_budget=budget,runtime=runtime,
               remaining=['2,098 locally selected source placements remain budget-excluded; 147 placements lack recovered assets.',
                          'Building signage decal still lacks its source texture (564 triangles); one empty-model triangle also uses fallback.',
                          'Single-client checks do not establish multiplayer frame times or original post-match crash cause.'])
    (DOC/'validation.json').write_text(json.dumps(proof,indent=2))
    b=json.loads((OUT/'source-build.json').read_text())
    b.update(version='0.4.0',client_verified=True,validation=proof,render_triangles=scene['triangles'],
             active_render_triangles=scene['triangles']-108,source_props=scene['props'],missing_props=len(scene['omitted']),draw_budget=budget,
             collision={k:v for k,v in json.loads((OUT/'physics.json').read_text()).items() if k not in ('owners','missing')},
             detail_recovery=recovery,repair_record='docs/composite/detail-recovery-2026-10-07.md',
             validation_evidence=['output/composite/detail-recovery/runtime.json','logs/composite-detail-recovery-tests.log'])
    b['build']['compact_bytes']=(OUT/'mp_arena_composite.bsp').stat().st_size;b['build']['checks']['bytes']=b['build']['compact_bytes'];b['build']['checks']['in_game_verified']=True;b['streaming_sidecar']['client_load_verified']=True
    tmp=OUT/'source-build.details.json';tmp.write_text(json.dumps(b,indent=2));os.replace(tmp,OUT/'source-build.json')
    (ROOT/'logs/composite-detail-recovery-tests.log').write_text('python -m unittest test_composite_port test_arena_boundaries test_composite_detail_recovery\n23 tests passed in 6.845 seconds.\n')
    text='''# Drop-Off 0.4.0 — source props and zipline supports

Recovered 95 placements, increasing the port from 4,123 to 4,218 static objects.
Both source zipline pairs retain their endpoints and now have all four arms and
four supporting posts at their original source transforms. The four arms use
the earlier single-material SMD/QC export; the other additions use compiled VG
author LODs. No placements or old geometry were removed to make this space.

## Added content

| Model | Placements |
| --- | ---: |
'''
    from collections import Counter
    text+='\n'.join(f'| `{name}` | {count} |' for name,count in Counter(Path(p['model']).stem for p in recovery['placements']).items())
    text+='''

Every added material has source albedo available. New source albedo, normal,
gloss and specular channels are bound where exported. All textures remain
resident with the existing 1024-pixel cap; the RPak grows by about 13 MB.
The zipline-arm albedo is very dark in the source export (mean RGB about
24/20/18), explaining its dark metal appearance in native captures.

## Budget and rendering

Added 35,986 triangles. Serialized draw occupancy is 935,974 triangles, including
108 disabled start-cover slots. Native padded index use is 2,811,912 of 3,145,728
(89.4% occupied; 10.6% free). There are 333 static material-batch runs, below the
512-run project policy and the audited 2,048 native capacity. Dynamic lighting
can split batches, so these are capacity checks rather than a frame-time claim.
Only about 6,400 more triangles fit before this build's conservative 90% index
policy. Larger recovery should reduce existing geometry or use a tested native
static-model path; simply filling the hard limit risks renewed missing visuals.

## Collision and lighting

Recovered IRPS/BVH polygon surfaces are transformed with each added prop.
The arm export has no compiled collider, so it uses its exact source mesh
triangles as surface collision. This is a documented approximation and does
not introduce box-shaped obstacles. All old collision headers, triangles and
nodes retain their bytes and offsets; only additional streams and the spatial
grid change. One support trace begins inside nearby existing wall collision;
other support checks begin clear and register collision.

New 4x4 triangle charts use unused tiles in the fourth existing lightmap page.
They are ray-baked against the old scene and new objects, omitting temporary
spawn barriers as casters. Every previously used lightmap tile and all character
probes remain byte-identical. New opaque geometry enters the native shadow
mesh stream; the existing baked scene does not gain new static contact shadows
until a future full rebake.

## Verification and remaining work

All 23 regression checks passed, including exact source attachment transforms,
old collision/draw stream preservation, original lightmap tile preservation,
native buffer capacity, material dependencies and source safety entities.
Native close views cover both ends of both ropes plus the court and interior.
Runtime receipts and reload/end-state results are in
`output/composite/detail-recovery/runtime.json`.

The complete omission inventory still lists 2,098 local budget omissions,
147 placements without recovered assets, 1,884 remote/menu/backdrop placements,
one deliberately removed detached shield and eight filtered decorative objects.
The `signage_building_02` source decal remains unrecovered (564 triangles);
`empty_model` accounts for one other fallback triangle. Three catalogue fallback
names have zero rendered triangles. No unrelated atlas is substituted.

Reproduction: `recover_composite_details.py plan`, then `materials`, then
`append`; the materials step takes a mandatory snapshot and detaches files
before tools overwrite them. Restore the snapshot before reapplying. The native
verification script is `verify_composite_details_runtime.py`. Scene and physics
caches record additions for future conversion tools. 0.3.0 remains packaged
separately and installed runtime files are backed up before replacement.
'''
    (DOC/'detail-recovery-2026-10-07.md').write_text(text,encoding='utf-8')
    (DOC/'README.md').write_text('''# Drop-Off 0.4.0 for Northstar

Port of Apex map `mp_rr_arena_composite`. Extract `ArenaComposite` into
`Titanfall2/R2Northstar/mods/`, enable it and restart. Both server and clients
need the same version. Launch with `map mp_arena_composite`.

The preview supports Skirmish, Pilots vs Pilots and Free For All. Opposing
teams have native team starts. Intro and evac are disabled; other modes lack
complete objectives or AI navigation. `composite_where` prints your position.

Includes 4,218 static placements, source collision, coarse baked lighting,
character probes and source loading artwork. This update restores 95 objects,
including four zipline arms and their posts, with source textures and new
lighting charts. Temporary spawn covers stay removed and intentional room
boundaries stay closed. Phase Runner is unchanged.

See `detail-recovery-2026-10-07.md` for measured capacity and verification,
`MISSING_CONTENT.md` for omissions, and `CONVERSION.md` for the workflow.
Player downloads contain runtime files, a short README and a game screenshot.
Original assets remain the work of their respective creators.
''',encoding='utf-8')
    path=DOC/'CONVERSION.md';r=path.read_text(encoding='utf-8').split('\n## Incremental source-detail recovery in 0.4.0')[0];r+='\n## Incremental source-detail recovery in 0.4.0\n\n`recover_composite_details.py` appends stable draw/collision streams, source\nmaterial bindings and new lighting charts in unused texels. See\n`detail-recovery-2026-10-07.md` for relocation rules and budget policy.\n';path.write_text(r,encoding='utf-8')
    scene['source_lod_policy']='Baseline author LOD scene plus 35,986 recovered triangles; tested below 90% native world-index capacity'
    (OUT/'scene.json').write_text(json.dumps(scene,indent=2))
    shutil.copy2(OUT/'source-build.json',MOD/'build-status.json');shutil.copy2(DOC/'README.md',MOD/'README.md');shutil.copytree(DOC,MOD/'docs',dirs_exist_ok=True)
    records={p.relative_to(MOD).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(MOD.rglob('*')) if p.is_file() and p.name!='checksums.json'}
    (MOD/'checksums.json').write_text(json.dumps(records,indent=2))
    print('Recorded 0.4.0 recovery, source inventory, runtime evidence and checksums.')

if __name__=='__main__':write()
