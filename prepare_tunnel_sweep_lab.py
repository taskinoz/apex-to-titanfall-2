"""Run player hull sweeps through reported openings in the isolated profile."""
import json,shutil
from pathlib import Path
import numpy as np
from audit_reported_tunnel_barriers import POINTS
from stage_prop_geometry import rotation
ROOT=Path(__file__).resolve().parent

def prepare():
    base=ROOT/'northstar/PhaseRunner.Preview';stage=ROOT/'northstar/PhaseRunner.TunnelSweepLab'
    for rel in ('mod.json','mod/maps/mp_phase_runner_preview.bsp','mod/scripts/vscripts/_phase_runner_preview.nut'):
        dst=stage/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base/rel,dst)
    props=json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
    rings=[p for p in props if p['in_arena'] and 'wraith_tt_portal_large' in p['model']]
    probes=[]
    for i,point in enumerate(POINTS):
        ring=min(rings,key=lambda p:np.linalg.norm(np.array(point)-p['origin']))
        direction=np.array(rotation(ring['angles']))[:,1];direction[2]=0;direction/=np.linalg.norm(direction)
        for lift in (4,24,48,80):
            for sign in (-1,1):
                center=np.array(point)+[0,0,lift]
                probes.append(dict(site=i,ring=ring['index'],lift=lift,direction=sign,start=(center-direction*64*sign).tolist(),end=(center+direction*64*sign).tolist()))
    def vec(v):return '< '+', '.join(f'{x:.6f}' for x in v)+' >'
    text='\n\t\tarray<vector> tunnelStarts = [ '+', '.join(vec(p['start']) for p in probes)+' ]\n'
    text+='\t\tarray<vector> tunnelEnds = [ '+', '.join(vec(p['end']) for p in probes)+' ]\n'
    text+='\t\tfor ( int i=0; i<tunnelStarts.len(); i++ )\n\t\t{\n'
    text+='\t\t\tTraceResults result = TraceHull( tunnelStarts[i], tunnelEnds[i], < -16,-16,0 >, < 16,16,72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n'
    text+='\t\t\tprintl( "Phase Runner tunnel sweep " + i + ": fraction=" + result.fraction + " startSolid=" + result.startSolid )\n\t\t}\n'
    script=stage/'mod/scripts/vscripts/_phase_runner_preview.nut';source=script.read_text()
    marker='\t\tprintl( "Phase Runner local test: server reporting disabled after startup config." )\n'
    if marker not in source:raise ValueError('Local test marker missing')
    script.write_text(source.replace(marker,marker+text))
    (ROOT/'logs/tunnel-native-sweep-probes.json').write_text(json.dumps(probes,indent=2))
    print('Tunnel sweep probes',len(probes))

if __name__=='__main__':prepare()
