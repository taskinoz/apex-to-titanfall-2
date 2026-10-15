# Party Crasher 0.5.1

Fixes flat grey and olive ground: 13 world-projected source materials (rubble, moss, snow, gravel, grunge) now tile at their Apex scale instead of once per unit. Removes the z-fighting white rubble overlay on floors and grass: it now blends with the original Apex coverage, and fully transparent parts are no longer drawn. Includes the 0.5.0 signs, banners and screen panels. Uses 97.93% of native world index capacity. Many source props (cafe furniture, planters, trees, window modules, rocks) remain omitted for the draw budget. AI navigation and Titan modes are not supplied. Restart between previews.

## Causes

- Apex wld pixel shaders project albedo from world position, uv = (x, -y) . c_uvN. The converted meshes stored raw world coordinates as UVs, so the texture repeated every unit and averaged to a flat colour. `classify_world_uv.py` traces each source pixel shader to find the c_uvN slot feeding the albedo.
- The b2t overlay opacity is (1 - saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)) * albedo.a. The real vertex colour is the record field bsp_tool names `negative_one`; its `colour` field is packed tangent data. Coverage is baked per triangle into an atlas drawn with the native world alpha shader.

The independent audit passed 2,279 checks: collision, lightmaps, entities, lights and probes are byte-identical and every non-overlay mesh keeps identical triangles. Native tests verified clear supported team spawns, all 69 safety triggers, postmatch return, stock Coliseum loading and Party Crasher reloading. Fourteen user-reported views were captured in R5R and Northstar from the exact mounted payload.

Baseline rollback is retained on the build drive under `party-crasher/before-0.5.1/`.

Reproduce with `classify_world_uv.py party-crasher`, `repair_party_surfaces.py patch`, `materials`, `verify_party_surfaces.py`, `repair_party_surfaces.py stage`, the `party-crasher-user-report` routes and `verify_party_structure_runtime.py surface-repair`.
