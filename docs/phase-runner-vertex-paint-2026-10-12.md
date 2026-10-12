# Phase Runner 1.3.0 — source vertex paint

The paired R5R views identified pale painted props. The static VG reader skipped
the source four-byte RGBA field; the world builder then wrote white. The stock
placeholder world shader also ignored COLOR, so restoring bytes alone did not
change the native image.

This repair restores RGB on 66,208 existing vertices matched by
material, position, normal and UV. Ambiguous source keys are omitted. Source
alpha is shader/layer data; native opaque alpha is retained. Five binary/matching
checks and two preservation/dependency checks pass.

Native Homestead shader sets 0x6AFE220DA02633A0 and 0x81F5BAC39D4DF3B1 are copied
with unchanged bytecode and input-layout flags. Their vertex program gamma-decodes
COLOR before albedo modulation. Existing opaque depth/blend states and PBR
channels remain. Source textures are copied as resident assets into the paint
pack; native fallback channels continue to reference the already loaded native
packs. Both paint packs attach to mp_coliseum.rpak for stable native lifetime.
The additional pack is 25,768,814 bytes; this is a residency cost,
not a claim of improved frame rate.

No triangles, colliders, portals, UVs, lightmap tiles or gameplay entities are
added or removed. Every unrelated lump is byte-checked, and all-visible index
and static batch counts are unchanged. The game-lump directory's absolute
pointers move during compaction; its payload is preserved.

3 fresh Northstar views are paired with hash-verified original R5R captures
at identical route cameras. Baseline and repaired captures are retained in
site/dist/. Source-to-port offset: [26000, 19000, 0]. The source geometry still has more
scenery than the budgeted port. Terrain layer/vertex-alpha shaders, animated
banner artwork and other documented omissions are future work.

Reproduce on an unmodified baseline with recover_vertex_paint.py phase-runner, then
stage_vertex_paint_shader.py phase-runner. These are guarded one-shot repairs.
Rollback snapshot: output/repair-backups/20261012-vertex-paint/PhaseRunner.
Comparison input: r5-harness/output/phase-runner-paint/comparison.json.
