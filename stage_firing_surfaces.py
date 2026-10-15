"""Stage the Firing Range surface repair as an isolated candidate mod.

Copies the accepted mod and replaces only the rebuilt map, STBSP and
world RPak. The shared ApexMaps.UI companion and loading pack are unchanged.
"""
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import digest
from map_pack_lifetime import audit

VERSION = '0.4.0'
# The repair rebuilds from the 0.3.1 snapshot; its BSP hash is recorded in port-0.3.0.
BASELINE_BSP = 'ec8d188dc56835749956488bb175dfa8cbfbe2a460d0e057076f64665f354c6b'
NAME = 'ApexFiringRange'
PAYLOAD = ('mod/maps/mp_apex_firing_range.bsp', 'mod/maps/mp_apex_firing_range.stbsp',
           'paks/firing_range_world.rpak')


def stage():
    out = folder('firing-range')
    accepted = ROOT/'northstar'/NAME
    if json.loads((accepted/'mod.json').read_text())['Version'] not in ('0.3.1', '0.4.0'):
        raise ValueError('Unexpected accepted baseline version')
    if digest(out/'before-0.4.0/mp_apex_firing_range.bsp') != BASELINE_BSP:
        raise ValueError('Repair snapshot is not the 0.3.1 payload')
    if not (out/'surface-repair/binary-validation.json').exists():
        raise ValueError('Run verify_firing_surfaces.py first')
    candidate = WORK/'surface-candidates'/NAME
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    sources = dict(zip(PAYLOAD, (out/'mp_apex_firing_range.bsp', out/'mp_apex_firing_range.stbsp',
                                 out/'materials/build/firing_range_world.rpak')))
    for relative, source in sources.items():
        shutil.copy2(source, candidate/relative)
        if digest(source) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text())
    mod['Version'] = VERSION
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    audit(candidate/'paks', 'mp_apex_firing_range')
    print('Staged', candidate, {k: digest(candidate/k) for k in PAYLOAD}, flush=True)
    return candidate


if __name__ == '__main__':
    stage()
