"""Stage recovered map meshes and repair unambiguous exported QC references.

These are source assets for conversion, not compiled Titanfall 2 models.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from audit_exported_assets import normalized


def prepare(report_path, summary_path, output):
    report = json.loads(report_path.read_text())
    required = json.loads(summary_path.read_text())['static_prop_models']
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for model in required:
        record = report['models'].get(normalized(model))
        if not record or not any(m.get('triangles', 0) > 0 and
                                 m['valid_triangle_records'] for m in record['meshes']):
            continue
        source = Path(record['qc'])
        destination = output / normalized(model)
        destination.mkdir(parents=True, exist_ok=True)
        text = source.read_text(errors='replace')
        repairs = []
        unresolved = []

        def repair(match):
            reference = match[1]
            if (source.parent / reference).is_file():
                return match[0]
            # Legion adds a body suffix in QC references that its SMD exporter omits.
            candidate = re.sub(r'_body_\d+(?=_LOD\d+\.smd$)', '', reference)
            if candidate != reference and (source.parent / candidate).is_file():
                repairs.append(dict(old=reference, new=candidate))
                return match[0].replace(reference, candidate)
            unresolved.append(reference)
            return match[0]

        text = re.sub(r'\bstudio\s+"([^"]+\.smd)"', repair, text)
        for mesh in record['meshes']:
            if mesh['valid_triangle_records']:
                shutil.copy2(mesh['path'], destination / Path(mesh['path']).name)
        (destination / source.name).write_text(text, encoding='utf-8')
        records.append(dict(model=model, source_qc=str(source),
                            staged_qc=str((destination / source.name).resolve()),
                            repaired_references=repairs, unresolved_references=unresolved))
    result = dict(staged_models=len(records),
                  repaired_references=sum(len(r['repaired_references']) for r in records),
                  unresolved_references=sum(len(r['unresolved_references']) for r in records),
                  playable=False, compiled_for_titanfall2=False, models=records,
                  note='Material bindings and target model compilation remain unresolved.')
    (output / 'preparation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'models'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('summary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prepare(args.report, args.summary, args.output)
