"""Match native sweep contact positions to original owned source surfaces."""
import json,re,struct,collections
import numpy as np
from pathlib import Path
from inspect_full_collision_contact import inspect
ROOT=Path(__file__).resolve().parent

def main():
    probes=json.loads((ROOT/'logs/tunnel-native-sweep-probes.json').read_text())
    log=(ROOT/'logs/tunnel-native-before.log').read_text()
    results=re.findall(r'tunnel sweep (\d+): fraction=([0-9.]+) startSolid=(\w+)',log)
    output=[]
    for index,f,solid in results:
        i=int(index);p=probes[i]
        if p['lift'] not in (4,80) or p['direction']!=1:continue
        start=np.array(p['start']);end=np.array(p['end']);point=start+(end-start)*float(f)
        contacts=inspect(point.tolist())
        owners=collections.Counter((str(t['source_prop']),t['model']) for t in contacts['triangles'])
        row=dict(probe=i,site=p['site'],lift=p['lift'],fraction=float(f),start_solid=solid=='true',contact_position=point.tolist(),brushes=contacts['brushes'],triangle_owners=[dict(index=k[0],model=k[1],count=v) for k,v in owners.items()])
        output.append(row);print(json.dumps(row),flush=True)
    (ROOT/'logs/native-tunnel-contact-ownership.json').write_text(json.dumps(output,indent=2))

if __name__=='__main__':main()
