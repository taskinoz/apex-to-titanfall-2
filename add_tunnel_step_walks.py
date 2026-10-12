"""Test normal player step-height movement through each reported obstruction."""
import json
from pathlib import Path
import numpy as np
from stage_prop_geometry import rotation
from audit_reported_tunnel_barriers import POINTS
ROOT=Path(__file__).resolve().parent

def add(stage=ROOT/'northstar/PhaseRunner.TunnelSweepLab'):
    props=json.loads((ROOT/'output/phase-runner/static-props.json').read_text());rings=[p for p in props if p['in_arena'] and 'wraith_tt_portal_large' in p['model']]
    def vec(v):return '< '+', '.join(f'{x:.6f}' for x in v)+' >'
    starts=[];ends=[]
    for point in POINTS:
        p=min(rings,key=lambda p:np.linalg.norm(np.array(point)-p['origin']));d=np.array(rotation(p['angles']))[:,1]
        for sign in (-1,1):starts.append(np.array(point)-d*64*sign);ends.append(np.array(point)+d*64*sign)
    text='\n\t\tarray<vector> walkStarts = [ '+', '.join(map(vec,starts))+' ]\n'
    text+='\t\tarray<vector> walkEnds = [ '+', '.join(map(vec,ends))+' ]\n'
    text+='''\t\tfor ( int i=0; i<walkStarts.len(); i++ )
\t\t{
\t\t\tvector first = walkStarts[i]
\t\t\tTraceResults ground = TraceHull( first+<0,0,32>, first-<0,0,96>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tvector position = ground.endPos + <0,0,2>
\t\t\tbool clear = ground.fraction < 1 && !ground.startSolid
\t\t\tint steps = 0
\t\t\tfor ( int step=1; step<=16 && clear; step++ )
\t\t\t{
\t\t\t\tvector next = first + (walkEnds[i]-first) * (float(step)/16.0)
\t\t\t\tnext.z = position.z + 18
\t\t\t\tTraceResults rise = TraceHull( position, position+<0,0,18>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\t\tTraceResults across = TraceHull( position+<0,0,18>, next, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\t\tTraceResults down = TraceHull( next, next-<0,0,54>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\t\tclear = rise.fraction == 1 && !rise.startSolid && across.fraction == 1 && !across.startSolid && down.fraction < 1 && !down.startSolid
\t\t\t\tif ( clear ) { position = down.endPos + <0,0,2>; steps++ }
\t\t\t\telse printl( "Phase Runner walk obstruction " + i + ": step=" + step + " rise=" + rise.fraction + " across=" + across.fraction + " down=" + down.fraction + " solid=" + rise.startSolid + "," + across.startSolid + "," + down.startSolid + " normal=" + across.surfaceNormal + " end=" + across.endPos )
\t\t\t}
\t\t\tprintl( "Phase Runner step walk " + i + ": clear=" + clear + " steps=" + steps + " floor=" + ground.fraction + " floorSolid=" + ground.startSolid + " end=" + position )
\t\t}
'''
    path=stage/'mod/scripts/vscripts/_phase_runner_preview.nut';source=path.read_text();marker='\t\tprintl( "Phase Runner local test: server reporting disabled after startup config." )\n'
    if 'array<vector> walkStarts' in source:raise ValueError('Duplicate test block')
    path.write_text(source.replace(marker,marker+text));(ROOT/'logs/tunnel-step-walk-probes.json').write_text(json.dumps([dict(start=a.tolist(),end=b.tolist()) for a,b in zip(starts,ends)],indent=2))
    print('Step walks',len(starts))

if __name__=='__main__':add()
