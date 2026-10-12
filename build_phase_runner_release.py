"""Rebuild the twenty fir additions with measured root corrections, then stage 1.0.0."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import build_phase_runner_firs as firs
from extract_native_material import NativePak

def build():
    prior=json.loads((ROOT/'northstar/PhaseRunner.Preview/trees.json').read_text())
    audit=json.loads((ROOT/'logs/tree-grounding-before.json').read_text())
    changes={p['index']:p for p in audit['placements']}
    props=copy.deepcopy(prior['source_placements'])
    for p in props:p['origin'][2]+=changes[p['index']]['delta_z']
    firs.OUT=ROOT/'output/phase-runner/release-1.0.0'
    firs.TARGET=firs.OUT/'mp_phase_runner.bsp'
    firs.PACKAGE=ROOT/'northstar/PhaseRunner'
    firs.VERSION='1.0.0'
    firs.select=lambda:props
    # The working foliage pipeline is unchanged; reuse its validated RPak.
    mapping=json.loads((firs.MATERIALS/'mapping.json').read_text())
    pak=NativePak(firs.MATERIALS/'build/phase_runner_firs.rpak')
    firs.materials=lambda names:(mapping,pak)
    firs.build()
    report=json.loads((firs.OUT/'trees.json').read_text())
    original={p['index']:p for p in prior['source_placements']}
    for p in report['source_placements']:
        p['source_origin']=original[p['index']]['origin']
        p['grounding_delta_z']=changes[p['index']]['delta_z']
    report.update(original_positions_rotations_scales_and_uvs_preserved=False,
                  original_xy_rotations_scales_skins_uvs_preserved=True,
                  intentional_vertical_root_corrections=True,grounding_audit=audit,
                  baseline_release='0.1.46',trees_moved=sum(r['delta_z']<-.01 for r in audit['placements']))
    for target in (firs.OUT/'trees.json',firs.PACKAGE/'trees.json'):target.write_text(json.dumps(report,indent=2))
    meta=json.loads((firs.PACKAGE/'mod.json').read_text())
    meta.update(Name='PhaseRunner',Description='Phase Runner release: grounded firs, industrial catwalks, collision, PBR, baked lighting and localized loading artwork.')
    (firs.PACKAGE/'mod.json').write_text(json.dumps(meta,indent=2))
    status=json.loads((firs.PACKAGE/'build-status.json').read_text());status['tree_release']=report
    status['release_version']='1.0.0';(firs.PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(dict(version='1.0.0',trees_checked=20,trees_moved=report['trees_moved'],target=str(firs.TARGET),package=str(firs.PACKAGE)),indent=2))

if __name__=='__main__':build()
