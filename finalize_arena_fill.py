"""Promote scenery candidates only after native scene, gameplay and reload checks."""
import csv
import json
import shutil
from pathlib import Path

from build_arena_fill import CONFIG, OUT, ROOT, VERSIONS
from package_player_mods import digest, runtime_files


def finalize():
    modes=json.loads((OUT/'mode-validation.json').read_text())
    expected={('mp_arena_composite',m) for m in ('ps','ffa')} | {('mp_phase_runner',m) for m in ('tdm','ps','ctf','cp','fastball','aitdm')}
    assert {(r['map'],r['mode']) for r in modes}==expected
    assert all(not r['logs']['script_errors'] and not r['logs'].get('native_crashes') for r in modes)
    assert all(all(p['clear'] and p['supported'] for p in r['live_spawn_checks']) for r in modes if r['map']=='mp_phase_runner')
    reload=json.loads((OUT/'reload-validation.json').read_text())
    assert reload['pid_before']==reload['pid_after'] and not reload['logs']['script_errors'] and not reload['logs'].get('native_crashes')
    assert reload['postmatch']['level']=='mp_lobby'
    # Check both complete candidates before changing either working package.
    for ident,config in CONFIG.items():
        result=json.loads((OUT/ident/'result.json').read_text())
        runtime=json.loads((OUT/ident/'runtime/capture-validation.json').read_text())
        candidate=OUT/'candidates'/config['package']
        assert all(digest(candidate/name)==sha for name,sha in runtime['staged_sha256'].items())
        assert all(r['bsp_sha256']==result['bsp_sha256'] for r in modes if r['map']==config['map'])
        assert next(r for r in reload['reloads'] if r['map']==config['map'])['bsp_sha256']==result['bsp_sha256']
    doc=ROOT/'docs/scenery-fill';doc.mkdir(exist_ok=True)
    summaries={}
    for ident,config in CONFIG.items():
        work=OUT/ident;result=json.loads((work/'result.json').read_text())
        checks=json.loads((work/'binary-validation.json').read_text())
        assert checks['checks']==len(checks['passed'])==(142 if ident=='phase-runner' else 147)
        runtime=json.loads((work/'runtime/capture-validation.json').read_text())
        assert not runtime['logs']['script_errors'] and len(runtime['angle_sweeps'])==8
        assert len(runtime['matched_source_views'])==(12 if ident=='drop-off' else 11)
        assert len(runtime['team_starts'])==2 and .97<=result['world_fraction']<=.975
        assert len(runtime['new_prop_collision_contacts'])==(6 if ident=='phase-runner' else 30)
        candidate=OUT/'candidates'/config['package'];target=ROOT/'northstar'/config['package']
        assert json.loads((candidate/'mod.json').read_text())['Version']==VERSIONS[ident]
        assert digest(candidate/'mod/maps'/(config['map']+'.bsp'))==result['bsp_sha256']
        assert runtime['staged_sha256']['mod/maps/'+config['map']+'.bsp']==result['bsp_sha256']
        assert all(r['bsp_sha256']==result['bsp_sha256'] for r in modes if r['map']==config['map'])
        assert next(r for r in reload['reloads'] if r['map']==config['map'])['bsp_sha256']==result['bsp_sha256']
        # The complete previous runtime remains in work/baseline and its release ZIP.
        for p in runtime_files(candidate):
            dest=target/p.relative_to(candidate);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest);assert digest(dest)==digest(p)
        result['native_runtime_verified']=True
        # The lighting helper's historical label says 30 for both maps.
        result['lighting']['existing_fixture_count']=30 if ident=='phase-runner' else 60
        result['lighting'].pop('static_sun_sky_and_existing_30_point_lights_baked',None)
        result['lighting']['static_sun_sky_and_existing_fixtures_baked']=True
        (work/'result.json').write_text(json.dumps(result,indent=2))
        contacts=[dict(source_index=r['index'],model=r['model'],expected_surface=r['expected_surface'],
                       fraction=r['trace']['data']['fraction']) for r in runtime['new_prop_collision_contacts']]
        budget={k:v for k,v in result['budget'].items() if k!='path'}
        local=16376 if ident=='phase-runner' else 6472
        rendered=result['source_placements_previously_rendered']+result['added_placements']
        proof=dict(version=VERSIONS[ident],map=config['map'],baseline_version=result['baseline_version'],
            bsp_sha256=result['bsp_sha256'],added_placements=result['added_placements'],
            local_source_placements=local,rendered_source_placements=rendered,remaining_local_placements=local-rendered,
            added_render_triangles=result['added_render_triangles'],added_collision_triangles=result['added_collision_triangles'],
            model_counts=result['model_counts'],world_fraction=result['world_fraction'],
            remaining_world_indices=result['remaining_world_indices'],static_batch_reserve=result['static_batch_reserve'],
            budget=budget,collision=result['collision'],lighting=result['lighting'],
            native_comparison_views=len(runtime['matched_source_views']),angle_checks=8,
            new_prop_collision_contacts=contacts,team_spawns_checked=[2,3],
            binary_validation=checks,native_mode_checks=[r['mode'] for r in modes if r['map']==config['map']],
            same_process_postmatch_and_reload=True,native_runtime_verified=True,dynamic_entities_added=0,new_portals=0,
            limitations=['Single-client initialization and hull tests do not establish multiplayer frame times.',
                        'AI navigation and live Attrition waves are not added or validated.',
                        'World geometry reserve is separate from model, texture, dynamic entity and AI budgets.'])
        # Binary receipts use only check names/results; strip any local paths before publishing.
        def clean(value):
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('baseline','candidate','path','bsp')}
            if isinstance(value,list):return [clean(v) for v in value]
            return value
        proof['binary_validation']=clean(checks)
        (doc/(ident+'-validation.json')).write_text(json.dumps(proof,indent=2))
        (target/'scenery-fill-validation.json').write_text(json.dumps(proof,indent=2))
        translation=[-26000,-19000,0] if ident=='phase-runner' else [0,0,0]
        placements=[dict(p,original_apex_origin=[v-translation[i] for i,v in enumerate(p['source_origin'])]) for p in result['placements']]
        ledger=dict(version=VERSIONS[ident],baseline_version=result['baseline_version'],map=config['map'],
            source_to_target_translation=translation,source_origin_frame='Target frame before ground adjustment; original_apex_origin is unshifted Apex world space.',
            total_local=local,previously_rendered=result['source_placements_previously_rendered'],
            newly_rendered=result['added_placements'],now_rendered=rendered,remaining_local=local-rendered,
            placements=placements)
        (doc/(ident+'-recovered-placements.json')).write_text(json.dumps(ledger,indent=2))
        inventory=ROOT/'docs'/('conversion' if ident=='phase-runner' else 'composite')/'missing-static-placements.csv'
        with inventory.open(newline='') as stream:
            reader=csv.DictReader(stream);columns=reader.fieldnames;omitted=list(reader)
        index_key='source_index' if ident=='phase-runner' else 'index'
        recovered={p['index'] for p in result['placements']}
        assert recovered<={int(r[index_key]) for r in omitted}
        remaining=[r for r in omitted if int(r[index_key]) not in recovered]
        with (doc/(ident+'-remaining-placements.csv')).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(remaining)
        (target/'SCENERY_FILL.md').write_text((ROOT/'docs/arena-scenery-fill-2026-10-13.md').read_text().replace('(scenery-fill/','(../../docs/scenery-fill/'))
        old=(target/'README.md').read_text()
        prefix=f"# {('Phase Runner' if ident=='phase-runner' else 'Drop-Off')} {VERSIONS[ident]} for Northstar\n\nAdds {result['added_placements']:,} original scenery placements. Uses {result['world_fraction']*100:.2f}% of the native world index capacity with no added dynamic entities. Existing minimaps, gameplay, collision exclusions and tunnel visibility are preserved. See SCENERY_FILL.md for measured budgets and validation. AI navigation remains incomplete.\n\n## Previous release notes\n\n"
        if not old.startswith(prefix):(target/'README.md').write_text(prefix+old)
        if ident=='phase-runner':
            (target/'REMAINING_OBJECTS.md').write_text(f'''# Remaining source objects — {VERSIONS[ident]}

{rendered:,} of {local:,} local arena placements are rendered; {local-rendered:,} remain omitted.
Another 486 placements lie outside the imported arena. This pass adds
{result['added_placements']:,} placements to the historical 5,425-object baseline.

The complete historical source inventory is in `docs/conversion/`.
Merge the added source indices in `docs/scenery-fill/phase-runner-recovered-placements.json`
when interpreting that baseline's omissions. See `SCENERY_FILL.md` for current
native rendering capacity, collision and gameplay checks.
''')
        summaries[ident]=proof
    registry=ROOT/'site/maps.json';catalogue=json.loads(registry.read_text())
    notes={
        'phase-runner':'Adds 432 source scenery placements: supported ground plants, flowers, small snow rocks and power equipment. Uses 97.04% of native world index capacity with no added dynamic entities. Preserves minimap, displays, paint, lighting, team modes and catwalks. AI navigation and some layered/animated materials remain incomplete.',
        'drop-off':'Adds 366 source placements: conduits, clamps, tanks, crates, furniture and structural details. Uses 97.06% of native world index capacity with no added dynamic entities. Preserves minimap, Northstar banners, displays, paint, lighting, safety volumes and ziplines. Some scenery and animated materials remain incomplete. Intro and evac are disabled.'}
    for row in catalogue['maps']:row['notes']=notes[row['id']]
    registry.write_text(json.dumps(catalogue,indent=2))
    readme=ROOT/'README.md';text=readme.read_text();old_start=text.index('The investigation history below')
    readme.write_text('''# Apex to Titanfall 2 map ports

Current builds: **Phase Runner 1.6.0** and **Drop-Off 0.10.0**. Restore
432 and 366 source scenery placements respectively, reaching 97.04% and
97.06% of the native world index capacity. No dynamic entities are added.
Existing minimaps, lighting, gameplay, collision exclusions and catwalks remain.
AI navigation is still incomplete. See [budgets, recovery and validation](docs/arena-scenery-fill-2026-10-13.md),
including the initial test failures and the scope of subsequent native checks.

- [Saved map comparison site](site/dist/index.html): 23 matching wider-area
  views of these builds, with earlier snapshots retained.
- [Site source and release export](site/README.md).
- [Repository contents and local dependencies](REPOSITORY.md).
- [Northstar harness](test-harness/README.md) and [R5R harness](r5-harness/README.md).
- [Native minimap conversion](docs/arena-minimaps-2026-10-13.md).
- [Northstar banners and Apex displays](docs/banner-display-textures-2026-10-12.md).

Clean downloads: `output/PhaseRunner-1.6.0-Northstar.zip` and
`output/ArenaComposite-0.10.0-Northstar.zip`. Previous 1.5.0 / 0.9.0 ZIPs,
runtime snapshots and installed copies remain available for rollback.
The comparison site is local and has not been deployed.

'''+text[old_start:])
    (OUT/'promotion.json').write_text(json.dumps({k:dict(version=v['version'],bsp_sha256=v['bsp_sha256']) for k,v in summaries.items()},indent=2))
    print('Promoted Phase Runner 1.6.0 and Drop-Off 0.10.0; previous runtime snapshots retained.')
    return summaries


if __name__=='__main__':finalize()
