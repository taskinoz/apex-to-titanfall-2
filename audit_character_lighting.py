"""Inspect native model lighting records without changing any BSP."""
import json,struct
from pathlib import Path
from repair_preview_index_padding import read_lumps
ROOT=Path(__file__).resolve().parent
PATHS={'phase_runner':ROOT/'northstar/PhaseRunner.Preview/mod/maps/mp_phase_runner.bsp',
       **{n:ROOT/f'inputs/titanfall2-{folder}/maps/{name}.bsp' for n,folder,name in
          [('coliseum','coliseum','mp_coliseum'),('homestead','homestead','mp_homestead'),('colony','colony','mp_colony02')]}}

def main():
    output={}
    for name,path in PATHS.items():
        lumps=read_lumps(path,[4,6,7,0x36,0x65,0x66,0x67,0x68])
        refs=list(struct.iter_unpack('<3fIi',lumps[0x68]));trees=list(struct.iter_unpack('<2I',lumps[0x67]))
        data={'path':str(path),'bytes':{hex(k):len(v) for k,v in lumps.items()},
              'parents':list(struct.iter_unpack('<i6I',lumps[4])),
              'bsp_nodes':list(struct.iter_unpack('<4f2I',lumps[6]))[:30],
              'bsp_ref_ids':list(struct.iter_unpack('<I',lumps[7]))[:100],
              'tree_first_records':trees[:100],'tree_tags':sorted(set(x[0]&3 for x in trees)),
              'references':len(refs),'reference_examples':refs[:8],
              'origin_min':[min(r[k] for r in refs) for k in range(3)] if refs else None,
              'origin_max':[max(r[k] for r in refs) for k in range(3)] if refs else None,
              'probe_examples':[list(struct.unpack_from('<24B4h4B4hI',lumps[0x65],i)) for i in range(0,min(6*48,len(lumps[0x65])),48)]}
        output[name]=data
    (ROOT/'logs/character-lighting-audit.json').write_text(json.dumps(output,indent=2))
    for name,d in output.items():print(name,json.dumps({k:v for k,v in d.items() if k not in ('tree_first_records','bsp_nodes','bsp_ref_ids','probe_examples')}))
if __name__=='__main__':main()
