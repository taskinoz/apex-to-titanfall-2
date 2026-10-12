"""Add grounded traversal and floor contacts along both new pipe walkways."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent

def add():
    routes=json.loads((ROOT/'output/phase-runner/preview-tunnel-walkways/tunnel-walkways.json').read_text())['routes'];stage=ROOT/'northstar/PhaseRunner.TunnelSweepLab'
    def vec(v):return '< '+', '.join(f'{x:.6f}' for x in v)+' >'
    points=[];starts=[];ends=[];probes=[]
    for ri,route in enumerate(routes):
        for a,b in zip(route['points'],route['points'][1:]):
            a=np.array(a);b=np.array(b);count=max(1,int(np.ceil(np.linalg.norm(b-a)/8)))
            for j in range(count):
                p=a+(b-a)*j/count;q=a+(b-a)*(j+1)/count
                starts.append(p+[0,0,2]);ends.append(q+[0,0,2]);probes.append(dict(route=ri,start=starts[-1].tolist(),end=ends[-1].tolist()))
    text='\n\t\tarray<vector> routeStarts = [ '+', '.join(map(vec,starts))+' ]\n'
    text+='\t\tarray<vector> routeEnds = [ '+', '.join(map(vec,ends))+' ]\n'
    text+='''\t\tint routeClear = 0
\t\tint floorHits = 0
\t\tfor ( int i=0; i<routeStarts.len(); i++ )
\t\t{
\t\t\tvector start = routeStarts[i]
\t\t\tvector end = routeEnds[i]
\t\t\tfloat height = max( start.z, end.z ) + 18
\t\t\tvector a = <start.x,start.y,height>
\t\t\tvector b = <end.x,end.y,height>
\t\t\tTraceResults forward = TraceHull( a,b, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tTraceResults reverse = TraceHull( b,a, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tTraceResults floor = TraceHull( b, end-<0,0,8>, < -16,-16,0 >, <16,16,72>, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
\t\t\tif ( floor.fraction < 1 && !floor.startSolid ) floorHits++
\t\t\tif ( forward.fraction == 1 && reverse.fraction == 1 && !forward.startSolid && !reverse.startSolid ) routeClear++
\t\t\telse printl( "Phase Runner route obstruction " + i + ": forward=" + forward.fraction + " reverse=" + reverse.fraction + " solid=" + forward.startSolid + "," + reverse.startSolid + " normal=" + forward.surfaceNormal + " end=" + forward.endPos )
\t\t}
\t\tprintl( "Phase Runner walkway traversal: " + routeClear + "/" + routeStarts.len() + " clear; floors=" + floorHits )
'''
    path=stage/'mod/scripts/vscripts/_phase_runner_preview.nut';source=path.read_text();marker='\t\tprintl( "Phase Runner local test: server reporting disabled after startup config." )\n'
    if 'array<vector> routeStarts' in source:raise ValueError('Duplicate block')
    path.write_text(source.replace(marker,marker+text));(ROOT/'logs/tunnel-walkway-route-probes.json').write_text(json.dumps(probes,indent=2));print('Walkway route segments',len(probes))

if __name__=='__main__':add()
