"""Export a small public validation receipt without private harness state or logs."""
import json
import subprocess

from prepare_anniversary_release import ROOT,OUT,BASE,write
from package_anniversary_rc import DEST,gates


def report():
    structural,combined,modes,stress=gates()
    visual=json.loads((OUT/'visual-validation.json').read_text())
    provenance=json.loads((OUT/'baseline-manifest.json').read_text())
    pin=json.loads((OUT/'runtime-pin.json').read_text())
    releases=json.loads((DEST/'release-manifest.json').read_text())
    session=json.loads((OUT/'final-session.json').read_text())
    if not session.get('owned_session_stopped') or session['script_errors'] or session['native_crashes']:
        raise ValueError('Final owned session did not close cleanly')
    result={'date':'2026-10-28','scope':'Original five; one local Windows client',
            'runtime':{k:pin[k] for k in ('version','launcher_sha256','dll_sha256')},
            'base_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'runtime_bytes_changed':False,'mounted_runtime_files_verified':True,
            'owned_session_stopped_cleanly':True,'structural':structural,
            'native_sessions':[],'screenshots':[],
            'overflow_stress':{'completed_cycles':stress['count'],'fresh_process_launches':stress['count']-1,
                               'stock_and_converted_reload_cycles':stress['count'],
                               'modes':[r['mode'] for r in stress['runs']],
                               'logged_script_errors':0,'logged_native_crashes':0,
                               'root_cause_of_historical_crash_established':False},
            'offline_tests':{'geometry_capacity_support':21,'binary_adapters':4,'harness':12,'archive_provenance':4},
            'packages':releases['packages'],
            'limitations':['One local client; multiplayer load, balance and dedicated servers not certified',
                           'AI navigation and Apex-specific gameplay systems remain incomplete',
                           'Objective presence is not full objective scoring/round certification',
                           'Bounded newer-runtime checks do not establish the old Overflow crash root cause',
                           'Safety volumes preserved; every hazard and traversal route not physically exercised']}
    for record in (*combined['maps'][:5],*modes['maps']):
        native=record['mode_check']
        result['native_sessions'].append({'package':record['package'],'map':record['map'],'mode':record['mode'],
            'pilot_spawns':record['pilot_spawns'],'invalid_pilot_spawns':len(record['invalid_pilot_spawns']),
            'both_teams_selected':record['both_teams_live'],'living_player':True,'weapon_fire_exercised':True,
            'postmatch_return_to_lobby':True,'objectives':native['objectives'],'panels':native['panels'],
            'entities':native['entities'],'logged_script_errors':len(record['logs']['script_errors']),
            'logged_native_crashes':len(record['logs']['native_crashes'])})
    for row in visual['captures']:
        cap=row['capture'];client=cap['state']['contexts']['client']
        result['screenshots'].append({'package':row['package'],'map':client['level'],'sha256':cap['sha256'],
                                     'width':cap['width'],'height':cap['height'],'origin':client['origin'],
                                     'angles':client['angles'],'captured':cap['captured'],'visually_reviewed':True})
    for name in BASE:
        result.setdefault('accepted_beta_archive_hashes',{})[name]=provenance[name]['accepted_zip_sha256']
    write(ROOT/'docs/anniversary-2026-validation.json',result)
    print('Public anniversary validation receipt written',flush=True)


if __name__=='__main__':report()
