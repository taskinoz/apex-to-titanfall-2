"""Publish gated initial Northstar previews, inventories and matched native comparisons locally."""
import argparse
import collections
import csv
import hashlib
import json
import shutil
from pathlib import Path
from new_arena_ports import CONFIG, ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip


def finalize(ident,make_zip=False):
    cfg=CONFIG[ident];work=folder(ident);source=WORK/'candidates'/cfg['package']
    sha=digest(source/'mod/maps'/(cfg['target']+'.bsp'))
    binary=json.loads((work/'binary-validation.json').read_text())
    captures=json.loads((work/'runtime/captures.json').read_text())
    gameplay=json.loads((work/'runtime/gameplay-validation.json').read_text())
    for proof in (binary,captures,gameplay):
        if proof['bsp_sha256']!=sha:raise ValueError('Stale validation: '+ident)
    if not captures.get('mounted_payload_verified'):raise ValueError('Mounted capture proof missing')
    if not gameplay['postmatch_lobby'] or not gameplay['stock_map_reload']:raise ValueError('Reload gates missing')
    if {m['mode'] for m in gameplay['modes']}!={'ps','ffa'}:raise ValueError('Pilot mode gates missing')
    for proof in (captures,gameplay):
        if proof['logs']['script_errors'] or proof['logs']['native_crashes']:raise ValueError('Native log failure')
    mod=ROOT/'northstar'/cfg['package'];docs=ROOT/'docs/candidates'/ident/'port-0.1.0'
    mod.mkdir(parents=True,exist_ok=True);docs.mkdir(parents=True,exist_ok=True)
    paths=[source/'mod.json',source/'paks/rpak.json',*source.glob('paks/*.rpak'),
           source/'mod/maps'/(cfg['target']+'.bsp'),source/'mod/maps'/(cfg['target']+'.stbsp'),
           *source.glob('mod/scripts/vscripts/*.nut'),*source.glob('mod/resource/*_*.txt'),
           source/'mod/resource/overviews'/(cfg['target']+'.txt')]
    for p in paths:
        dest=mod/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    scene=json.loads((work/'scene.json').read_text());physics=json.loads((work/'physics.json').read_text())
    materials=json.loads((work/'materials/mapping.json').read_text());safety=json.loads((work/'source-gameplay.json').read_text())
    placements={p['index']:p for p in scene['placements']};omitted={p['index']:p for p in scene['omitted']}
    inventory=json.loads((work/'source-inventory.json').read_text());owners={p['index']:p for p in physics['owners']}
    with (docs/'placement-inventory.csv').open('w',newline='',encoding='utf-8') as stream:
        fields=['index','model','source_x','source_y','source_z','target_x','target_y','target_z','status','lod','triangles','collision','reason']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for p in inventory['props']:
            selected=placements.get(p['index']);skip=omitted.get(p['index']);owner=owners.get(p['index'])
            status='rendered' if selected else 'omitted-local' if skip else 'no-supported-sections' if p['in_region'] else 'outside-region'
            collision='world/source-owned or source-nonsolid'
            if owner:collision=owner['method'] if owner['brushes'] or owner['headers'] else 'no recovered shape'
            writer.writerow(dict(index=p['index'],model=p['model'],**dict(zip(('source_x','source_y','source_z'),p['original_apex_origin'])),
                **dict(zip(('target_x','target_y','target_z'),p['origin'])),status=status,lod=selected['lod'] if selected else '',
                triangles=selected['triangles'] if selected else '',collision=collision,reason=skip['reason'] if skip else ''))
    budget={k:v for k,v in binary['budget'].items() if k!='path'}
    summary=dict(map=cfg['target'],source=cfg['source'],version='0.1.0',bsp_sha256=sha,
        source_to_target_offset=cfg['offset'],source_static_placements=scene['source_static_placements'],
        rendered_static_placements=scene['props'],omitted_local_placements=len(scene['omitted']),
        outside_region=scene['source_outside_region'],
        no_supported_sections=sum(p['in_region'] and p['index'] not in placements and p['index'] not in omitted for p in inventory['props']),
        omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
        budget=budget,collision={k:v for k,v in physics.items() if k not in ('owners','missing')},
        missing_prop_collision=[dict(index=p['index'],model=p['model']) for p in physics['missing']],
        fallback_materials={k:v for k,v in materials['missing'].items() if v},source_safety_volumes=safety['added_counts'],
        source_entity_classes=dict(collections.Counter(e['classname'] for e in inventory['entities'])))
    proof=dict(bsp_sha256=sha,binary_checks=binary['checks'],mounted_native_captures=True,
        modes=[dict(mode=m['mode'],live_spawns=len(m['live']['liveSpawns']),
                    clear_supported=all(p['clear'] and p['supported'] for p in m['live']['liveSpawns']),
                    floor_contacts=len(m['floor_contacts']),angle_captures=len(m['angle_captures'])) for m in gameplay['modes']],
        postmatch_lobby=True,stock_map_reload=True,script_errors=[],native_crashes=[],limitations=gameplay['limitations'],
        known_failed_stress_check='A longer shared Overflow/Party Crasher session crashed during repeated FFA-to-PS cycling. Cause unresolved; clean individual checks do not erase this failure.')
    (docs/'inventory-summary.json').write_text(json.dumps(summary,indent=2));(docs/'validation.json').write_text(json.dumps(proof,indent=2))
    screenshot=docs/'screenshot.png';shutil.copy2(captures['views'][0]['northstar']['path'],screenshot)
    percent=budget['native_padded_indices']/budget['world_index_capacity']*100
    notes=f"Initial native preview for Pilots vs Pilots and Free For All. Recovers {scene['props']:,} static placements and uses {percent:.2f}% of this engine's measured per-view world index capacity."
    readme=f'''# {cfg['name']} 0.1.0 — initial Northstar preview

Extract `{cfg['package']}` into `Titanfall2/R2Northstar/mods/`, enable it and restart.
Every player needs the same version. Launch with `mp_gamemode ps` followed by
`map {cfg['target']}` (or choose `ffa` for Free For All).

{notes}

Native checks cover both pilot modes, supported/clear spawns, both team start
selections in PS, viewing angles near those starts, postmatch return to lobby,
and a stock-map reload. Tests used one local client; multiplayer performance
and balance are not established. Scenery is baked into native world meshes.
A longer shared Overflow/Party Crasher session crashed during repeated mode
changes. The cause is unresolved. Restart between new preview maps and avoid
repeated mode cycling in the same process.

This is less complete than Phase Runner and Drop-Off. Decorations, dense
foliage, distant scenery and some materials are missing. Authored lower LODs,
1024-pixel texture caps, approximate sky mapping, coarse direct lightmaps and
point approximations of spot lights reduce fidelity. Animated/emissive source
materials use static approximations. Apex interactions, weapon stations,
training dummies, AI navigation, Titan modes, CTF/Hardpoint/Fastball objectives,
intro and evac are not supplied. Source safety volumes are retained, but each
hazard has not been physically exercised. The Firing Range minimap is generated;
the arena minimaps use original overview artwork. Enable only the preview map
you are testing to limit resident texture packs; all five ports together have
not been validated. Original game assets remain their creators' work.

Detailed counts and every omitted source placement are recorded in the repo's
`docs/candidates/{ident}/port-0.1.0/`.
'''
    (mod/'README.md').write_text(readme,encoding='utf-8');(docs/'README.md').write_text(readme,encoding='utf-8')
    (mod/'build-status.json').write_text(json.dumps(dict(version='0.1.0',candidate=False,client_verified=True,
        initial_preview_ready=True,full_release_ready=False,bsp_sha256=sha,validated_modes=['ps','ffa']),indent=2))
    shutil.copy2(screenshot,mod/'screenshot.png')
    gallery=ROOT/'output/new-port-comparisons'/ident;gallery.mkdir(parents=True,exist_ok=True)
    route=dict(title=cfg['name']+' initial native preview comparison',source_map=cfg['source'],target_map=cfg['target'],
               source_offset=[-v for v in cfg['offset']],mode='ps',shots=[])
    pairs=[]
    for i,r in enumerate(captures['views']):
        name='view-'+str(i);camera=r['source']['camera'];target=[v+d for v,d in zip(camera['origin'],cfg['offset'])]
        shot=dict(name=name,origin=target,angles=camera['angles'],fov=camera['fov'],settle=3);route['shots'].append(shot)
        pair=dict(name=name,route_camera=shot)
        for engine,meta in (('r5r',r['source']),('northstar',r['northstar'])):
            dest=gallery/(name+'-'+engine+'.png');shutil.copy2(meta['path'],dest)
            if digest(dest)!=meta['sha256']:raise ValueError('Comparison capture hash mismatch')
            pair[engine]={k:meta[k] for k in ('width','height','captured','sha256')};pair[engine]['gallery_path']=dest.name
        pairs.append(pair)
    (gallery/'comparison.json').write_text(json.dumps(dict(route=route,pairs=pairs),indent=2))
    (ROOT/'r5-harness/routes'/(ident+'-initial-preview.json')).write_text(json.dumps(route,indent=2))
    RELEASES[cfg['package']]=dict(version='0.1.0',map=cfg['target'],title=cfg['name'],
        screenshot=str(screenshot.relative_to(ROOT)),notes=notes)
    # Keep detailed ledgers out of player ZIPs; the short README includes limits.
    RELEASES[cfg['package']]['notes']=notes+' Initial preview: missing scenery/materials and Apex interactions; no AI, Titan modes, intro or evac. A longer shared Overflow/Party Crasher session crashed on repeated mode changes; the cause is unresolved. Enable one new preview at a time and restart between maps. The complete five-map bundle has not been tested.'
    if make_zip:
        release=write_player_zip(mod,ROOT/'output'/(cfg['package']+'-0.1.0-Northstar.zip'))
        ledger=ROOT/'output/player-distributions.json';releases=json.loads(ledger.read_text()) if ledger.exists() else {}
        releases[cfg['package']]=release;ledger.write_text(json.dumps(releases,indent=2))
    print(ident,'initial preview finalized',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=[*CONFIG,'all']);p.add_argument('--zip',action='store_true')
    a=p.parse_args()
    for ident in CONFIG if a.map=='all' else [a.map]:finalize(ident,a.zip)
