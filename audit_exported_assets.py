"""Check recovered meshes and QC references against map dependencies."""
import argparse
import json
import re
from pathlib import Path


def normalized(name):
    value = name.replace('\\','/').lower()
    if value.startswith('models/'):
        value = 'mdl/' + value[7:]
    return value.rsplit('.',1)[0]


def audit(folder, geometry_summary, output):
    required = json.loads(geometry_summary.read_text())['static_prop_models']
    recovered = {}
    for qc in sorted(folder.rglob('*.qc')):
        text = qc.read_text(errors='replace')
        match = re.search(r'\$modelname\s+"([^"]+)"',text)
        if not match:
            continue
        references = re.findall(r'\bstudio\s+"([^"]+\.smd)"',text)
        files = sorted(qc.parent.glob('*.smd'))
        meshes = []
        for smd in files:
            lines = smd.read_text(errors='replace').splitlines()
            try:
                starts=[i+1 for i,line in enumerate(lines) if line=='triangles']
                if not starts: raise ValueError('No triangle sections')
                all_blocks=[]
                for first in starts:
                    last=lines.index('end',first)
                    blocks=lines[first:last]
                    if len(blocks)%4: raise ValueError('Incomplete triangle block')
                    for offset in range(0,len(blocks),4):
                        for line in blocks[offset+1:offset+4]:
                            values=line.split()
                            if len(values)<9: raise ValueError('Truncated vertex')
                            list(map(float,values[1:9]))
                    all_blocks.extend(blocks)
                blocks=all_blocks
                materials=sorted(set(blocks[::4]))
                meshes.append(dict(path=str(smd.resolve()),triangles=len(blocks)//4,
                                   materials=materials,valid_triangle_records=True))
            except (ValueError,IndexError) as exc:
                meshes.append(dict(path=str(smd.resolve()),error=str(exc),valid_triangle_records=False))
        record = dict(model=match[1],qc=str(qc.resolve()),meshes=meshes,
                      missing_qc_mesh_references=[r for r in references if not (qc.parent/r).is_file()])
        key = normalized(match[1])
        old = recovered.get(key)
        if old is None or sum(m.get('triangles',0) for m in meshes) > sum(m.get('triangles',0) for m in old['meshes']):
            recovered[key] = record
    matched = [name for name in required if normalized(name) in recovered and any(
        m['valid_triangle_records'] and m.get('triangles',0)>0 for m in recovered[normalized(name)]['meshes'])]
    result = dict(required_model_paths=len(required), recovered_qcs=len(recovered),
                  source_qc_files=len(list(folder.rglob('*.qc'))),source_smd_files=len(list(folder.rglob('*.smd'))),
                  recovered_smds=sum(len(v['meshes']) for v in recovered.values()),
                  required_models_with_valid_meshes=len(matched),
                  missing_required_meshes=[n for n in required if n not in matched],
                  qcs_with_missing_mesh_references=sum(bool(v['missing_qc_mesh_references']) for v in recovered.values()),
                  texture_files=len(list(folder.rglob('*.dds'))),models=recovered,
                  ready_for_titanfall2=False,
                  note='Extracted source meshes are not compiled Titanfall 2 models. QC links and material bindings require repair.')
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('models','missing_required_meshes')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('geometry_summary',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    audit(args.folder,args.geometry_summary,args.output)
