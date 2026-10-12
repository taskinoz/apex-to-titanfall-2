"""Generate engine floor-following sweeps across every authored tunnel ring."""
import json
import numpy as np
from pathlib import Path
from stage_prop_geometry import rotation
ROOT=Path(__file__).resolve().parent

def add(stage=ROOT/'northstar/PhaseRunner.TunnelSweepLab'):
    rings=[p for p in json.loads((ROOT/'output/phase-runner/static-props.json').read_text()) if p['in_arena'] and 'wraith_tt_portal_large' in p['model']]
    def vec(v):return '< '+', '.join(f'{x:.6f}' for x in v)+' >'
    starts=[];ends=[];bottoms=[]
    for p in rings:
        m=np.array(rotation(p['angles']));center=np.array(p['origin'])+m@np.array([0,0,-193.5])*p['scale'];depth=250*p['scale']+24
        bottoms.append(center);starts.append(center-m[:,1]*depth);ends.append(center+m[:,1]*depth)
    text='\n\t\tarray<vector> passageStarts = [ '+', '.join(map(vec,starts))+' ]\n'
    text+='\t\tarray<vector> passageEnds = [ '+', '.join(map(vec,ends))+' ]\n'
    text+='\t\tarray<vector> passageCenters = [ '+', '.join(map(vec,bottoms))+' ]\n'
    text+='''\t\tfor ( int i=0; i<passageStarts.len(); i++ )
\t\t{
\t\t\tvector start = passageStarts[i]
\t\t\tvector end = passageEnds[i]
\t\t\tvector middle = passageCenters[i]
\t\t\tTraceResults a = TraceHull( start+<0,0,64>, start-<0,0,96>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tTraceResults b = TraceHull( end+<0,0,64>, end-<0,0,96>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tTraceResults c = TraceHull( middle+<0,0,64>, middle-<0,0,96>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tfloat floor = max( max( a.endPos.z, b.endPos.z ), c.endPos.z ) + 4
\t\t\tstart.z = floor
\t\t\tend.z = floor
\t\t\tTraceResults forward = TraceHull( start, end, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tTraceResults reverse = TraceHull( end, start, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tprintl( "Phase Runner passage " + i + ": floor=" + floor + " floorHits=" + a.fraction + "," + b.fraction + "," + c.fraction + " forward=" + forward.fraction + " reverse=" + reverse.fraction + " solid=" + forward.startSolid + "," + reverse.startSolid + " normal=" + forward.surfaceNormal + " end=" + forward.endPos )
\t\t}
'''
    path=stage/'mod/scripts/vscripts/_phase_runner_preview.nut';source=path.read_text();marker='\t\tprintl( "Phase Runner local test: server reporting disabled after startup config." )\n'
    if 'array<vector> passageStarts' in source:raise ValueError('Duplicate test block')
    path.write_text(source.replace(marker,marker+text))
    (ROOT/'logs/tunnel-floor-sweep-rings.json').write_text(json.dumps(rings,indent=2))
    print('Passage checks',len(rings)*2)

if __name__=='__main__':add()
