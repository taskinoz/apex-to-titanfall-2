import collections,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
inv=json.loads((ROOT/'output/composite/source-inventory.json').read_text())
props=[p for p in inv['props'] if abs(p['origin'][0])<8000 and abs(p['origin'][1])<8000 and -8000<p['origin'][2]<8000]
folders=[ROOT/'tools/composite-legion/exported_files/models',ROOT/'tools/legion/exported_files/models',ROOT/'output/phase-runner/shared-assets/models',ROOT/'output/phase-runner/common-assets/exported_files/models',ROOT/'output/phase-runner/legion-assets/exported_files/models']
index={}
for root in folders:
    if root.is_dir():
        for p in root.rglob('*.rmdl'):
            if p.with_suffix('.vg').is_file():index.setdefault(p.stem.lower(),str(p.parent))
counts=collections.Counter(p['model'] for p in props)
found={m:index.get(Path(m).stem.lower()) for m in counts}
report=dict(playable_props=len(props),unique_models=len(counts),model_paths=found,
    recovered_placements=sum(counts[m] for m in counts if found[m]),
    missing={m:c for m,c in counts.items() if not found[m]},props=props,
    materials=inv['materials'],entities=inv['entities'])
(ROOT/'output/composite/asset-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('model_paths','props','materials','entities')},indent=2))
print('Environment:',[(e.get('classname'),e.get('origin'),e.get('_light'),e.get('_ambient'),e.get('angles'),e.get('skyname')) for es in inv['entities'].values() for e in es if e.get('classname') in ('worldspawn','light_environment','sky_camera')])
