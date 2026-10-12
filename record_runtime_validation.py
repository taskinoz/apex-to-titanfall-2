"""Record scoped engine load/probe evidence without packaging raw logs."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def record(server_log,client_log,mod):
    server=server_log.read_text(errors='replace')
    client=client_log.read_text(errors='replace')
    probes=[float(v) for v in re.findall(r'Phase Runner collision probe \d+: fraction=([0-9.]+)',client)]
    summary=re.search(r'Phase Runner collision probes: (\d+)/(\d+) hit',client)
    checks=dict(
        mod_version=json.loads((mod/'mod.json').read_text())['Version'],
        team_deathmatch_intro_finished='intro finished!' in client,
        runtime_script_error='SCRIPT ERROR' in client,
        dedicated_map_load_verified='Phase Runner preview:' in server and 'loading took' in server,
        client_map_callback_verified='CLIENT CodeCallback ClientCodeCallback_MapSpawn called' in client,
        client_player_initialized='Player client script initialization complete:' in client,
        client_authentication_rejected='Authentication Failed' in client,
        mod_script_compile_error='COMPILE ERROR' in client,
        server_reporting_disabled='Phase Runner local test: server reporting disabled after startup config.' in client,
        server_registration_attempted='Attempting to register the local server' in client,
        sampled_collision_probe_count=len(probes),
        sampled_collision_hits=int(summary[1]) if summary else 0,
        sampled_collision_expected_distance_verified=bool(probes) and all(abs(v-.5)<.002 for v in probes),
        visual_verified=False,full_map_collision_verified=False,complete_playable_port=False)
    if not all((checks['dedicated_map_load_verified'],checks['client_map_callback_verified'],
                checks['client_player_initialized'],checks['server_reporting_disabled'],
                checks['sampled_collision_expected_distance_verified'],checks['team_deathmatch_intro_finished'])):
        raise ValueError('Runtime evidence does not establish a successful preview test')
    if any((checks['client_authentication_rejected'],checks['mod_script_compile_error'],
            checks['server_registration_attempted'],checks['runtime_script_error'])):
        raise ValueError('Runtime test reports an unresolved failure')
    (mod/'runtime-validation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    files={p.relative_to(mod).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in mod.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (mod/'checksums.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('server_log',type=Path)
    parser.add_argument('client_log',type=Path)
    parser.add_argument('mod',type=Path)
    args=parser.parse_args()
    record(args.server_log,args.client_log,args.mod)
