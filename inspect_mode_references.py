import sys,json,struct,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.branches.shared import Entities
def main():
    path=ROOT/'inputs/titanfall2-homestead/maps/mp_homestead_spawn.ent'
    def read(p):
        d=p.read_bytes();return Entities.from_bytes(d[d.index(b'{'):])
    for filename in ('mp_homestead_spawn.ent','mp_homestead_script.ent'):
        rows=read(path.with_name(filename));print(filename,collections.Counter(e['classname'] for e in rows))
        for cls in ('info_spawnpoint_flag','trigger_multiple'):
            selected=[e for e in rows if e.get('classname')==cls and (cls!='trigger_multiple' or e.get('editorclass')=='trigger_capture_point')]
            if selected:print(json.dumps(dict(selected[0]),indent=2))
    p=ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'
    with p.open('rb') as f:
        h=f.read(2064)
        for i in (0,0x18):
            o,n,_,_=struct.unpack_from('<4I',h,16+16*i);f.seek(o);print('lump',i,f.read(n).decode(errors='replace'))
if __name__=='__main__':main()
