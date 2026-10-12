"""Restore source safety volumes and convert ropes to native R2 ziplines."""
import collections,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from repair_environment_lighting import entities
from compact_preview_bsp import compact
from build_composite_map import entity_bytes

def rope(a,b,name):
    common=dict(Zipline='1',ZiplineSagEnable='0',ZiplineSagHeight='50',ZiplineMoveSpeedScale='1',
        ZiplineAutoDetachDistance='80',Width='2',UseWind='0',Type='0',TextureScale='1',Subdiv='2',
        spawnflags='1',Slack='0',RopeMaterial='cable/zipline.vmt',PositionInterpolator='2',
        MoveSpeed='64',Dangling='0',Collide='0',Breakable='0',Barbed='0')
    end=name+'_end'
    return [dict(common,classname='move_rope',origin=' '.join(map(str,a)),targetname=name,NextKey=end),
            dict(common,classname='keyframe_rope',origin=' '.join(map(str,b)),targetname=end)]

def apply():
    source=json.loads((ROOT/'output/composite/source-gameplay-volumes.json').read_text())
    volumes=json.loads((ROOT/'output/composite/native-gameplay-volumes.json').read_text())
    report={}
    for key,path in [('phase',ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'),
                     ('dropoff',ROOT/'output/composite/mp_arena_composite.bsp')]:
        rows=[e for e in entities(path) if not e.get('targetname','').startswith(key+'_source_boundary_') and not e.get('targetname','').startswith('dropoff_zipline_')]
        additions=list(volumes[key]);routes=[]
        if key=='dropoff':
            ends={e.get('link_guid'):e for e in source[key] if e['classname']=='zipline_end'}
            for i,e in enumerate(e for e in source[key] if e['classname']=='zipline'):
                a=list(map(float,e['origin'].split()));b=list(map(float,ends[e['link_to_guid_0']]['origin'].split()))
                additions.extend(rope(a,b,f'dropoff_zipline_source_{i}'));routes.append(dict(source=True,start=a,end=b))
            # Preserve the source layout. Upper-platform ropes and boundary
            # openings added by the port were not present in the Apex map.
        target=path.with_suffix('.boundaries.bsp')
        # All target entities live in the main lump; no external entity
        # partitions are shipped, so clear the inherited partition tag.
        compact(path,target,{0:entity_bytes([*rows,*additions]),0x18:b''});os.replace(target,path)
        report[key]=dict(added_counts=dict(collections.Counter(e['classname'] for e in additions)),
            volume_bounds='Source convex pieces intersected with native +/-16,000 world domain',
            ziplines=routes)
    (ROOT/'output/arena-boundary-repair.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':apply()
