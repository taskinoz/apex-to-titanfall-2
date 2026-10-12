import collections,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from read_vg_static import compiled_materials
from extract_native_material import NativePak
P=ROOT/'output/phase-runner'
def main():
    props=json.loads((P/'static-props.json').read_text());rendered=set()
    for group in ('prop','phase-structure','support','area-detail','broad','portal','landscape'):
        rendered.update(p['index'] for p in json.loads((P/(group+'-geometry')/'report.json').read_text())['restored'])
    rendered.update(p['index'] for p in json.loads((P/'center-detail/center-detail.json').read_text())['source_geometry']['placements'])
    arena=[p for p in props if p['in_arena']];missing=[p for p in arena if p['index'] not in rendered]
    groups=collections.Counter(p['model'].split('/')[1] for p in missing);models=collections.Counter(p['model'] for p in missing)
    info=dict(source_static_placements=len(props),arena_static_placements=len(arena),rendered_static_placements=len(rendered),
        rendered_in_arena=sum(p['index'] in rendered for p in arena),unrendered_arena_placements=len(missing),unrendered_all_placements=len(props)-len(rendered),
        unrendered_arena_distinct_models=len(models),remaining_arena_categories=dict(groups),remaining_models=dict(models),
        remaining_placements=missing,source_entity_inventory=json.loads((P/'entity-prop-inventory.json').read_text())['model_counts'])
    print('COUNTS',json.dumps({k:v for k,v in info.items() if k not in ('remaining_placements','remaining_models')},indent=2))
    print('MODEL_COUNTS',json.dumps(dict(models.most_common()),indent=2))
    mapping=json.loads((P/'world-materials/mapping.json').read_text())['materials'];mats={k.rsplit('/',1)[-1] for k in mapping}
    consoles=[]
    for model in sorted({p['model'] for p in props if p['index'] in rendered}):
        if not any(k in model.lower() for k in ('console','computer','monitor','laptop')):continue
        name=Path(model).stem;folder=ROOT/'tools/legion/exported_files/models'/name
        try:slots,skins=compiled_materials((folder/(name+'.rmdl')).read_bytes())
        except Exception as e:print('CONSOLE_ERROR',model,str(e));continue
        rows=[p for p in props if p['model']==model and p['index'] in rendered]
        entry=dict(model=model,slots=slots,skins=skins,materials_mapped=[[(m,m in mats) for m in skin] for skin in skins],placements=rows)
        consoles.append(entry)
        print('CONSOLE',json.dumps({**entry,'placements':[{k:p[k] for k in ('index','origin','skin')} for p in rows]},indent=2))
    info['console_models']=consoles
    (ROOT/'logs/remaining-props-material-audit.json').write_text(json.dumps(info,indent=2))
    glass=[]
    for filename in ('common.raw.rpak','coliseum.raw.rpak'):
        pak=NativePak(ROOT/'inputs/tf2-rpak-work'/filename)
        for a in pak.assets:
            if a['type']!='matl' or a['version']!=12:continue
            spec,uber=pak.material(a)
            if any(w in spec['name'].lower() for w in ('glass','monitor','screen','computer')):
                glass.append(dict(pak=filename,guid=hex(a['guid']),spec=spec,uber_bytes=len(uber)))
        del pak
    (ROOT/'logs/native-glass-console-materials.json').write_text(json.dumps(glass,indent=2))
    print('NATIVE_MATERIALS',[(x['pak'],x['guid'],x['spec']['name'],x['spec']['shaderType'],x['spec']['blendStates'],x['spec']['glueFlags']) for x in glass])
if __name__=='__main__':main()
