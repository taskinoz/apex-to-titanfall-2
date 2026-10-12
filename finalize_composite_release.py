"""Record omissions and reproducible evidence; package a separate Northstar mod."""
import argparse, collections, csv, hashlib, json, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/composite'
DOC = ROOT / 'docs/composite'
MOD = ROOT / 'northstar/ArenaComposite'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def document(version=None):
    version=version or json.loads((OUT/'source-build.json').read_text())['version']
    source = json.loads((OUT/'source-inventory.json').read_text())
    scene = json.loads((OUT/'scene.json').read_text())
    physics = json.loads((OUT/'physics.json').read_text())
    materials = json.loads((OUT/'materials/mapping.json').read_text())
    chosen = {p['index']: p for p in scene['placements']}
    omitted = {p['index']: p for p in scene['omitted']}
    local = {p['index'] for p in json.loads((OUT/'asset-audit.json').read_text())['props']}
    inventory = []
    for p in source['props']:
        row = {k: p[k] for k in ('index','model','origin','angles','scale','solid')}
        if p['index'] in chosen:
            row.update(status='Included', lod=chosen[p['index']]['lod'])
        elif p['index'] in omitted:
            row.update(status=omitted[p['index']]['reason'])
        elif p['index'] in local:
            row.update(status='No rendered sections after atmosphere / glow filters')
        else:
            row.update(status='Excluded remote origin / menu or backdrop region')
        inventory.append(row)
    counts = collections.Counter(p['status'] for p in inventory)
    entities = {name: dict(collections.Counter(e.get('classname','unknown') for e in rows))
                for name,rows in source['entities'].items()}
    summary = dict(source_map='mp_rr_arena_composite',target_map='mp_arena_composite',
                   placements=dict(counts), collision_missing=physics['missing'],
                   missing_materials=materials['missing'], entity_classes=entities)
    (DOC/'inventory-summary.json').write_text(json.dumps(summary,indent=2))
    (DOC/'static-placement-inventory.json').write_text(json.dumps(inventory,indent=2))
    (DOC/'missing-collision.json').write_text(json.dumps(physics['missing'],indent=2))
    (DOC/'missing-materials.json').write_text(json.dumps(materials['missing'],indent=2))
    with (DOC/'missing-static-placements.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(('index','model','x','y','z','scale','source_solid','reason'))
        writer.writerows((p['index'],p['model'],*p['origin'],p['scale'],p['solid'],p['status'])
                        for p in inventory if p['status']!='Included')
    rows='\n'.join(f'| {name} | {count:,} |' for name,count in counts.items())
    mats='\n'.join(f'| `{name}` | {count:,} |' for name,count in materials['missing'].items())
    (DOC/'MISSING_CONTENT.md').write_text(f'''# Drop-Off {version} preview omissions

This inventory accounts for all {len(inventory):,} source static placements. The
local origin filter contains {scene['source_playable_props']:,}; it is a conversion
selection policy, not a statement about Apex's native playable bounds.

| Static placement status | Count |
| --- | ---: |
{rows}

Budget exclusions are recoverable source assets, but adding them indiscriminately
can overflow native all-visible draw submission. Lower author LODs and spatial
visibility would allow further recovery. No placements are silently relabeled
as successfully converted. The CSV lists all exclusions with source positions.

## Collision

{len(physics['missing'])} selected solid placements have no decoded source collision
shape: small cable stoppers, puddle decals and bamboo. `missing-collision.json`
names each source owner. Unsuitable guessed bounding boxes were not added.
World BVH and successfully recovered IRPS/BVH prop shapes are included.

## Materials with fallback

Counts are rendered source triangles; zero-count entries are unused catalogue
names. Missing entries use a plain neutral material, not an unrelated atlas.

| Source material | Triangles |
| --- | ---: |
{mats}

## Behaviour and visual approximations

Source scripted dynamic props, eight doors, movers/train nodes, audio,
particles, source UI surfaces and Apex arena gameplay are not reproduced. Inline
brush geometry is fixed; conditional or animated states are not simulated.
No CTF/Hardpoint objectives, Fastball setup or AI navigation is provided.
Intro and evac are disabled. Only the two source zipline pairs are converted to native Titanfall ziplines.
Temporary arena spawn covers are omitted; permanent room and roof clips remain. Source safety
volumes include 21 out-of-bounds areas and five hurt volumes.

The source photographic sky uses an approximate sphere mapping. Primary native
PBR channels and alpha masks are recovered, but vertex colours, layered materials,
animated displays and full source reflections remain incomplete. Texture caps
and lower author LODs visibly reduce detail. Lightmaps are coarse, spot lights
are point approximations and there is no bounced GI. Sixty local source lights
are selected from hundreds rather than preserving every light.
The reported development door cover is removed. The reported roof/window
opening still needs identification; no speculative pane has been added.

The package deliberately uses conservative all-visible cells. This avoids known
angular culling problems but needs performance testing with multiple players and
combat effects. Binary capacity checks do not prove stable frame times.
See `validation.json` for which runtime checks actually ran on this build.
''',encoding='utf-8')
    for name in ('engine-limits.json','binary-layouts.json','respawn_conversion_layouts.h'):
        shutil.copy2(ROOT/'docs/conversion'/name,DOC/name)
    return summary

def release(validation, make_zip):
    document()
    proof=json.loads(validation.read_text())
    build=json.loads((OUT/'source-build.json').read_text())
    build.update(client_verified=proof.get('final_client_verified',False),
                 lighting=json.loads((OUT/'lighting.json').read_text()),
                 validation=proof,version='0.4.0')
    build['collision']={k:v for k,v in json.loads((OUT/'physics.json').read_text()).items()
                        if k not in ('owners','missing')}
    build['build']['checks']['in_game_verified']=build['client_verified']
    build['streaming_sidecar']['client_load_verified']=build['client_verified']
    (OUT/'source-build.json').write_text(json.dumps(build,indent=2))
    from package_composite import package
    package()
    shutil.copy2(DOC/'README.md',MOD/'README.md')
    shutil.copytree(DOC,MOD/'docs',dirs_exist_ok=True)
    shutil.copy2(validation,MOD/'docs/validation.json')
    records={p.relative_to(MOD).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p))
             for p in sorted(MOD.rglob('*')) if p.is_file() and p.name!='checksums.json'}
    (MOD/'checksums.json').write_text(json.dumps(records,indent=2))
    if make_zip:
        target=ROOT/'output/ArenaComposite-0.4.0-Northstar.zip'
        from package_player_mods import write_player_zip
        write_player_zip(MOD,target)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--zip',action='store_true')
    args=parser.parse_args();release(args.validation,args.zip)
