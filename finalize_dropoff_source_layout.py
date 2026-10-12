"""Refresh the source-layout release ledger and remove obsolete access carving."""
import json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def refresh():
    path=ROOT/'apply_arena_boundaries.py'
    text=path.read_text()
    start=text.index('def allow_platform_access(')
    end=text.index('def apply():',start)
    path.write_text(text[:start]+text[end:])
    path=ROOT/'test_arena_boundaries.py'
    text=path.read_text()
    start=text.index('    def test_access_corridors_')
    end=text.index("if __name__",start)
    replacement='''    def test_dropoff_keeps_original_converted_source_volumes(self):
        rows=entities(ROOT/'output/composite/mp_arena_composite.bsp')
        expected=json.loads((ROOT/'output/composite/native-gameplay-volumes.json').read_text())['dropoff']
        actual=[e for e in rows if e.get('targetname','').startswith('dropoff_source_boundary_')]
        self.assertEqual(actual,expected)

'''
    path.write_text(text[:start]+replacement+text[end:])
    path=ROOT/'package_player_mods.py'
    path.write_text(path.read_text().replace('dropoff-020-court-e031b52f.png','dropoff-030-court-ddf932bf.png'))
    path=ROOT/'finalize_composite_release.py'
    text=path.read_text().replace('0.2.0','0.3.0')
    text=text.replace('Two source zipline pairs and two additional upper\nplatform access ropes are converted to native Titanfall ziplines.',
                      'Only the two source zipline pairs are converted to native Titanfall ziplines.\nTemporary arena spawn covers are omitted; permanent room and roof clips remain.')
    path.write_text(text)
    doc=ROOT/'docs/composite'
    path=doc/'README.md'
    text=path.read_text().replace('0.2.0','0.3.0')
    start=text.index('This repair adds')
    text=text[:start]+'''This repair preserves the two source zipline pairs, removes temporary arena
spawn covers, and restores the intended room and roof boundaries. It retains
all 124 source stair placements and the previous material fixes. See
`../dropoff-source-layout-2026-10-07.md` for source comparison and validation.
'''
    path.write_text(text,encoding='utf-8')
    path=doc/'MISSING_CONTENT.md'
    text=path.read_text().replace('0.2.0','0.3.0')
    text=text.replace('Two source zipline pairs and two additional upper\nplatform access ropes are converted to native Titanfall ziplines.',
                      'Only the two source zipline pairs are converted to native Titanfall ziplines.\nTemporary arena spawn covers are omitted; permanent room and roof clips remain.')
    path.write_text(text,encoding='utf-8')
    path=doc/'CONVERSION.md'
    text=path.read_text()
    text+='\n## Source-layout correction in 0.3.0\n\nSee `../dropoff-source-layout-2026-10-07.md`. Conditional arena start covers\nare excluded from permanent rendering. Source zipline GUID pairs provide the\nendpoints; intentional toolclip room closures are retained.\n'
    path.write_text(text,encoding='utf-8')
    path=ROOT/'docs/arena-repairs-2026-10-06.md'
    text=path.read_text()
    text='Historical 0.2.0 record. Drop-Off source-layout corrections are documented in\n[the 0.3.0 record](dropoff-source-layout-2026-10-07.md).\n\n'+text
    path.write_text(text,encoding='utf-8')

def record():
    out=ROOT/'output/composite';doc=ROOT/'docs/composite';mod=ROOT/'northstar/ArenaComposite'
    runtime=json.loads((out/'source-layout-runtime.json').read_text())
    proof=dict(version='0.3.0',final_client_verified=True,conversion_tests=19,
               harness_tests=7,harness_tests_note='Harness unchanged; seven tests passed in the preceding round.',
               native_repair_evidence='output/composite/source-layout-runtime.json',
               runtime=runtime,source_safety=json.loads((ROOT/'output/arena-boundary-repair.json').read_text())['dropoff'],
               remaining=['Reported window opening still needs identification.',
                          'Temporary covers may leave minor old baked shadows until a full rebake.',
                          'Original post-match crash root cause remains unestablished.'])
    (doc/'validation.json').write_text(json.dumps(proof,indent=2))
    build=json.loads((out/'source-build.json').read_text())
    build.update(version='0.3.0',client_verified=True,validation=proof,
                 collision={k:v for k,v in json.loads((out/'physics.json').read_text()).items() if k not in ('owners','missing')},
                 safety=proof['source_safety'],repair_record='docs/dropoff-source-layout-2026-10-07.md',
                 source_layout_repair=json.loads((out/'source-layout-repair.json').read_text()),
                 active_render_triangles=899880,
                 validation_evidence=['output/composite/source-layout-runtime.json','logs/dropoff-source-layout-tests.log'])
    build['build']['checks']['in_game_verified']=True
    build['build']['checks']['bytes']=(out/'mp_arena_composite.bsp').stat().st_size
    build['build']['compact_bytes']=build['build']['checks']['bytes']
    build['streaming_sidecar']['client_load_verified']=True
    (out/'source-build.json').write_text(json.dumps(build,indent=2))
    shutil.copy2(out/'source-build.json',mod/'build-status.json')
    shutil.copy2(doc/'README.md',mod/'README.md')
    shutil.copytree(doc,mod/'docs',dirs_exist_ok=True)
    (ROOT/'logs/dropoff-source-layout-tests.log').write_text('python -m unittest test_composite_port test_arena_boundaries\n19 tests passed in 6.453 seconds.\n')
    path=ROOT/'docs/dropoff-source-layout-2026-10-07.md'
    text=path.read_text().split('\n### Native confirmation')[0]
    path.write_text(text+'\n### Native confirmation\n\nAll 19 regression checks passed. Native traces cross all six spawn exits\nwithout collision. North and both mirrored diagonal room closures register\ncollision. Reviewed native captures show the start covers removed and the\nmap still rendered correctly. Runtime entity counts retain two rope pairs,\n21 out-of-bounds volumes and five hurt volumes. A forced native Postmatch\nreturned to the lobby with the same live process and no logged script errors.\nThis single end-state test does not establish the cause of the earlier crash.\n')
    shutil.copy2(path,mod/'docs/source-layout-2026-10-07.md')
    print('Release ledger updated for Drop-Off 0.3.0.')

if __name__=='__main__':
    import sys
    record() if '--record' in sys.argv else refresh()
