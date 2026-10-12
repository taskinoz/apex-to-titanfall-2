# Retained prototype scripts

Historical scripts are reference implementations. They include superseded experiments; consult the guide and current release builder before running them. Filenames alone do not establish a supported conversion stage.

| File | Opening description |
|---|---|
| `add_preview_sky.py` | Replace failed sky portals with a diagnostic dome using the recovered sky image.  The original vista model is not converted yet. A sphere-map projection is an |
| `add_prop_runtime_probes.py` | from pathlib import Path p=Path('package_northstar.py');s=p.read_text();needle="    (scripts/'_phase_runner_preview.nut').write_text(" insert='''    if status.get('prop_physics'): |
| `add_tunnel_floor_sweeps.py` | Generate engine floor-following sweeps across every authored tunnel ring. import json import numpy as np |
| `add_tunnel_step_walks.py` | Test normal player step-height movement through each reported obstruction. import json from pathlib import Path |
| `add_walkway_route_tests.py` | Add grounded traversal and floor contacts along both new pipe walkways. import json from pathlib import Path |
| `append_prop_geometry.py` | Add staged architectural meshes to the TF2 preview without changing physics. import json import math |
| `apply_baked_lighting.py` | Encode native directional lightmaps and repair tangent frames for the arena.  The shipped uberSamp2222_wld_ps shader establishes these layouts: |
| `apply_interior_lighting.py` | Add baked local-light visibility and reduce native shadow draw calls. import json,struct,shutil,hashlib from repair_environment_lighting import ROOT,np,WorldLightv3,OUT |
| `apply_world_materials.py` | Regroup the preview's world triangles by their original Apex OBJ materials. import collections import json |
| `audit_all_collision.py` | Audit every existing brush and every rendered solid source-model placement. import collections,json,struct from pathlib import Path |
| `audit_available_model_lods.py` | Read-only audit of recovered compiled Apex LOD triangle counts. import collections,json,struct from pathlib import Path |
| `audit_character_light_indices.py` | Compare shipped probe links with native light positions and radii. import json,struct from audit_character_lighting import PATHS,ROOT |
| `audit_character_lighting.py` | Inspect native model lighting records without changing any BSP. import json,struct from pathlib import Path |
| `audit_client_loading_art.py` | Read-only native lightmap and asset-package comparisons for the load hang. import json,struct from pathlib import Path |
| `audit_collision_capacity.py` | Find redundant world brushes wholly enclosed by existing rock hulls. import json,struct from pathlib import Path |
| `audit_compatibility.py` | Compare actual source/target map records without writing a converted BSP. import argparse import collections |
| `audit_coordinate_rendering.py` | Locate render meshes at reported positions without changing their draw state. import json,struct from pathlib import Path |
| `audit_entity_props.py` | Inventory render props from Apex BSP entities and entity partitions. import collections,json,re from pathlib import Path |
| `audit_environment_ground.py` | Inspect nearby upward-facing lightmap receivers at reported gameplay locations. import json from repair_environment_lighting import ROOT,OUT,BAKE,np |
| `audit_exported_assets.py` | Check recovered meshes and QC references against map dependencies. import argparse import json |
| `audit_full_collision_sources.py` | Check every installed source-model collider against its recovered physics. import json,struct,collections from pathlib import Path |
| `audit_menu_lighting.py` | Read-only comparison of native MP menu stages, world lights and shadow sets. import sys,json,struct,re,collections from pathlib import Path |
| `audit_model_transforms.py` | Report Apex inline model placement and source vertex bounds. import json import sys |
| `audit_native_tunnel_contacts.py` | Match native sweep contact positions to original owned source surfaces. import json,re,struct,collections import numpy as np |
| `audit_phy_counts.py` | import json,collections,struct from pathlib import Path from read_prop_physics import read_phy |
| `audit_portal_clearance.py` | from pathlib import Path import json,struct,itertools from stage_prop_geometry import rotation,transform |
| `audit_portal_physics.py` | from read_prop_physics import read_bvh,plane from pathlib import Path import math |
| `audit_preview_alignment.py` | Inspect placement, fallback materials and lighting without changing the map. import collections,json,struct from pathlib import Path |
| `audit_preview_bounds.py` | Check actual world vertex positions against every existing mesh bound. import json,struct from pathlib import Path |
| `audit_preview_material_bindings.py` | Check active BSP material names against packaged native RPak material headers. import json,struct from pathlib import Path |
| `audit_probe_occupancy.py` | import struct,json from pathlib import Path base=Path('output/phase-runner/preview-prop-physics');d=(base/'mp_phase_runner_preview.bsp').read_bytes() |
| `audit_prop_collision_targets.py` | import json,struct,collections from pathlib import Path p=Path('output/phase-runner/preview-draw-restored/mp_phase_runner_preview.bsp');d=p.read_bytes() |
| `audit_remaining_props_and_materials.py` | import collections,json,struct,sys from pathlib import Path ROOT=Path(__file__).resolve().parent |
| `audit_remaining_recovery_budget.py` | Read-only remaining-placement/compiled-LOD audit for the installed 0.1.44 map. import json import struct |
| `audit_reported_art.py` | Trace the five reported art problems to source placements and draw surfaces. import json,struct,sys,collections from pathlib import Path |
| `audit_reported_locations.py` | Compare user-reported obstructions with actual collision and native bounds. import json,struct from pathlib import Path |
| `audit_reported_tunnel_barriers.py` | Read-only ownership audit for the user's nine blocked tunnel positions. import collections,json from pathlib import Path |
| `audit_tree_grounding.py` | Audit fir roots against rendered terrain without mistaking their own collider for ground. import json,sys from pathlib import Path |
| `audit_tunnel_surface_materials.py` | Associate recovered Apex surface properties with the native world triangles. import collections,json import numpy as np |
| `audit_user_coordinates.py` | Identify exact source placements at the six reported problem locations. import json,struct from pathlib import Path |
| `audit_world_collision_contents.py` | Recover per-triangle source contents and identify falsely solid tunnel volumes. import collections,json,struct from pathlib import Path |
| `audit_world_draw_budget.py` | Audit native index-copy and static draw-batch limits without binary changes.  engine.dll+0xb72af compares the next index total with 0x300000 and branches |
| `bake_terrain_transitions.py` | Bake a preview seam blend from recovered albedos and layer masks.  This is an opaque approximation, not a reconstruction of Apex's layer shader. |
| `build_art_supports.py` | Restore omitted cargo/fence supports and repair pipe LODs and alpha road decals. import collections,io,json,os,re,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_budget_preview.py` | Budget-safe render diagnostic: source LODs, exact original world and physics. import collections,hashlib,json,math,shutil,struct,time,re from pathlib import Path |
| `build_center_detail.py` | Restore source center props and authored Nessie LOD0 over confirmed 0.1.40. import collections,json,os,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_character_lighting.py` | Add only native moving-model probes, their KD tree and parent range. import itertools,json,math,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_glass_console.py` | Rebind only recovered glass faces over the confirmed 0.1.41 scene. import collections,json,os,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_phase_runner_catwalks.py` | Replace only the two prototype paths with lit, colliding industrial catwalks. import collections,json,math,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_phase_runner_firs.py` | Stage twenty full-size authored firs over the working 0.1.44, with native cutout leaves. import collections,io,json,os,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_phase_runner_presentation.py` | Native loading material, lobby atlas and localized Phase Runner map tokens. import json,shutil,struct,subprocess,sys,hashlib from pathlib import Path |
| `build_phase_runner_release.py` | Rebuild the twenty fir additions with measured root corrections, then stage 1.0.0. import copy,json,sys from pathlib import Path |
| `build_phase_runner_trees.py` | Stage twenty authored acacias over the working 0.1.44, with native cutout leaves. import collections,io,json,os,shutil,struct,subprocess,sys,time from pathlib import Path |
| `build_preview_source.py` | Create an explicitly incomplete Phase Runner geometry preview for MRVN-Radiant.  OBJ coordinates/winding compensate for the compiler's Assimp import transform. |
| `build_preview_stbsp.py` | Write a native v8.0 STBSP catalog for the preview's resident RPak assets.  Empty coverage columns use the native Coliseum empty-column encoding. This is |
| `build_triangle_collision_lab.py` | Create collision-only native triangle fixtures without replacing the user map. import json,shutil,struct import numpy as np |
| `build_triangle_edges_lab.py` | Compare native player sweeps with independent triangle/AABB SAT at edges. import json import numpy as np |
| `build_tunnel_walkways.py` | Add visible, gently connected player floors along the authored pipe route. import json,math,shutil,struct import numpy as np |
| `compact_preview_bsp.py` | Compact active BSP lumps and relocate absolute game-lump directory offsets. import hashlib,json,shutil,struct from pathlib import Path |
| `conservative_preview_draw.py` | Use map-wide draw bounds while investigating preview GPU culling. import json,math,shutil,struct from pathlib import Path |
| `decode_collision.py` | Recover regular world BVH polygons for inspection, not a playable TF2 map.  Leaf layouts follow r-ex/rsx's published bvh decoder. Map nodes use the |
| `decode_inline_world_collision.py` | Recover the eight inline world convex leaves using the published RSX layout. import struct from pathlib import Path |
| `decompress_rpak.py` | Make an uncompressed v8 RPak copy for extractors without ZSTD support. import argparse import hashlib |
| `document_conversion_release.py` | Generate exhaustive release inventories, actual binary layouts and measured capacities. import collections,csv,hashlib,json,re,struct,sys,shutil from pathlib import Path |
| `document_preview_020.py` | from pathlib import Path import json p=Path('README.md');s=p.read_text();addition=''' |
| `expand_preview_collision.py` | Build bounded native TF2 brush collision for recovered support surfaces.  All nondegenerate merged regular floors/ramps are retained. Remaining capacity |
| `export_geometry.py` | Recover Apex brush geometry for inspection; this does not create a TF2 map. import argparse import json |
| `extend_prop_collision.py` | Add native prop brushes without removing existing world collision. import collections,itertools,json,math,mmap,shutil,struct from pathlib import Path |
| `extend_structure_collision.py` | Reclaim provably redundant box solids, then add original structural physics. import collections,json,math,shutil,struct from pathlib import Path |
| `extract_map.py` | Extract Respawn client VPKs using bsp_tool and r5vpk's LZHAM DLL. import argparse import ctypes as c |
| `extract_native_material.py` | Read an unpatched native v7 RPak and stage a material for RePak.  Header layouts follow RSX's cpakfile.h and material.h. The original game file |
| `extract_world_glass_shader.py` | Preserve native TF2 shader bytecode and input flags in RePak's MSW format. import struct from pathlib import Path |
| `finalize_art_supports.py` | Verify, preserve the full 0.1.42 snapshot, install and archive 0.1.43. import collections,hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_art_supports_loading.py` | Promote the shader repair only after actual client loading and reload pass. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_camera_visibility_release.py` | Record fresh server checks and install the conservative visibility diagnostic. import hashlib, json, re, shutil, zipfile from pathlib import Path |
| `finalize_catwalk_release.py` | Install the validated renamed release and preserve the complete prior mod. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_center_detail.py` | Install the verified prop pass with an immutable verified prior snapshot. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_character_lighting.py` | Install the tested character-lighting-only release with a full rollback. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_draw_budget_release.py` | Verify fresh evidence, install the budget-safe diagnostic and archive it. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_environment_release.py` | Install only the tested native lighting candidate and archive verified copies. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_full_collision_release.py` | Verify the 0.1.27 collision evidence, installation and distributable archive. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_glass_console.py` | Verify, snapshot, install and archive the 0.1.42 candidate. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_interior_release.py` | Install the validated interior-lighting and balanced-material candidate. import json,re,shutil,zipfile,hashlib from pathlib import Path |
| `finalize_lighting_release.py` | Install the tested lighting-only candidate and retain the playable rollback. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_local_visibility_release.py` | Install only the hash-verified native visibility candidate and retain rollback. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_material_release.py` | Install the verified lighting/material candidate and preserve both rollbacks. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_phase_runner_firs.py` | Back up 0.1.45 and promote the fir correction after regression/client checks. import collections,hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_phase_runner_release.py` | Verify native evidence, preserve the prior install, package and install the release. import hashlib,json,os,re,shutil,subprocess,zipfile from pathlib import Path |
| `finalize_phase_runner_trees.py` | Back up 0.1.44 and promote the tree pass only after regression and client checks. import collections,hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_playable_visibility.py` | Install the validated visibility-only release with a verified rollback. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `finalize_portalfree_release.py` | Verify and install the portal-free candidate; retain the confirmed rollback. import hashlib,json,re,shutil,struct,zipfile from pathlib import Path |
| `finalize_textured_preview.py` | Record textured preview test results and verify the installed package. import hashlib import json |
| `finalize_tunnel_release.py` | Verify final tunnel evidence, install the mod and hash-check its archive. import hashlib,json,re,shutil,zipfile from pathlib import Path |
| `finalize_world_batch_order.py` | Verify and install exact draw ordering with full prior backup and archive. import hashlib,json,os,re,shutil,zipfile from pathlib import Path |
| `fix_spatial_material_sharing.py` | from pathlib import Path p=Path('spatial_preview_meshes.py');s=p.read_text().replace("struct.pack_into('<H',mesh,22,len(sorts)//12)","struct.pack_into('<H',mesh,22,si)") s=s.replac |
| `guard_native_sort_capacity.py` | from pathlib import Path p=Path('package_northstar.py');s=p.read_text();needle="    sets=lumps.get(0x57,(0,0,0))[1]//8" s=s.replace(needle,"    # Engine loader uses a fixed 1024-by |
| `inspect_center_contact.py` | import json,re,sys from pathlib import Path ROOT=Path(__file__).resolve().parent |
| `inspect_center_detail.py` | import json,collections,sys from pathlib import Path ROOT=Path(__file__).resolve().parent |
| `inspect_character_native.py` | import json,struct from pathlib import Path import pefile |
| `inspect_console_uvs.py` | import json,struct,sys,collections from pathlib import Path ROOT=Path(__file__).resolve().parent |
| `inspect_draw_metadata.py` | Inspect native directional metadata and rendered mesh bounds. import collections,json,struct from pathlib import Path |
| `inspect_full_collision_contact.py` | Identify exact source shapes touching a reported player-hull position. import json,struct import numpy as np |
| `inspect_maps.py` | Inventory Respawn map inputs without modifying game files. import argparse import json |
| `inspect_missing_models.py` | import json,struct,collections,sys from pathlib import Path ROOT=Path(__file__).resolve().parent |
| `inspect_native_draw_reader.py` | Read-only native draw metadata references; never modifies game binaries. import argparse,bisect,struct from pathlib import Path |
| `inspect_native_pointer_users.py` | Read-only RIP-relative users in a bounded native data-address range. import bisect,sys from pathlib import Path |
| `inspect_native_range.py` | Read-only bounded disassembly of the installed native engine. import sys from pathlib import Path |
| `inspect_native_tricoll.py` | Inspect native triangle-tree layouts and per-triangle orientation flags. import collections,json,struct import numpy as np |
| `inspect_pvs_code.py` | Read-only executable references for native PVS diagnostics. import struct from pathlib import Path |
| `inspect_repaired_tunnel_contact.py` | Inspect only active native shapes, including appended aperture triangles. import json,struct import numpy as np |
| `inspect_static_props.py` | Inventory missing static props and the recovered meshes available to restore them. import collections import json |
| `make_rtech_decoder.py` | Stage a small AGPLv3 RPak decoder from the checked-out RSX source.  Only the upstream RTech decoder and its lookup tables are compiled; the original |
| `merge_collision.py` | Merge adjacent coplanar collision polygons without filling gaps or concavities. from pathlib import Path from build_preview_source import cross, subtract, TRANSLATION |
| `native_preview_cells.py` | Generate conservative TF2 cells and open portals, independently of Apex VIS.  Record layouts and the roots-first AABB forest follow native Homestead/Colony. |
| `native_triangle_collision.py` | Experimental native TF2 triangle collision; validate in an isolated lab first. import math,struct import numpy as np |
| `optimize_portalfree_render.py` | Exact render sharing and local PVS safety on the confirmed portal-free build.  All collision and normal/position buffers stay byte-identical. Re-indexing |
| `optimize_preview_textures.py` | Deduplicate identical channels and add native mip chains in a separate RPak project. import json,struct,hashlib,shutil,subprocess,math,concurrent.futures,collections,time from path |
| `pack_preview_vertices.py` | Share exact vertices using native local indices, preserving all drawn corners. import collections,json,mmap,shutil,struct,time,math from pathlib import Path |
| `package_character_lighting.py` | Stage only the character-lighting BSP over the complete 0.1.37 package. import json,os,shutil from build_character_lighting import ROOT,SOURCE,TARGET,OUT |
| `package_northstar.py` | Validate and package a compiled diagnostic map as a Northstar mod. import argparse import hashlib |
| `package_phase_runner_release.py` | Package the renamed map and append targeted native catwalk movement checks. import json,shutil,struct,sys from pathlib import Path |
| `plan_budget_model_geometry.py` | Measure original model LODs with component-preserving local simplification. import ctypes,collections,json,os from pathlib import Path |
| `plan_coordinate_collision.py` | Plan source-physics coverage at reported gaps before allocating native brushes. import collections,json,struct from pathlib import Path |
| `plan_render_lod_budget.py` | Estimate a full-placement lower-detail diagnostic from original Apex LODs. import collections,json,struct from pathlib import Path |
| `prepare_dev_materials.py` | Recover missing source texture channels without rebuilding existing materials. import json, shutil, struct, collections from pathlib import Path |
| `prepare_environment_bake.py` | Exclude only the photo sky dome, retaining the confirmed atlas and face IDs. import json,struct,hashlib from prepare_lighting_scene import ROOT,SOURCE,OUT,np |
| `prepare_full_collision_probes.py` | Retain clear-start engine contacts and add reported pipe-floor checks. import json,re,struct import numpy as np |
| `prepare_interior_lights.py` | Recover building fixture positions and space low-cost lights along both tunnels. import json,struct from repair_environment_lighting import ROOT,np |
| `prepare_lighting_scene.py` | Unwrap the confirmed playable map without changing its draw or collision data.  Run with the bundled Python and workspace tools/lighting-python dependencies. |
| `prepare_model_sources.py` | Stage recovered map meshes and repair unambiguous exported QC references.  These are source assets for conversion, not compiled Titanfall 2 models. |
| `prepare_portal_collision.py` | from read_prop_physics import read_bvh from merge_collision import merge from pathlib import Path |
| `prepare_tunnel_sweep_lab.py` | Run player hull sweeps through reported openings in the isolated profile. import json,shutil from pathlib import Path |
| `prepare_world_materials.py` | Stage recovered Apex DDS images with native TF2 world material templates. import collections import json |
| `preview_visibility.py` | Build and validate a native TF2 visibility tree with spatially bounded leaves. import math,struct  |
| `read_prop_physics.py` | Read Season 3 model physics using the checked RSX IRPS/BVH layouts. import math,struct,collections from pathlib import Path |
| `read_vg_static.py` | Decode static Season 3 VG geometry, using Legion's documented packed layout. import math import struct |
| `rebuild_complete_collision.py` | Rebuild world/player collision and every rendered solid model from source physics.  Closed IRPS pieces retain convex brushes. Concave BVH rocks and tunnels use |
| `rebuild_local_visibility.py` | Native open TF2 cells with camera-safe local geometry and conservative portals.  No Apex occlusion, draw geometry, lights or collider data are reused or edited. |
| `record_clear_hull_evidence.py` | from pathlib import Path p=Path('finalize_textured_preview.py');s=p.read_text();s=s.replace("        evidence['prop_hull_hits']=count","        prop_results=re.findall(r'Phase Runn |
| `record_runtime_validation.py` | Record scoped engine load/probe evidence without packaging raw logs. import argparse import hashlib |
| `recover_model_slots.py` | Read validated Season 3 RMDL mesh slots instead of trusting SMD labels. import re import struct |
| `remove_legacy_sky.py` | Remove the obsolete 3D sky camera, keeping the recovered world sky dome. import json import re |
| `repair_art_supports_loading.py` | Embed a uniquely identified decal shader to remove a sibling-pak dependency. import json,os,shutil,struct,subprocess,sys from pathlib import Path |
| `repair_camera_visibility.py` | Build a conservative camera-access-path diagnostic without changing draw bounds.  Titanfall's client PvsCullAccessPath clips CELL_AABB_NODES and OBJ_REF_BOUNDS |
| `repair_coordinate_collision.py` | Restore original container/stair physics and reported tunnel surface gaps. import collections,json,shutil,struct,time from pathlib import Path |
| `repair_dev_materials.py` | Replace only proven fallback faces; preserve vertices, lightmaps and physics. import sys,json,struct,collections,shutil from pathlib import Path |
| `repair_draw_regression.py` | Undo 0.1.18 draw experiments while retaining the recovered map content. import hashlib,json,mmap,shutil,struct from pathlib import Path |
| `repair_environment_lighting.py` | Replace lighting only: correct sky occlusion and separate the native menu stage. import json,struct,shutil,math,hashlib from apply_baked_lighting import ROOT,OUT,np,encode_rgbm,dis |
| `repair_ground_layers.py` | Remove unsupported transparent terrain overlays and identical render copies.  The preview uses opaque TF2 materials. Apex terrain overlays need blend shaders |
| `repair_native_render_partitions.py` | Sort within native opaque / transparent world ranges, preserving geometry. import struct from audit_world_draw_budget import static_draw_key |
| `repair_playable_visibility.py` | Visibility-only recovery over the client-confirmed character lighting build. import json, os, shutil, struct from pathlib import Path |
| `repair_portal_surfaces.py` | Replace identified tunnel surfaces and restore newly recovered moss meshes. import collections import json |
| `repair_preview_hull_edges.py` | Add native AABB sweep bevels to existing convex collision, keeping its volume. import itertools,json,math,struct,time from pathlib import Path |
| `repair_preview_index_padding.py` | Repair native pairwise triangle reads and withdraw the 0.1.21 cell experiment.  The client dump at engine+0xae8d3 reads the next mesh's first triangle when |
| `repair_preview_lighting.py` | Replace unrelated prototype lights with recovered Phase Runner globals. import json import shutil |
| `repair_preview_render.py` | Repair the diagnostic compiler's render records using TF2's native layouts.  This deliberately keeps the existing lumps at their original offsets: game-lump |
| `repair_preview_surface_alignment.py` | Build the next preview with native sweep bevels and corrected draw metadata. import json,shutil,struct from pathlib import Path |
| `repair_preview_visibility.py` | Correct visibility subtree starts without changing geometry, assets or physics. import json import shutil |
| `repair_prop_coverage.py` | Reclaim enclosed solids, restore original prop physics and bound VIS traversal. import collections,json,shutil,struct,time from pathlib import Path |
| `repair_signed_rock_collision.py` | Correct signed global BVH vertices without disturbing other collision. import json,shutil,struct,time from pathlib import Path |
| `repair_tunnel_passages.py` | Open only tool-material end caps inside portal apertures; fit frame physics. import collections,json,shutil,struct,time from pathlib import Path |
| `repair_world_batch_order.py` | Group exact world draw records below native submission's 2,048-batch limit. import json,os,shutil,struct from pathlib import Path |
| `restore_art_supports_baseline.py` | Restore the complete verified 0.1.42 snapshot after a client-loading regression. import json,os,shutil from pathlib import Path |
| `restore_lighting_baseline.py` | Withdraw 0.1.35 using the exact, hash-verified confirmed-lighting package. import json,shutil from pathlib import Path |
| `restore_terrain_uvs.py` | Bake recovered Apex terrain UV transforms into the native preview vertices.  OBJ import flips V. Apply the source transform in source UV space and then |
| `restore_working_visibility.py` | Restore the exact archived 0.1.27 package after the failed 0.1.28 experiment. import hashlib,json,shutil,zipfile from pathlib import Path |
| `simplify_preview_draw.py` | Topology-aware render-only simplification; full source collision stays intact. import ctypes, json, math, struct, time, os from pathlib import Path |
| `spatial_preview_meshes.py` | Replace broad material batches with spatial draw sections; keep exact vertices. import json,math,mmap,struct,shutil,time from pathlib import Path |
| `stage_client_loading_isolation.py` | Keep failed-candidate assets, but use the proven BSP/sidecar to isolate loading. import os,shutil from pathlib import Path |
| `stage_landscape_vg.py` | Restore missing rock placements directly from compiled VG/RMDL assets. import collections,json,struct from pathlib import Path |
| `stage_prop_geometry.py` | Stage structural prop meshes at their original Apex placements.  This bakes static meshes into the diagnostic BSP rather than compiling new MDLs. |
| `test_art_supports.py` | Exact scene preservation, source props, native alpha decals and physics. import collections,io,json,mmap,struct,unittest from build_art_supports import ROOT,SOURCE,TARGET,PACKAGE,M |
| `test_art_supports_loading.py` | Preserve the art release while making the road shader self-contained. import json,struct,unittest from pathlib import Path |
| `test_binary_tools.py` | Regression checks for package preprocessing and BSP collision validation. import json import struct |
| `test_budget_preview.py` | Validate actual source LODs, collision preservation and native draw constraints. import hashlib,json,struct,unittest from pathlib import Path |
| `test_camera_visibility.py` | Check native camera acceptance and immutable draw/physics data independently. import math, struct, unittest from pathlib import Path |
| `test_center_detail.py` | Check localized source restoration, native draw limits and exact preservation. import collections,json,struct,unittest from build_center_detail import ROOT,P,SOURCE,TARGET,PACKAGE, |
| `test_character_lighting.py` | Independent moving-model lighting and preservation regressions. import itertools,json,struct,subprocess,tempfile,unittest from build_character_lighting import ROOT,SOURCE,TARGET,OU |
| `test_coordinate_collision.py` | Check exact source physics, reported tunnel contacts and preserved draw data. import json,struct,unittest from pathlib import Path |
| `test_dev_materials.py` | Prove the texture pass preserves all geometry, lighting and collider data. import unittest,sys,struct,json from pathlib import Path |
| `test_draw_regression.py` | Verify that the regression repair changes only the declared draw records. import hashlib,json,mmap,struct,unittest from pathlib import Path |
| `test_environment_lighting.py` | Regression checks for the actual ray blocker bug and native menu routing. import unittest,tempfile,subprocess,struct from pathlib import Path |
| `test_expanded_collision.py` | import math import struct import unittest |
| `test_glass_console.py` | Preservation, exact source rebinding and native transparency compatibility. import collections,json,mmap,struct,unittest from build_glass_console import ROOT,SOURCE,TARGET,PACKAGE, |
| `test_interior_lighting.py` | Verify local PBR light routing, occlusion, preserved outdoor lighting and optimized assets. import unittest,json,struct,tempfile,subprocess,hashlib from pathlib import Path |
| `test_local_visibility.py` | Exercise native portal/camera safety against independent spatial expectations. import bisect, collections, copy, json, math, struct, unittest from pathlib import Path |
| `test_model_slots.py` | import struct import tempfile import unittest |
| `test_native_preview_cells.py` | import json,struct,unittest from pathlib import Path from native_preview_cells import make_cells,validate_cells |
| `test_native_triangle_collision.py` | Native collision layout and sweep regressions, including the real map audit. import itertools,json,struct,unittest import numpy as np |
| `test_northstar_build.py` | Regression checks for generated map planes and real target BSP references. import json import math |
| `test_phase_runner_catwalks.py` | Independent preservation, traversal, native rendering and presentation checks. import collections,hashlib,json,math,struct,subprocess,unittest from pathlib import Path |
| `test_phase_runner_firs.py` | Source recovery, alpha pipeline, physics and immutable-scene regression checks. import collections,json,mmap,os,struct,unittest from build_phase_runner_firs import ROOT,P,SOURCE,TA |
| `test_phase_runner_release.py` | Grounded release checks: visual/physics alignment and preserved established map data. import json,struct,sys,unittest from pathlib import Path |
| `test_phase_runner_trees.py` | Source recovery, alpha pipeline, physics and immutable-scene regression checks. import collections,json,mmap,os,struct,unittest from build_phase_runner_trees import ROOT,P,SOURCE,T |
| `test_playable_visibility.py` | Independent native acceptance and immutable gameplay/render data checks. import math, struct, unittest from repair_playable_visibility import ROOT, SOURCE, TARGET, PACKAGE, BASE, C |
| `test_portalfree_optimization.py` | Prove exact rendered corners, native range safety and portal-free sky coverage. import json,math,struct,unittest from pathlib import Path |
| `test_preview_index_padding.py` | import json,struct,unittest from pathlib import Path from repair_preview_index_padding import add_index_padding,validate_index_padding,read_lumps,audit_native |
| `test_preview_streaming_lighting.py` | import json import struct import sys |
| `test_preview_surface_alignment.py` | Regression checks for hull edge contacts, mesh ranges and removed barriers. import itertools,json,struct,unittest from pathlib import Path |
| `test_preview_visibility.py` | Exercise multi-level native visibility traversal and invalid geometry bounds. import struct,unittest from preview_visibility import build_visibility,validate_visibility |
| `test_prop_coverage.py` | Verify reclaimed collision union, original prop pieces and visibility capacity. import json,struct,unittest from pathlib import Path |
| `test_prop_physics.py` | import collections,json,math,mmap,struct,tempfile,unittest from pathlib import Path from read_prop_physics import read_phy,read_bvh,convex_planes |
| `test_prop_transforms.py` | Source prop placement must preserve handedness, pitch direction and scale. import unittest import tempfile |
| `test_recovered_landscape.py` | Check compiled geometry against a complete independent Legion export. import math,struct,unittest,tempfile,json,contextlib,io from pathlib import Path |
| `test_signed_rock_collision.py` | Regress actual signed BVH assets, reported obstructions and unaffected solids. import json,struct,unittest from pathlib import Path |
| `test_static_light_bake.py` | Verify native encoding and geometry/collision preservation of the lighting pass. import unittest,struct,hashlib import numpy as np |
| `test_terrain_uvs.py` | import unittest from restore_terrain_uvs import transformed_uv  |
| `test_tunnel_passages.py` | Check surgical collider adaptation and preservation of working rendering. import json,struct,unittest import numpy as np |
| `test_tunnel_walkways.py` | Validate visible traversal floors without changing unrelated geometry. import json,struct,unittest import numpy as np |
| `test_world_batch_order.py` | Native limit, full submission, and physical-reference preservation checks. import collections,json,random,struct,unittest from repair_world_batch_order import ROOT,SOURCE,TARGET,BA |
| `test_world_draw_budget.py` | Prevent reuse of the failed all-visible build and verify its native limit. import unittest from pathlib import Path |
| `tighten_prop_collision_probes.py` | from pathlib import Path p=Path('extend_prop_collision.py');s=p.read_text();s=s.replace('done=[];skipped=[];probes=[];cache={};pending_portals=[]','''done=[];skipped=[];probes=[];c |
| `triangle_capsule_reference.py` | Independent Euclidean reference for Titanfall's upright rounded player hull. import numpy as np  |
| `update_physics_packaging.py` | from pathlib import Path p=Path('package_northstar.py');s=p.read_text();a=s.index('    offset,length,_=lumps[0x57]');b=s.index('    return dict(version=',a) s=s[:a]+'''    primitiv |
| `validate_conversion_docs.py` | Reconcile release documentation against generated ledgers and retained code. import collections,json,re,struct,subprocess,sys,importlib.metadata from pathlib import Path |
| `validate_ground_geometry.py` | Check the repaired mesh references and preservation of the source physics. import json import struct |
| `validate_preview_sky.py` | Verify the dome geometry, inward winding and unchanged collision data. import json import math |
| `validate_prop_geometry.py` | Check restored prop rendering indices, bounds, winding and unchanged physics. import json import math |
| `validate_world_materials.py` | Check packaged v12 material headers and their external dependencies. import json import struct |
