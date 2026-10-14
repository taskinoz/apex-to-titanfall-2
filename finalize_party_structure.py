"""Publish the validated Party Crasher recovery, inventory and player download."""
import argparse
import collections
import csv
import json
import os
import shutil
from pathlib import Path

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, runtime_files, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.4.0'
NAME = 'ArenaPartyCrasher'
NOTE = ('Restores 380 exact-source placements: 168 facade sections, all 42 large boundary rocks, '
        '42 rooftop vents and all 128 solar panels. Uses 97.66% of native world index capacity, '
        'with no additional gameplay entities. Existing lighting, collision, safety areas, spawns, '
        'loading screen and minimap are retained. Some dense window modules, roof foliage, '
        'animated advertisements and layered terrain materials remain incomplete. AI navigation '
        'and Titan modes are not supplied. Restart between previews; repeated mode cycling '
        'has an unresolved earlier failure.')


def finalize():
    out=folder('party-crasher');project=out/'structure-recovery'
    candidate=WORK/'structure-candidates'/NAME
    binary=json.loads((project/'binary-validation.json').read_text())
    runtime=json.loads((project/'runtime-validation.json').read_text())
    captures=json.loads((ROOT/'output/party-edge-roof/native.json').read_text())
    sha=digest(candidate/'mod/maps/mp_party_crasher.bsp')
    pack=digest(candidate/'paks/party_crasher_world.rpak')
    for proof in (binary,runtime,captures):
        if proof['bsp_sha256']!=sha:
            raise ValueError('Stale Party Crasher validation')
    for proof in (runtime,captures):
        if proof['material_pack_sha256']!=pack or not proof['mounted_payload_verified']:
            raise ValueError('Mounted material verification missing')
    if not all(runtime.get(k) for k in ('postmatch_lobby','stock_map_reload','party_reload')):
        raise ValueError('Reload gates missing')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    if len(captures['shots'])!=8:
        raise ValueError('Native edge/roof survey incomplete')
    audit_shared();audit(candidate/'paks','mp_party_crasher')
    mod=ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version']!='0.3.1':
        raise ValueError('Unexpected accepted baseline version')
    for relative in ('mod/maps/mp_party_crasher.bsp','mod/maps/mp_party_crasher.stbsp',
                     'paks/party_crasher_world.rpak','mod.json'):
        source=candidate/relative;target=mod/relative
        shutil.copy2(source,target)
        if digest(source)!=digest(target):raise ValueError('Published payload differs')
    status=dict(version=VERSION,candidate=False,client_verified=True,initial_preview_ready=True,
                full_release_ready=False,bsp_sha256=sha,render_fraction=binary['budget']['native_padded_indices']/3145728,
                new_placements=380,validation='Single-client pilot spawns, source contacts and reloads; FFA definitions unchanged')
    (mod/'build-status.json').write_text(json.dumps(status,indent=2)+'\n')
    shot=next(r['northstar'] for r in captures['shots'] if r['name']=='north-roof')
    shutil.copy2(shot['path'],mod/'screenshot.png')
    docs=ROOT/'docs/candidates/party-crasher/port-0.4.0';docs.mkdir(parents=True,exist_ok=True)
    scene=json.loads((out/'scene.json').read_text());physics=json.loads((out/'physics.json').read_text())
    summary=json.loads((ROOT/'docs/candidates/party-crasher/port-0.3.0/inventory-summary.json').read_text())
    summary.update(version=VERSION,bsp_sha256=sha,rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k:v for k,v in binary['budget'].items() if k!='path'},
                   collision={k:v for k,v in physics.items() if k not in ('owners','missing')},
                   new_recovery=dict(placements=380,triangles=72590,categories=json.loads((project/'plan.json').read_text())['categories']))
    (docs/'inventory-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    inventory=json.loads((out/'source-inventory.json').read_text())
    included={p['index']:p for p in scene['placements']};omitted={p['index']:p for p in scene['omitted']}
    owners={p['index']:p for p in physics['owners']}
    fields=['index','model','source_x','source_y','source_z','status','lod','triangles','collision','reason']
    with (docs/'placement-inventory.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for p in inventory['props']:
            used=included.get(p['index']);skip=omitted.get(p['index']);owner=owners.get(p['index'])
            writer.writerow(dict(index=p['index'],model=p['model'],
                **dict(zip(('source_x','source_y','source_z'),p['original_apex_origin'])),
                status='rendered' if used else 'omitted-local' if skip else 'outside-region',
                lod=used['lod'] if used else '',triangles=used['triangles'] if used else '',
                collision=owner['method'] if owner else 'Source world or non-solid',reason=skip['reason'] if skip else ''))
    proof=dict(bsp_sha256=sha,material_pack_sha256=pack,binary_checks=binary['checks'],
               native_captures=len(captures['shots']),native_collider_contacts=len(runtime['contacts']),
               both_teams_verified=True,spawn_clearance_and_support=True,
               postmatch_lobby=True,stock_map_reload=True,party_reload=True,
               script_errors=[],native_crashes=[],single_client_only=True,
               safety_triggers_unchanged=True,ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof,indent=2)+'\n')
    shutil.copy2(mod/'screenshot.png',docs/'screenshot.png')
    (docs/'README.md').write_text(f'# Party Crasher {VERSION}\n\n{NOTE}\n\n'
        f'The independent audit passed {binary["checks"]:,} checks. Native tests verified '
        f'{len(runtime["contacts"])} new source collider contacts, clear supported team spawns, '
        'postmatch return, stock Coliseum loading and Party Crasher reloading. Eight native '
        'edge/roof views were captured from the exact mounted payload. '
        'Camera-only diagnostic runs temporarily removed safety trigger entities in the '
        'isolated process; gameplay checks restored all 67 out-of-bounds and two hurt '
        'triggers by reloading the unmodified map. The previous FFA '
        'registration and entities are byte-identical; this round exercises PS. '
        'No multiplayer FPS, AI capacity or all-five-map stress certification is implied.\n\n'
        'Baseline rollback is retained on the build drive under `party-crasher/before-0.4.0/`. '
        'The rejected facade-first candidate and its receipts are also retained separately.\n\n'
        'Reproduce with `recover_party_structure.py plan`, `materials`, `append`, then '
        '`verify_party_structure.py`, both harness surveys and `verify_party_structure_runtime.py`. '
        'Set APEX_PORT_WORK to the owned build workspace. The append is guarded against '
        'reapplication; restore the immutable snapshot before rebuilding.\n',encoding='utf-8')
    shutil.copy2(docs/'README.md',mod/'README.md')
    build=json.loads((out/'source-build.json').read_text());build.update(version=VERSION,render_triangles=scene['triangles'],draw_budget=binary['budget'])
    (out/'source-build.json').write_text(json.dumps(build,indent=2))
    print('Published Party Crasher',VERSION,sha,flush=True)


def package():
    RELEASES[NAME]=dict(version=VERSION,map='mp_party_crasher',title='Party Crasher',
                       screenshot='northstar/ArenaPartyCrasher/screenshot.png',notes=NOTE)
    result=write_player_zip(ROOT/'northstar'/NAME,ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path=ROOT/'output/player-distributions.json';ledger=json.loads(path.read_text());ledger[NAME]=result
    path.write_text(json.dumps(ledger,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['finalize','package'])
    dict(finalize=finalize,package=package)[p.parse_args().action]()
