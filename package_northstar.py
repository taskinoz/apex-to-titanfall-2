"""Validate and package a compiled diagnostic map as a Northstar mod."""
import argparse
import hashlib
import json
import os
import shutil
import struct
from pathlib import Path


def validate_bsp(path,require_native_index_padding=False):
    data = path.read_bytes()
    if len(data)<2064:
        raise ValueError('Truncated BSP header')
    magic,version,revision,last_lump = struct.unpack_from('<4s3I',data)
    if magic!=b'rBSP' or version!=37 or last_lump!=127:
        raise ValueError('Expected an internal Titanfall 2 v37 BSP')
    intervals=[]
    lumps={}
    for index in range(128):
        offset,length,lump_version,padding=struct.unpack_from('<4I',data,16+index*16)
        if not length:
            continue
        if offset<2064 or offset+length>len(data):
            raise ValueError(f'Lump {index} exceeds file bounds')
        intervals.append((offset,offset+length,index))
        lumps[index]=(offset,length,lump_version)
    intervals.sort()
    for left,right in zip(intervals,intervals[1:]):
        if left[1]>right[0]:
            raise ValueError(f'Overlapping lumps {left[2]} and {right[2]}')
    # Record sizes from the target compiler and native BSP schema.
    for index,size in ((0x0e,32),(0x50,28),(0x51,32),(0x55,28),(0x56,4),(0x57,8),(0x5c,32)):
        if index in lumps and lumps[index][1]%size:
            raise ValueError(f'Lump {index:#x} record size mismatch')
    for index in (0x0e,0x50,0x51,0x55,0x56,0x5c):
        if index not in lumps:
            raise ValueError(f'Missing required diagnostic geometry lump {index:#x}')
    # Engine loader uses a fixed 1024-byte material-sort bitset.
    # The 0.1.20 development minidump showed an oversized memset overwriting
    # its saved model pointer; retain shared sorts below this native capacity.
    if lumps.get(0x52,(0,0,0))[1]//12>8192:
        raise ValueError('Native material-sort loader capacity exceeded')
    sets=lumps.get(0x57,(0,0,0))[1]//8
    offset,length,_=lumps[0x56]
    for cell,(first,count) in enumerate(struct.iter_unpack('<2H',data[offset:offset+length])):
        if first+count>sets:
            raise ValueError(f'Collision grid cell {cell} refers outside geosets')
    brush_count=lumps[0x5c][1]//32
    static_props=struct.unpack_from('<I',data,lumps[0x7b][0]+12)[0] if lumps.get(0x7b,(0,0,0))[1]>=16 else 0
    palette_count=lumps.get(0x5b,(0,0,0))[1]//4
    primitive_offset,primitive_length,_=lumps.get(0x59,(0,0,0))
    primitive_count=primitive_length//4
    if primitive_length%4 or lumps.get(0x5a,(0,0,0))[1]!=primitive_count*16:
        raise ValueError('Primitive bounds count differs')
    if lumps.get(0x58,(0,0,0))[1]!=sets*16:
        raise ValueError('Geoset bounds count differs')
    def validate_primitive(packed):
        kind=packed>>24;index=(packed>>8)&65535
        # 0x60 references a static-prop placement; LEVEL_INFO (0x7b) field 3 is the placement count.
        limit=brush_count if kind==0 else lumps.get(0x45,(0,0,0))[1]//44 if kind==0x40 else static_props if kind==0x60 else 0
        if index>=limit or (packed&255)>=palette_count:
            raise ValueError('Collision primitive refers outside brushes/contents')
    for (packed,) in struct.iter_unpack('<I',data[primitive_offset:primitive_offset+primitive_length]):
        validate_primitive(packed)
    if 0x45 in lumps:
        for lid,size in ((3,12),(0x42,4),(0x44,16),(0x45,44),(0x60,2),(0x61,4)):
            if lid not in lumps or lumps[lid][1]%size:
                raise ValueError('Malformed native triangle collision buffer')
        def count(lid,size):return lumps[lid][1]//size
        o,n,_=lumps[0x45]
        for header in struct.iter_unpack('<6h4i4f',data[o:o+n]):
            flags,texture_flags,texture,verts,tris,bevels,first_vert,first_tri,first_node,first_bevel,*frame=header
            nodes=2*(tris-(tris+3)%6+3)//3
            if verts<3 or tris<1 or min(first_vert,first_tri,first_node,first_bevel,bevels)<0 or first_vert+verts>count(3,12) or first_tri+tris>count(0x42,4) or first_tri+tris>count(0x60,2) or first_node+nodes>count(0x44,16) or first_bevel>count(0x61,4):
                raise ValueError('Native triangle collision header exceeds buffers')
    offset,length,_=lumps[0x57]
    for geo,(group,count,packed) in enumerate(struct.iter_unpack('<HHI',data[offset:offset+length])):
        if count<1 or (packed&255)>=palette_count:
            raise ValueError(f'Invalid diagnostic geoset {geo}')
        if count==1:validate_primitive(packed)
        elif packed>>24!=0 or (packed>>8 & 65535)+count>primitive_count:
            raise ValueError(f'Compound geoset {geo} exceeds primitive array')
    index_validation=None
    if require_native_index_padding:
        from repair_preview_index_padding import validate_index_padding
        def payload(i):o,n,_=lumps[i];return data[o:o+n]
        index_validation=validate_index_padding(payload(0x50),payload(0x4f),payload(0x52))
    return dict(version=version,bytes=len(data),nonempty_lumps=len(lumps),
                collision_geosets=sets,structural_checks_passed=True,in_game_verified=False,
                native_triangle_pair_validation=index_validation)


def package(bsp,source_report,output):
    status=json.loads(source_report.read_text())
    map_name=bsp.stem
    def stage_asset(source,target):
        # Large immutable 0.1.37 outputs share storage within the workspace.
        # Unlink the owned package path before linking; never overwrite its
        # source through an existing hard link on a repeated build.
        source=Path(source);target=Path(target)
        if status.get('catwalk_release') and source.stat().st_size>10*1024*1024:
            if not target.resolve().is_relative_to(output.resolve()):raise ValueError('Package target escaped output')
            if target.exists() and os.path.samefile(source,target):return
            target.unlink(missing_ok=True)
            os.link(source,target)
        else:shutil.copy2(source,target)
    if status.get('camera_visibility_repair'):
        from audit_world_draw_budget import enforce_camera_bypass_budget
        enforce_camera_bypass_budget(bsp)
    if status.get('world_draw_budget_repair'):
        from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
        budget=audit(bsp)
        if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):
            raise ValueError('Draw-budget candidate lacks required 15 percent headroom')
    if status.get('local_visibility_rebuild'):
        from rebuild_local_visibility import validate
        from repair_preview_index_padding import read_lumps
        current=read_lumps(bsp,(1,0x51,*range(0x6a,0x7a)))
        validate(current,current[0x51])
    checks=validate_bsp(bsp,require_native_index_padding=bool(status.get('native_cell_rebuild') or status.get('index_padding_repair')))
    output.mkdir(parents=True,exist_ok=True)
    (output/'runtime-validation.json').unlink(missing_ok=True)
    maps=output/'mod/maps'
    scripts=output/'mod/scripts/vscripts'
    maps.mkdir(parents=True,exist_ok=True)
    scripts.mkdir(parents=True,exist_ok=True)
    stage_asset(bsp,maps/bsp.name)
    if status.get('streaming_sidecar'):
        sidecar=bsp.with_suffix('.stbsp')
        if not sidecar.is_file():raise ValueError('Required streaming sidecar is missing')
        shutil.copy2(sidecar,maps/sidecar.name)
    # Sky MDLs live in the native Coliseum VPK. RPak aliases supply their GPU
    # assets but do not mount that VPK for this custom map, so stage local MDLs.
    sky_models=output/'mod/models/vistas'
    sky_models.mkdir(parents=True,exist_ok=True)
    for name in ('grave_se.mdl','planet_blue_sun.mdl'):
        shutil.copy2(Path('inputs/tf2-sky/models/vistas')/name,sky_models/name)
    for ent in bsp.parent.glob(bsp.stem+'_*.ent'):
        shutil.copy2(ent,maps/ent.name)
    textured = bool(status.get('world_materials'))
    mod=dict(Name='PhaseRunner.Preview',Version='0.1.15' if status.get('broad_restore') else '0.1.14' if status.get('missing_sections') else '0.1.13' if status.get('area_details') else '0.1.12' if status.get('support_structures') else '0.1.11' if status.get('lighting_repair') else ('0.1.10' if status.get('map_structures') else ('0.1.9' if status.get('terrain_uv_repair') else ('0.1.8' if status.get('ground_surface_repair') else ('0.1.7' if status.get('structural_props') else ('0.1.6' if status.get('preview_sky') else ('0.1.5' if textured else '0.1.4')))))),LoadPriority=10,
             Description='Phase Runner development preview with recovered textures and geometry. Props and collision remain incomplete.',
             ConVars=[dict(Name='phase_runner_local_test',DefaultValue='0')],
             Scripts=[dict(Path='_phase_runner_preview.nut',RunOn='SERVER && MP',
                           ServerCallback=dict(After='PhaseRunnerPreview_Init'))])
    if status.get('portal_material_repair'):mod['Version']='0.1.16'
    if status.get('visibility_range_repair'):mod['Version']='0.1.17'
    if status.get('landscape_restore'):mod['Version']='0.1.18'
    if status.get('draw_regression_repair'):mod['Version']='0.1.19'
    if status.get('prop_physics'):mod['Version']='0.1.20'
    if status.get('native_cell_rebuild'):mod['Version']='0.1.21'
    if status.get('index_padding_repair'):mod['Version']='0.1.22'
    if status.get('surface_alignment_repair'):mod['Version']='0.1.23'
    if status.get('signed_rock_collision_repair'):mod['Version']='0.1.24'
    if status.get('prop_coverage_repair'):mod['Version']='0.1.25'
    if status.get('coordinate_collision_repair'):mod['Version']='0.1.26'
    if status.get('full_collision_rebuild'):mod['Version']='0.1.27'
    if status.get('camera_visibility_repair'):mod['Version']='0.1.28'
    if status.get('world_draw_budget_repair'):mod['Version']='0.1.29'
    if status.get('tunnel_collision_repair'):mod['Version']='0.1.30'
    if status.get('static_light_bake'):
        mod['Version']='0.1.31'
        mod['Description']='Phase Runner preview with static sun/sky lightmaps and corrected PBR tangent frames.'
    if status.get('dev_material_repair'):
        mod['Version']='0.1.32'
        mod['Description']='Phase Runner preview with baked lighting, native PBR materials and repaired developer-texture surfaces.'
    if status.get('lighting_environment_repair'):
        mod['Version']='0.1.33'
        mod['Description']='Phase Runner preview with corrected sun/sky lightmaps and separate native gameplay/menu lighting environments.'
    if status.get('interior_light_repair'):
        mod['Version']='0.1.34'
        mod['Description']='Phase Runner preview with baked interior point lights, mip-ready materials and fewer native shadow draw calls.'
    if status.get('local_visibility_rebuild'):
        mod['Version']='0.1.35'
        mod['Description']='Phase Runner preview with native spatial visibility portals and protected nearby tunnel/outdoor geometry.'
    if status.get('portalfree_optimization'):
        mod['Version']='0.1.36'
        mod['Description']='Phase Runner preview with restored single-cell sky visibility, shared render batches and local tunnel protection.'
    if status.get('catwalk_release'):
        mod['Version']='0.1.37'
        mod['Description']='Phase Runner with lit industrial tunnel catwalks and railings, loading artwork and improved tunnel visibility.'
    (output/'mod.json').write_text(json.dumps(mod,indent=2))
    paks=output/'paks'
    paks.mkdir(exist_ok=True)
    # Load native Coliseum assets for the fallback material and engine map assets.
    # Aliases use existing game files; no Titanfall assets are copied or rewritten.
    pak_config = dict(Aliases={
        map_name+'.rpak':'mp_coliseum.rpak',
        map_name+'_loadscreen.rpak':'mp_coliseum_loadscreen.rpak'})
    if textured:
        material_project = Path(status.get('material_project','output/phase-runner/world-materials'))
        material_validation = json.loads((material_project/'validation.json').read_text())
        if not material_validation['all_dependencies_present']:
            raise ValueError('World RPak has unresolved dependencies')
        stage_asset(material_project/'build/phase_runner_world.rpak',paks/'phase_runner_world.rpak')
        pak_config['Postload'] = {'phase_runner_world.rpak':'mp_coliseum.rpak'}
        status['world_material_validation'] = material_validation
    (paks/'rpak.json').write_text(json.dumps(pak_config,indent=2))
    probe_vectors=lambda key: ', '.join('< '+', '.join(f'{v:.6f}' for v in p[key])+' >'
                                      for p in status.get('collision_probes',[]))
    probe_script=(
        '\t\tarray<vector> starts = [ '+probe_vectors('start')+' ]\n'
        '\t\tarray<vector> ends = [ '+probe_vectors('end')+' ]\n'
        '\t\tint hits = 0\n'
        '\t\tfor ( int i = 0; i < starts.len(); i++ )\n\t\t{\n'
        '\t\t\tTraceResults result = TraceLine( starts[i], ends[i], null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n'
        '\t\t\tif ( result.fraction < 1.0 || result.startSolid || result.allSolid )\n\t\t\t\thits++\n'
        '\t\t\tprintl( "Phase Runner collision probe " + i + ": fraction=" + result.fraction )\n'
        '\t\t\tprintl( "Phase Runner collision occupancy " + i + ": startSolid=" + result.startSolid + " allSolid=" + result.allSolid )\n\t\t}\n'
        '\t\tprintl( "Phase Runner collision probes: " + hits + "/" + starts.len() + " hit" )\n')
    if status.get('prop_physics'):
        new_probes=status.get('pilot_hull_contact_probes',[p for p in status['collision_probes'] if p['kind'] in ('rock','pipe','portal') or p.get('prop_probe')])
        vectors=lambda key: ', '.join('< '+', '.join(f'{v:.6f}' for v in p[key])+' >' for p in new_probes)
        probe_script += ('\t\tarray<vector> propStarts = [ '+vectors('start')+' ]\n'
            '\t\tarray<vector> propEnds = [ '+vectors('end')+' ]\n'
            '\t\tint hullHits = 0\n'
            '\t\tfor ( int i = 0; i < propStarts.len(); i++ )\n\t\t{\n'
            '\t\t\tTraceResults result = TraceHull( propStarts[i], propEnds[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n'
            '\t\t\tif ( result.fraction < 1.0 && !result.startSolid && !result.allSolid )\n\t\t\t\thullHits++\n'
            '\t\t\tprintl( "Phase Runner prop hull probe " + i + ": fraction=" + result.fraction + " startSolid=" + result.startSolid )\n\t\t}\n'
            '\t\tprintl( "Phase Runner prop hull probes: " + hullHits + "/" + propStarts.len() + " hit" )\n')
    if status.get('hull_clearance_probes'):
        vectors=lambda key: ', '.join('< '+', '.join(f'{v:.6f}' for v in p[key])+' >' for p in status['hull_clearance_probes'])
        probe_script += ('\t\tarray<vector> edgeStarts = [ '+vectors('start')+' ]\n'
            '\t\tarray<vector> edgeEnds = [ '+vectors('end')+' ]\n'
            '\t\tint clearEdges = 0\n'
            '\t\tfor ( int i = 0; i < edgeStarts.len(); i++ )\n\t\t{\n'
            '\t\t\tTraceResults result = TraceHull( edgeStarts[i], edgeEnds[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n'
            '\t\t\tif ( result.fraction == 1.0 && !result.startSolid && !result.allSolid )\n\t\t\t\tclearEdges++\n'
            '\t\t\tprintl( "Phase Runner edge clearance probe " + i + ": fraction=" + result.fraction + " startSolid=" + result.startSolid )\n\t\t}\n'
            '\t\tprintl( "Phase Runner edge clearance probes: " + clearEdges + "/" + edgeStarts.len() + " clear" )\n')
    (scripts/'_phase_runner_preview.nut').write_text(
        'untyped\n\nglobal function PhaseRunnerPreview_Init\n\n'
        'void function PhaseRunnerPreview_Init()\n{\n'
        f'\tif ( GetMapName() != "{map_name}" )\n\t\treturn\n'
        '\tClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )\n'
        '\tClassicMP_ForceDisableEpilogue( true )\n'
        '\tAddCallback_OnClientConnected( PhaseRunnerPreview_AssignTeam )\n'
        '\tAddClientCommandCallback( "phase_runner_where", PhaseRunnerPreview_Position )\n'
        '\tforeach ( int team in [ TEAM_IMC, TEAM_MILITIA ] )\n\t{\n'
        '\t\tforeach ( string classname in [ "info_spawnpoint_human_start", "info_spawnpoint_human" ] )\n\t\t{\n'
        '\t\t\tentity point = CreateEntity( classname )\n'
        '\t\t\tpoint.SetOrigin( < -761.369792, -4444.361979, -991.0 > )\n'
        '\t\t\tpoint.SetAngles( < 0, 0, 0 > )\n'
        '\t\t\tpoint.kv.teamnumber = team\n'
        '\t\t\tpoint.kv.ignoreGamemode = 1\n'
        '\t\t\tpoint.s.lastUsedTime <- -999\n'
        '\t\t\tpoint.s.inUse <- false\n'
        '\t\t\tDispatchSpawn( point )\n\t\t}\n\t}\n'
        '\tprintl( "Phase Runner preview: native pilot spawns and no-dropship intro configured." )\n'
        '\tif ( GetConVarBool( "phase_runner_local_test" ) )\n\t{\n'
        '\t\tSetConVarBool( "sp_not_focus_pause", false )\n'
        '\t\tSetConVarBool( "ns_report_server_to_masterserver", false )\n'
        '\t\tSetConVarBool( "ns_report_sp_server_to_masterserver", false )\n'
        '\t\tif ( GetConVarString( "ip" ) == "127.0.0.1" )\n'
        '\t\t\tSetConVarBool( "ns_auth_allow_insecure", true )\n'
        '\t\tprintl( "Phase Runner local test: server reporting disabled after startup config." )\n'
        '\t\tthread PhaseRunnerPreview_TestStatus()\n'
        +probe_script+'\t}\n'
        '\tprintl( "Phase Runner preview: incomplete geometry conversion; use noclip for inspection." )\n}\n'
        '\nvoid function PhaseRunnerPreview_AssignTeam( entity player )\n{\n'
        '\tif ( !IsFFAGame() && !IsPrivateMatchSpectator( player ) && player.GetTeam() != TEAM_IMC && player.GetTeam() != TEAM_MILITIA )\n'
        '\t\tSetTeam( player, TEAM_IMC )\n'
        '\tprintl( "Phase Runner connected player team=" + player.GetTeam() )\n}\n'
        '\nbool function PhaseRunnerPreview_Position( entity player, array<string> args )\n{\n'
        '\tif ( !IsValid( player ) )\n\t\treturn true\n'
        '\tvector pos = player.GetOrigin()\n'
        '\tstring message = format( "Phase Runner position: %.1f %.1f %.1f", pos.x, pos.y, pos.z )\n'
        '\tprintl( message )\n'
        '\tSendHudMessage( player, message, -1, 0.35, 255, 255, 255, 255, 0.1, 12.0, 0.1 )\n'
        '\treturn true\n}\n'
        '\nvoid function PhaseRunnerPreview_TestStatus()\n{\n'
        '\tfor ( int i = 0; i < 24; i++ )\n\t{\n'
        '\t\twait 5.0\n'
        '\t\tprintl( "Phase Runner test state=" + GetGameState() + " time=" + Time() )\n'
        '\t\tforeach ( entity player in GetPlayerArray() )\n'
        '\t\t\tprintl( "Phase Runner test player: team=" + player.GetTeam() + " alive=" + IsAlive( player ) + " origin=" + player.GetOrigin() )\n'
        '\t}\n}\n')
    (output/'README.md').write_text(
        '# Phase Runner - Northstar geometry preview\n\n'
        '**This is an incomplete development preview, not a playable Apex map port.**\n\n'
        'Copy this folder to `Titanfall2/R2Northstar/mods/PhaseRunner.Preview`, restart Northstar, '
        'and use the console command `map mp_phase_runner_preview`. '
        'Inspection may require `sv_cheats 1` and `noclip`. For a localhost inspection test, '
        'set `ip 127.0.0.1` and `phase_runner_local_test 1` before loading the map.\n\n'
        'The BSP contains recovered world render geometry, approximate floor/ramp collision and a limited wall selection. '
        'Native Coliseum RPak aliases supply the temporary material assets. '
        'Native pilot spawns and a no-dropship intro support preview startup. The recovered Apex sky dome supplies the background. '+
        ('Recovered Apex world textures use native TF2 shader approximations. ' if textured else '')+
        ('This build restores a limited structural prop selection as world meshes. Most prop material bindings use the first QC skin material as an approximation. ' if status.get('structural_props') else '')+
        ('Identical render copies are removed. Unsupported transparent terrain overlays are omitted to reduce ground interference; some original ground detail is missing. ' if status.get('ground_surface_repair') else '')+
        ('Recovered terrain UV scales are applied in source coordinates. Full terrain layer blending is unfinished. ' if status.get('terrain_uv_repair') else '')+
        ('Recovered Phase Runner ring frames, panels and tunnel sections are included as render meshes, with approximate material bindings. Their native prop collision remains unfinished. ' if status.get('map_structures') else '')+
        ('Source sun and ambient lights replace prototype lights; native baked illumination and static shadow conversion remain unfinished. A native STBSP catalog is included for resident RPak textures; spatial mip streaming is not implemented. ' if status.get('lighting_repair') else '')+
        ('Recovered construction supports and crane parts preserve their original placements. The obsolete preview sky camera and Titanfall vista spawn are removed. Additional prop collision and exact skin bindings remain unfinished. ' if status.get('support_structures') else '')+
        ('Additional recovered details near the northern inspection area are rendered at source placements. This pass adds no physics; foliage, unavailable landscape meshes and assets over the area budget remain omitted. ' if status.get('area_details') else '')+
        ('All recovered SMD triangle sections are now read. Previously omitted submeshes on already restored placements are appended without duplicating their first sections. Unknown material slots still use the first QC skin as an approximation. ' if status.get('missing_sections') else '')+
        ('This build restores additional textured structures across the arena and prioritizes larger recovered rocks. The native visibility tree is rebuilt with spatial leaves and verified geometry bounds. Pop-in still requires client verification. ' if status.get('broad_restore') else '')+
        ('The two tunnels now use validated compiled material slots; unsupported opaque AO/decal overlays are omitted. 321 recovered moss/snow terrain props retain their original placements and skins. Portal pop-in and terrain overlap need a client check. ' if status.get('portal_material_repair') else '')+
        ('Visibility subtree starts now match the native Homestead/Colony layout. This build changes 26 internal reference offsets while preserving geometry, textures, lighting and collision. Visual confirmation of the pop-in correction is still required. ' if status.get('visibility_range_repair') else '')+
        'Native static prop model compilation, original collision flags, complete collision, original sky model, and final gameplay spawns '
        'remain unfinished. Runtime loading and visual correctness must be checked in Northstar.\n\n'
        'Build details are in `build-status.json`. When present, `runtime-validation.json` records '
        'server/client load results and sample collision probes, separately from visual verification. '
        'This local package contains extracted game geometry.\n',encoding='utf-8')
    if status.get('landscape_restore'):
        (output/'README.md').write_text('''# Phase Runner Northstar preview 0.1.18

Load with `map mp_phase_runner_preview` after restarting Northstar.

This build adds 365 original rock placements from nine compiled models (1,662,160 triangles), retaining their original skins, scale and transforms. The compiled geometry decoder was checked against an independent complete Legion export.

World vertices are shared while preserving positions, normals, texture coordinates, colours, lightmap fields and mirrored UV seams. Tangents are averaged and orthogonalized at shared vertices. Hollow portal materials use native two-sided drawing. Map-wide draw bounds are a temporary conservative measure for investigating distance/angle pop-in and may lower frame rate. They do not prove the underlying rendering issue is fixed.

A 4096-pixel opaque ground atlas uses the recovered snow, lavender, secondary moss and layer-mask images to blend 39 shared boundaries. This is a 96-unit preview seam approximation, not the original Apex layered shader. Atlas resampling can soften texture detail. No transparent overlay geometry is added.

A native v8 STBSP material catalog is included. Textures remain resident in the custom RPak; spatial texture streaming is unfinished.

This is an incomplete development preview. Original static prop collision, complete exterior collision, final lighting/shadows, layered rock materials, foliage and gameplay support remain unfinished. The new rocks add render geometry only. Missing interactable doors remain omitted as requested. Dedicated server checks do not verify client rendering or complete movement coverage.

See `build-status.json` and `runtime-validation.json` for verification evidence.
''',encoding='utf-8')
    if status.get('draw_regression_repair'):
        (output/'README.md').write_text('''# Phase Runner Northstar preview 0.1.19

Restart Northstar and load `map mp_phase_runner_preview`.

This build removes the two draw experiments from 0.1.18: map-wide bounds and two-sided portal material states. Actual geometric mesh bounds, spatial visibility records, and the earlier native material rasterizer settings are restored. The 365 recovered rock placements, opaque terrain seam atlas, shared vertex buffers and existing collision are retained.

This is a regression repair. Earlier distance/angle pop-in may remain; client verification is required. The terrain seam bake approximates the original layered shader. New rocks add render geometry only. Complete prop collision, exterior collision, original shaders, final lighting and gameplay support remain unfinished.

A native STBSP catalog is included; custom textures are resident, with spatial mip streaming unfinished. Server checks do not verify client rendering or full movement coverage. See `build-status.json` and `runtime-validation.json` for evidence.
''',encoding='utf-8')
    if status.get('prop_physics'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.20

Restart Northstar and load `map mp_phase_runner_preview`.

Rendering uses smaller spatial mesh sections with the original triangles, materials and vertex attributes. This changes draw granularity and the native visibility tree; remaining pop-in needs client verification. Actual geometry bounds and the restored native rasterizer settings remain in use.

Rock and pipe collision is added at the original prop transforms. Available IRPS physics preserves its convex pieces. Dense rock BVHs use a bounded 26-direction hull approximation, which may fill concavities; approximations that overlap the portal bounds are withheld. Large portal tubes retain partial thin surface collision; no whole-tube bounding box closes the passage. Smaller hollow elbow decorations remain deferred because the native brush index capacity is full. Existing world solids are retained, with only exact duplicate brushes removed. A compound collision grid shares primitive ranges across cells.

Textures and STBSP catalog are retained. Complete portal/prop collision, spatial texture streaming, original layered shaders, final lighting/shadows and gameplay support remain unfinished. Server probes verify selected surfaces; full movement and GPU rendering require a client check.

See `build-status.json` and `runtime-validation.json` for counts and evidence.
""",encoding='utf-8')
    if status.get('native_cell_rebuild'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.21

Restart Northstar and load `map mp_phase_runner_preview`.

New TF2 visibility cells and portals replace the single-cell prototype. Four outdoor cells connect through full shared faces, with native sky portals and a roots-first spatial visibility forest. Geometry crossing a cell boundary appears in both cell trees. Apex visibility records are not reused. Spatial mesh sections now declare their actual local vertex ranges. This conservative layout needs client rendering checks and is not final occlusion optimization.

Original convex physics adds collision to 165 railing placements and 67 other structural props. Both tubes gain 64 additional walkable surface prisms each. Every previous world/prop solid is retained in the collision union: 424 entries are reclaimed by exact contiguous box unions or solids entirely contained in a solid box. Gaps and concave structures are not filled by this optimization.

Materials, textures, source placement geometry, lighting and the resident-texture STBSP catalog are retained. The reported invisible central props still need a client check to distinguish visibility from material problems. Complete collision, original layered shaders, final lighting and spatial texture streaming remain unfinished. Dedicated server traces verify selected contacts, not complete movement or GPU rendering.

See `build-status.json` and `runtime-validation.json` for evidence.
""",encoding='utf-8')
    if status.get('index_padding_repair'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.22

Restart Northstar and load `map mp_phase_runner_preview`.

This repairs the 0.1.21 rendering crash. The client dump showed the engine reading two triangles from an odd-sized mesh without its required degenerate padding triangle, then using the next mesh's smaller indices with the wrong vertex origin. Each odd-sized mesh now has the same three repeated padding indices used by native Homestead and Colony. Real triangle counts, positions, normals, texture coordinates, materials and bounds remain unchanged.

The experimental four-cell portal layout and narrowed vertex ranges are withdrawn. Visibility and vertex-range metadata return to 0.1.20, which the user reported rendering better. Earlier pop-in and incomplete materials may remain. The additional 165 railing placements, 67 structural placements and 128 tube walkable surfaces from 0.1.21 retain their collision.

This is still an incomplete preview. Runtime collision samples and server loading cannot verify client rendering, a player grapple or complete movement. Textures, lighting and the resident-texture STBSP catalog are retained. Original layered shaders, complete collision and spatial texture streaming remain unfinished.

See `build-status.json` and `runtime-validation.json` for evidence.
""",encoding='utf-8')
    if status.get('surface_alignment_repair'):
        repair=status['surface_alignment_repair'];c=repair['collision'];d=repair['draw']
        (output/'README.md').write_text(f"""# Phase Runner Northstar preview 0.1.23

Restart Northstar and load `map mp_phase_runner_preview`.

Native player-hull edge planes are added to {c['brushes_with_bevels_added']:,} existing collision brushes ({c['edge_planes_added']:,} planes). These remove false contacts near angled edges without moving brush origins, changing bounds or replacing original faces. Complex colliders that could not be safely reconstructed are retained, and missing prop/tube collision remains unfinished.

Every draw section declares its exact local vertex span and keeps the native triangle-pair padding. Apex arena start barrier surfaces (108 triangles) are omitted, leaving their openings visible. These are source barrier visuals, not interactive doors; source barrier collision ownership is still being checked. No nearby collision is deleted by a bounds guess.

Uniform preview lightmap pages replace Coliseum's spatial baked illumination. This is a temporary lighting calibration, not a final map-specific directional bake. The preview does not carry Coliseum's shadow geometry or menu entities. The reported ramp material and stray shadows still need client investigation.

Recovered materials, models, the current visibility tree and resident-texture STBSP catalog are retained. The cell lookup assigns the same cell everywhere; out-of-bounds unloading has not been established as the pop-in cause. Remaining pop-in, complete collision, layered/PBR shaders and spatial texture streaming are unfinished. Dedicated server checks do not verify GPU rendering or full player movement.

See `build-status.json` and `runtime-validation.json` for evidence.
""",encoding='utf-8')
    if status.get('signed_rock_collision_repair'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.24

Restart Northstar and load `map mp_phase_runner_preview`.

Corrects signed packed physics vertices for 73 placements of the large desertlands rock model. The previous unsigned decode enlarged and displaced its hulls, blocking empty space at (186,-5211,-955) and (-1716,-3994,-963). Both locations are now checked with player-sized clearance probes; eight additional contacts exercise corrected rocks. Other collision shapes and their side data are preserved.

Rock collision still uses convex approximations and cannot represent every recess. Full collision coverage remains unfinished. Geometry, materials, triangle padding, lighting and the current visibility tree are retained. The separate ground-level rock pop-in remains under investigation; disabling pvs_extraCull did not resolve it. Client rendering and movement need verification.

See build-status.json and runtime-validation.json for evidence. This is a development preview, not the complete playable port.
""",encoding='utf-8')
    if status.get('prop_coverage_repair'):
        c=status['prop_coverage_repair'];v=status['visibility_queue_rebuild']
        (output/'README.md').write_text(f"""# Phase Runner Northstar preview 0.1.25

Restart Northstar and load `map mp_phase_runner_preview`.

Original convex collision is restored to {c['restored_prop_placements']} crate, ring and hollow pipe elbow placements, with native player-hull edge planes. {c['redundant_world_brushes_removed']} world brushes wholly enclosed by existing rock solids are removed to reclaim capacity. Every removed brush has a conservative full-bounds containment proof; the existing solid union is preserved. Ring openings are represented by their original separate pieces, not whole-object boxes. Complete collision remains unfinished.

The single-cell spatial visibility tree is rebuilt with 128-reference leaves. Its maximum pending node count falls from {v['before']['maximum_pending_nodes']} to {v['after']['maximum_pending_nodes']}, below the 1,024-entry local traversal queue found in Titanfall's reader. Actual geometric bounds, draw buffers, material states and triangle padding are retained. This is a diagnostic change: the queue's involvement in the reported angle-dependent pop-in has not been established, and GPU rendering needs client verification.

Use `cmd phase_runner_where` in the console to display your coordinates on screen for 12 seconds and record them in the server log. This replaces relying on getpos when it produces no output.

Recovered textures, sky and resident-texture STBSP catalog are retained. Original layered/PBR shaders, final lighting, spatial mip streaming and full gameplay support remain incomplete. This is a development preview.

See build-status.json and runtime-validation.json for evidence.
""",encoding='utf-8')
    if status.get('coordinate_collision_repair'):
        c=status['coordinate_collision_repair']
        (output/'README.md').write_text(f"""# Phase Runner Northstar preview 0.1.26

Restart Northstar and load `map mp_phase_runner_preview`.

Original convex physics is added to {c['placements_by_kind']['stairs']} stair placements and {c['placements_by_kind']['cargo']} containers/equipment props, including the stairs near (-4176,-1464,-1015) and cargo container near (-1330,3043,-928). Both large portal tunnels gain 900 additional walkable source surface prisms each. Half the tunnel surface budget concentrates around the three reported pipe gaps; the rest covers large omitted floor surfaces. Separate source convex pieces and surface prisms retain openings, with native player-hull edge planes. Existing collision is preserved byte for byte.

All three reported pipe columns have explicit contact probes ending within the newly restored source floor. Full movement coverage remains incomplete, and {c['remaining_brush_capacity']} native brush slots remain available.

Render geometry, visibility, textures and lighting are unchanged. The camera-angle disappearing rocks and stairs are unresolved; this release does not claim to fix them. Recovered textures, sky and resident-texture STBSP catalog are retained. Original layered/PBR shaders, final lighting, spatial mip streaming and full gameplay support remain incomplete.

Use `cmd phase_runner_where` to display and log coordinates. See build-status.json and runtime-validation.json for validation evidence.
""",encoding='utf-8')
    if status.get('full_collision_rebuild'):
        c=status['full_collision_rebuild']
        (output/'README.md').write_text(f"""# Phase Runner Northstar preview 0.1.27

Restart Northstar and load `map mp_phase_runner_preview`.

Collision is rebuilt across all {c['solid_model_placements']:,} restored solid-model placements. Original physics supplies {c['source_physics_model_placements']:,}; two blue barrels use their recovered visual surfaces because their physics export is unavailable. The {c['intentionally_nonsolid_placements']} source props marked nonsolid remain nonsolid.

All {c['convex_brushes']:,} convex pieces have native player sweep bevels. Detailed concave rocks, complete pipe/tunnel surfaces and world geometry use {c['native_triangles']:,} native collision triangles. These replace partial floor patches and approximate whole-rock hulls, retaining openings and recesses. Every model collider is checked against its recovered source physics, and every brush and triangle is audited for native indices, bounds, plane flags and stored geometry. Reported pipe floor positions have direct engine probes.

The full source world surface is retained inside Titanfall's ±32,760 coordinate envelope; 370 remote lobby/sky-limit polygons outside it are omitted. Render geometry, materials, lighting, visibility and STBSP are unchanged. Pop-in remains a separate unresolved rendering issue.

Dedicated point, clear-start player-hull and clearance checks are recorded in runtime-validation.json. They verify sampled engine contacts, not every possible player movement or grapple. Client movement remains unverified; please test stairs, rocks, crates, railings and the interiors of both pipes.

Use `cmd phase_runner_where` to display and log coordinates. Original layered/PBR shaders, final lighting and spatial texture streaming remain incomplete.
""",encoding='utf-8')
    if status.get('camera_visibility_repair'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.28

Restart Northstar and load `map mp_phase_runner_preview`.

This is a controlled visibility diagnostic. Native visibility node and object-reference boxes contain the playable camera domain, bypassing camera-angle rejection in the access-path clipping stage. The tree has 87 directly reachable leaves and preserves all 22,170 mesh references in their earlier order. Actual geometric mesh bounds, triangle-pair padding, vertices, materials, lighting and the complete 0.1.27 collision are unchanged byte for byte.

This may reduce frame rate because PVS is deliberately conservative. The root cause of the angle-dependent disappearance remains unconfirmed. Dedicated loading and collision checks cannot verify GPU rendering. Please compare ground-level rocks, stairs and both tunnel shells while rotating the camera through horizontal, upward and downward views.

The user reports improved collision in 0.1.27 but some invisible tunnel barriers remain. This build retains that collision while their exact source ownership is investigated. It does not remove nearby rocks or fill tunnel openings by a bounds guess. Use `cmd phase_runner_where` to display and log a blocked passage's coordinates.

The STBSP resident-texture catalog is included. Full spatial texture streaming, original layered/PBR shaders, final lighting and complete gameplay support remain unfinished. Build and runtime evidence are recorded separately from client visual verification.
""",encoding='utf-8')
    if status.get('world_draw_budget_repair'):
        b=status['world_draw_budget_repair']
        (output/'README.md').write_text(f'''# Phase Runner Northstar preview 0.1.29

Restart Northstar and load `map mp_phase_runner_preview`.

This is a lower-detail visibility diagnostic. Original Apex model LODs and component-anchored reduction keep all {b['all_restored_placements']:,} recovered placements while bringing the entire arena within Titanfall's native world draw-index capacity. The BSP contains {b['after']['real_triangles']:,} rendered triangles and uses {b['after']['native_padded_indices']:,} of {b['after']['world_index_capacity']:,} available indices. Actual spatial geometry bounds and a bounded native visibility tree remain in use.

The complete user-tested 0.1.27 collision is retained. Its position buffer prefix and every collision structure remain byte-identical. Render detail is reduced, so small decorative details can differ from collision. Terrain triangles retain their previous positions, textures and UVs; existing recovered materials, skybox, uniform lighting and resident-texture STBSP catalog remain included.

This removes a verified capacity overflow, but its role in the angle-dependent disappearance still needs a client check. Please compare ground-level rocks, stairs and both tunnel shells while looking horizontally, up and down. Dedicated loading and collision samples do not verify GPU rendering.

Material approximations remain where original bindings have no recovered texture. Original layered/PBR shaders, final lighting, full spatial mip streaming and complete gameplay remain unfinished. Invisible tunnel barriers remain under investigation and are unchanged in this rendering pass. Use `cmd phase_runner_where` to display coordinates.

See build-status.json, render-placement-proof.json and runtime-validation.json for evidence. Full-detail 0.1.27 remains archived for rollback.
''',encoding='utf-8')
    if status.get('tunnel_collision_repair'):
        c=status['tunnel_collision_repair'];b=status['tunnel_render_detail']['budget']
        (output/'README.md').write_text(f'''# Phase Runner Northstar preview 0.1.30

Restart Northstar and load `map mp_phase_runner_preview`.

Both large tunnel models now use their full original LOD0 meshes without simplification. Portal frames use unsimplified LOD1. Other props retain the render settings from 0.1.29, which the user confirmed show every restored object without pop-in. All meshes together use {b['native_padded_indices']:,} of {b['world_index_capacity']:,} draw indices, leaving at least 15% capacity headroom.

Invisible world clip/end-cap surfaces are opened only inside the authored portal apertures. {c['modified_world_triangles']} tool-material collision triangles are cut at those openings; their exterior portions are retained. The 26 portal-frame colliders follow the original visible metal frame triangles, while the energy disks remain nonsolid. All other world/model collision records, including the full tunnel floors and walls, remain byte-identical. Floors and sloped tunnel walls still collide.

Two new 80-unit-wide metal walkways follow the original pipe ring routes. Visible floor panels and collision use exactly the same triangles. The floors pass above decorative pipe fixtures and through the smaller overlapping rings, with approach ramps limited to a 35-degree gradient. The walkways are new Titanfall traversal adaptations; original tunnel meshes remain in place.

Engine contact and passage tests are recorded separately in runtime-validation.json. They sample player-sized movement; full client traversal and the appearance of this new tunnel detail need an in-game check. Original material/PBR approximations, layered terrain shading, final lighting and complete gameplay support remain unfinished.

Recovered textures, sky and the resident-texture STBSP catalog are included. Full spatial mip streaming is unfinished. Use `cmd phase_runner_where` to display and log coordinates of remaining gaps or barriers. The confirmed working 0.1.29 archive remains available for rollback.

See build-status.json, tunnel-collision-repair.json, render-placement-proof.json and runtime-validation.json for evidence.
''',encoding='utf-8')
    status['bsp_validation']=checks
    status['northstar_mod_packaged']=True
    (output/'build-status.json').write_text(json.dumps(status,indent=2))
    files={str(p.relative_to(output)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in output.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (output/'checksums.json').write_text(json.dumps(files,indent=2))
    print(json.dumps(checks,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bsp',type=Path)
    parser.add_argument('source_report',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    package(args.bsp,args.source_report,args.output)

