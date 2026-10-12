from pathlib import Path
p=Path('package_northstar.py');s=p.read_text();needle="    (scripts/'_phase_runner_preview.nut').write_text("
insert='''    if status.get('prop_physics'):
        new_probes=[p for p in status['collision_probes'] if p['kind'] in ('rock','pipe','portal')]
        vectors=lambda key: ', '.join('< '+', '.join(f'{v:.6f}' for v in p[key])+' >' for p in new_probes)
        probe_script += ('\\t\\tarray<vector> propStarts = [ '+vectors('start')+' ]\\n'
            '\\t\\tarray<vector> propEnds = [ '+vectors('end')+' ]\\n'
            '\\t\\tint hullHits = 0\\n'
            '\\t\\tfor ( int i = 0; i < propStarts.len(); i++ )\\n\\t\\t{\\n'
            '\\t\\t\\tTraceResults result = TraceHull( propStarts[i], propEnds[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\\n'
            '\\t\\t\\tif ( result.fraction < 1.0 || result.startSolid || result.allSolid )\\n\\t\\t\\t\\thullHits++\\n'
            '\\t\\t\\tprintl( "Phase Runner prop hull probe " + i + ": fraction=" + result.fraction + " startSolid=" + result.startSolid )\\n\\t\\t}\\n'
            '\\t\\tprintl( "Phase Runner prop hull probes: " + hullHits + "/" + propStarts.len() + " hit" )\\n')
'''
s=s.replace(needle,insert+needle);p.write_text(s)
p=Path('finalize_textured_preview.py');s=p.read_text();s=s.replace("    if 'Phase Runner collision probes: 24/24 hit' not in log:","    status = json.loads((package/'build-status.json').read_text())\n    collision_count=len(status['collision_probes'])\n    if f'Phase Runner collision probes: {collision_count}/{collision_count} hit' not in log:")
s=s.replace('sample_collision_hits=24,sample_collision_count=24','sample_collision_hits=collision_count,sample_collision_count=collision_count')
s=s.replace("'draw_regression_repair'):","'draw_regression_repair','spatial_draw_sections','prop_physics'):")
needle="    feedback_path = ROOT/f'output/phase-runner/client-feedback-{version}.json'"
s=s.replace(needle,'''    if status.get('prop_physics'):
        count=sum(p['kind'] in ('rock','pipe','portal') for p in status['collision_probes'])
        if f'Phase Runner prop hull probes: {count}/{count} hit' not in log:raise ValueError('Prop hull evidence incomplete')
        evidence['prop_hull_hits']=count
        evidence['prop_hull_count']=count
        evidence['previous_user_feedback']='0.1.19 looks better but rock/prop pop-in and missing rock/pipe collision remain. 0.1.20 adds smaller spatial draw sections and native collision to recovered props. GPU rendering and player movement remain unverified.'
''' + needle);p.write_text(s)
