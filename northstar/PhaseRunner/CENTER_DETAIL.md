> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Center props and Nessie — 0.1.41

The user confirmed 0.1.40 is solid with no pop-in or pop-out. This prop pass
retains its material/channel mesh ordering and its full playable-camera guards.
It does not add connected portals or change the underlying skybox/cell records.

The original Apex static placement table contains three closed police trucks
that earlier staging skipped because Legion did not generate valid staged QC
files. Their recovered RMDL/VG geometry is valid. Restore placements 16849,
16850 and 16856 at their exact translated positions, angles and scales. The
central trucks use unsimplified authored LOD2, 1,916 triangles each. The truck
under Nessie uses full LOD0, 10,401 triangles, including its hood and windows.
The native opaque world shader approximates the truck's glass; there is no
new vehicle interaction or glass transparency. Two center trucks are at
(-1161.8, -406.6, -1344) and (1360, -448, -1344).

Nessie placement 7806 remains at (2914.6992, 902, -1074.62), scale 1.5, with
its original rotation and skin. Replace exactly its 59 simplified LOD2 faces
with the original 1,442-triangle LOD0. Retain authored smooth corner normals,
diffuse UVs and recovered normal/gloss/specular channels. Its missing support
is truck 16850 at (3020, 846.5996, -1151.97). Restoring that truck's LOD0 hood
brings the sampled foot-to-hood gaps to approximately -2.90 through 3.72 units,
instead of 12 through 47 units with its distant LOD2. Preserve the authored
placement rather than lowering the doll onto unrelated terrain.

Restore 206 previously omitted small rock clusters around the map center and
within 1,200 horizontal units of Nessie. They use their original authored LOD3
without further simplification. They keep their original non-solid settings;
the existing colliding rocks remain unchanged. Unstaged signs, utility props,
foliage and animated entities are still outside this release's scope.

All unrelated rendered triangles retain exactly their vertex attributes,
bindings and lightmap coordinates. Original sky/sun/local lightmaps and the
player's directional lighting probes remain intact. Added props receive a
separate baked atlas against the retained geometry and current 30 local lights.
New shadow geometry matches the new props. Existing surface/probe lighting is
not rebaked for the added occluders. The three truck materials have all four
recovered PBR channels and validated native material-v12 dependencies. Their
resident texture GUIDs are appended to the existing native STBSP catalog;
existing coverage columns remain byte-identical.

Truck collision uses original checksum-verified IRPS convex pieces with pilot
sweep bevels. All original collider records and the exact original active
shape set are retained; only truck hulls are appended. One old Nessie test's
start was inside the newly restored truck. Move only that diagnostic start
above its retained target. Existing map and tunnel checks must still pass.

Preservation, source-detail, UV/normal/tangent, physics, visibility and native
capacity checks are recorded in test_center_detail.py and runtime-validation.json.
The new all-visible index total remains below 90 percent of the native limit,
with fewer than 512 static draw batches against a capacity of 2,048. The final
GPU appearance and frame rate require a client check.

Full prior snapshot: output/installed-backups/PhaseRunner.Preview-0.1.40-before-center-detail.
The confirmed 0.1.40 archive and older original-path backup are retained.
