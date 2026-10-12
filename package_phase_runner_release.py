"""Package the renamed map and append targeted native catwalk movement checks."""
import json,shutil,struct,sys
from pathlib import Path
from build_phase_runner_catwalks import ROOT,TARGET,np
from build_phase_runner_presentation import OUT as PRESENTATION,LANGUAGES
from package_northstar import package
PACKAGE=ROOT/'northstar/PhaseRunner.CatwalkRelease'

def probe_script(routes,details):
    floors=[];rails=[];walks=[]
    for r,d in zip(routes,details):
        p=np.array(r['points']);station=np.array(d['rail_station_points']);side=np.array(d['rail_sides'])
        for q,s in zip(station,side):
            floors.append(dict(start=(q+[0,0,80]).tolist(),end=(q-[0,0,12]).tolist()))
            # Feet clear the sloped deck; the upper rail still intersects the hull.
            for sign in (-1,1):rails.append(dict(start=(q+[0,0,20]).tolist(),end=(q+s*sign*52+[0,0,20]).tolist()))
        for a,b in zip(p,p[1:]):
            n=int(np.ceil(np.linalg.norm(b-a)/8))
            for j in range(n):
                x=a+(b-a)*j/n;y=a+(b-a)*(j+1)/n
                z=max(x[2],y[2])+20
                walks.append(dict(start=[float(x[0]),float(x[1]),float(z)],end=[float(y[0]),float(y[1]),float(z)],floor_end=(y-[0,0,8]).tolist()))
    text='\nvoid function PhaseRunner_CatwalkChecks()\n{\n';counts={}
    for name,probes,hull,hit in (('floor',floors,False,True),('rail',rails,True,True),('route',walks,True,False),('route_floor',[dict(start=w['end'],end=w['floor_end']) for w in walks],True,True)):
        vectors=lambda key:', '.join('< '+', '.join(f'{v:.6f}' for v in p[key])+' >' for p in probes)
        text+='\t{\n\t\tarray<vector> starts = [ '+vectors('start')+' ]\n\t\tarray<vector> ends = [ '+vectors('end')+' ]\n\t\tint passed = 0\n'
        text+='\t\tfor ( int i = 0; i < starts.len(); i++ )\n\t\t{\n'
        trace='TraceHull( starts[i], ends[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )' if hull else 'TraceLine( starts[i], ends[i], null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )'
        condition='result.fraction < 1.0 && !result.startSolid && !result.allSolid' if hit else 'result.fraction == 1.0 && !result.startSolid && !result.allSolid'
        if name=='route':
            text+='\t\t\tTraceResults reverse = TraceHull( ends[i], starts[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n'
            condition+=' && reverse.fraction == 1.0 && !reverse.startSolid && !reverse.allSolid'
        text+='\t\t\tTraceResults result = '+trace+'\n\t\t\tif ( '+condition+' )\n\t\t\t\tpassed++\n'
        text+='\t\t\telse\n\t\t\t\tprintl( "Phase Runner catwalk '+name+' failure " + i + ": fraction=" + result.fraction + " startSolid=" + result.startSolid )\n\t\t}\n'
        text+='\t\tprintl( "Phase Runner catwalk '+name+' checks: " + passed + "/" + starts.len() + " passed" )\n\t}\n';counts[name]=len(probes)
    text+='}\n'
    return text,dict(counts=counts,floor_probes=floors,rail_probes=rails,route_probes=walks)

def build():
    status=json.loads(TARGET.with_name('source-build.json').read_text());presentation=json.loads((PRESENTATION/'presentation.json').read_text())
    status['map_presentation']=presentation
    custom,probes=probe_script(status['catwalk_release']['routes'],status['catwalk_release']['catwalk_details']);status['catwalk_native_probes']=probes
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    package(TARGET,TARGET.with_name('source-build.json'),PACKAGE)
    mod=json.loads((PACKAGE/'mod.json').read_text());mod['Localisation']=['resource/phase_runner_%language%.txt'];(PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    resource=PACKAGE/'mod/resource';resource.mkdir(parents=True,exist_ok=True)
    for f in (PRESENTATION/'resource').iterdir():shutil.copy2(f,resource/f.name)
    paks=PACKAGE/'paks';shutil.copy2(PRESENTATION/'build/phase_runner_presentation.rpak',paks/'phase_runner_presentation.rpak')
    config=json.loads((paks/'rpak.json').read_text());config['Aliases']['mp_phase_runner_loadscreen.rpak']='phase_runner_presentation.rpak'
    config['Postload']['phase_runner_presentation.rpak']='common.rpak';(paks/'rpak.json').write_text(json.dumps(config,indent=2))
    script=PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut';text=script.read_text();marker='\t\tthread PhaseRunnerPreview_TestStatus()\n'
    if marker not in text:raise ValueError('Runtime test hook missing')
    script.write_text(text.replace(marker,marker+'\t\tPhaseRunner_CatwalkChecks()\n')+custom)
    shutil.copy2(PRESENTATION/'presentation.json',PACKAGE/'presentation.json');shutil.copy2(TARGET.with_name('catwalks.json'),PACKAGE/'catwalks.json')
    print(json.dumps(dict(version=mod['Version'],map_name=TARGET.stem,catwalk_native_checks=probes['counts'],loading_artwork=presentation['art_source'],localization_languages=list(LANGUAGES)),indent=2),flush=True)

if __name__=='__main__':build()
