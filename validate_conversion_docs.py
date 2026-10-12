"""Reconcile release documentation against generated ledgers and retained code."""
import collections,json,re,struct,subprocess,sys,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DOC=ROOT/'docs/conversion'

def main():
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    versions={'python':sys.version,'repositories':{},'libraries':{}}
    for name in ('numpy','Pillow','scipy','xatlas'):
        try:versions['libraries'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions['libraries'][name]='not found'
    for name in ('bsp_tool','mrvn-radiant','repak-source','rsx-source','legion-source','mdlshit'):
        result=subprocess.run(['git','-C',str(ROOT/'tools'/name),'rev-parse','HEAD'],capture_output=True,text=True)
        versions['repositories'][name]=result.stdout.strip() if result.returncode==0 else 'No Git commit available'
    (DOC/'toolchain-versions.json').write_text(json.dumps(versions,indent=2))
    guide=DOC/'APEX_TO_TITANFALL2.md'
    text=guide.read_text(encoding='utf-8')
    names={'apex_to_titanfall.py':'audit_compatibility.py','probe_map.py':'extract_map.py','convert_map.py':'build_preview_source.py',
           'recover_compiled_props.py':'prepare_model_sources.py','recover_prop_materials.py':'recover_model_slots.py',
           'rebuild_render_cells.py':'native_preview_cells.py','decode_apex_bvh.py':'decode_collision.py',
           'repair_tunnel_collision.py':'repair_tunnel_passages.py','build_tunnel_catwalks.py':'build_phase_runner_catwalks.py',
           'bake_phase_runner_lighting.py':'apply_baked_lighting.py'}
    for a,b in names.items():text=text.replace(a,b)
    guide.write_text(text,encoding='utf-8')
    for name in re.findall(r'`([A-Za-z0-9_-]+\.(?:py|cpp|ps1))`',text):
        assert (ROOT/name).is_file(),name
    for document in (guide,DOC/'TOOLCHAIN.md'):
        for link in re.findall(r'\]\(([^)]+)\)',document.read_text()):
            if not link.startswith('https:'):assert (DOC/link).is_file(),link
    inventory=json.loads((DOC/'static-placement-inventory.json').read_text())
    summary=json.loads((DOC/'missing-summary.json').read_text())
    rows=inventory['placements'];counts=collections.Counter(p['status'] for p in rows)
    assert counts==dict(rendered=5425,omitted=10951,outside_arena_not_imported=486)
    assert sum(summary['missing_categories'].values())==counts['omitted']
    assert len({p['source_index'] for p in rows})==16862
    models=json.loads((DOC/'missing-model-types.json').read_text())
    assert len(models)==68 and sum(p['placements'] for p in models)==10951
    assert sum(p['compiled_available'] for p in models)==summary['omitted_model_types_with_compiled_files']
    entities=json.loads((DOC/'entity-inventory.json').read_text())
    assert sum(entities['source_partition_counts'].values())==len(entities['source'])==701
    layouts=json.loads((DOC/'binary-layouts.json').read_text())
    assert len(layouts['lump_slots'])==128
    for r in layouts['observed_writer_layouts']:assert struct.calcsize(r['format'])==r['bytes'],r['name']
    json.loads((DOC/'conversion-project.schema.json').read_text())
    source_index=[]
    for p in sorted(ROOT.glob('*.py')):
        first=p.read_text(encoding='utf-8-sig').splitlines()[:3]
        source_index.append(f"| `{p.name}` | {' '.join(first).replace('|','/').replace('```','').replace('"""','')[:180]} |")
    (DOC/'SOURCE_INDEX.md').write_text('# Retained prototype scripts\n\nHistorical scripts are reference implementations. They include superseded experiments; consult the guide and current release builder before running them. Filenames alone do not establish a supported conversion stage.\n\n| File | Opening description |\n|---|---|\n'+'\n'.join(source_index)+'\n',encoding='utf-8')
    print(json.dumps(dict(placements_reconciled=len(rows),entities_reconciled=701,lump_slots=128,omitted_models=68,script_references_verified=True,document_links_verified=True),indent=2))

if __name__=='__main__':main()
