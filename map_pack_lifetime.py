"""Audit the shared UI atlas and preserve native world shader ordering."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPS = {'PhaseRunner': 'mp_phase_runner', 'ArenaComposite': 'mp_arena_composite',
        'ApexFiringRange': 'mp_apex_firing_range', 'ArenaPartyCrasher': 'mp_party_crasher',
        'ArenaOverflow': 'mp_overflow'}


def scope(paks, map_name):
    paks = Path(paks)
    if not re.fullmatch(r'mp_[a-z0-9_]+', map_name):
        raise ValueError('Invalid map name')
    path = paks / 'rpak.json'
    value = json.loads(path.read_text())
    names = {p.name for p in paks.glob('*.rpak')}
    for key in ('Preload', 'Postload'):
        if key in value:
            value[key] = {k: v for k, v in value[key].items() if k not in names}
            if not value[key]:
                value.pop(key)
    for name in sorted(names):
        value.pop(name, None)
        value.setdefault('Postload', {})[name] = ('common.rpak' if name.endswith('_presentation.rpak') else 'mp_coliseum.rpak')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return dict(map=map_name, configured_packs=sorted(names), binary_audit_pending=True)


def audit(paks, map_name):
    paks = Path(paks)
    value = json.loads((paks / 'rpak.json').read_text())
    names = sorted(p.name for p in paks.glob('*.rpak'))
    from extract_native_material import NativePak
    for name in names:
        if name.endswith('_minimap.rpak'):
            raise ValueError('Standalone minimap atlas must be moved to the shared UI pack')
        if name.endswith('_presentation.rpak'):
            if any(a['type']=='uimg' for a in NativePak(paks/name).assets):
                raise ValueError('Loading pack still owns a separate UI atlas: '+name)
            if value.get('Postload', {}).get(name) != 'common.rpak' or name in value:
                raise ValueError('Atlas-free loading material lifetime changed')
        elif value.get('Postload', {}).get(name) != 'mp_coliseum.rpak' or name in value:
            raise ValueError('Native world shader ordering changed: ' + name)
    presentation = next(n for n in names if n.endswith('_presentation.rpak'))
    aliases = value['Aliases']
    if aliases.get(map_name + '_loadscreen.rpak') != presentation:
        raise ValueError('Native loading screen alias changed')
    if aliases.get(map_name + '.rpak') != 'mp_coliseum.rpak':
        raise ValueError('Native base map alias changed')
    return dict(map=map_name, packs=names, startup_map_atlases=0,
                policy='Shared UI companion; atlas-free loading packs and native base-pack world ordering')


def audit_shared():
    from extract_native_material import NativePak
    shared=ROOT/'northstar/ApexMaps.UI'
    config=json.loads((shared/'paks/rpak.json').read_text())
    if config != {'Postload': {'apex_maps_ui.rpak':'common.rpak'}}:
        raise ValueError('Shared atlas lifetime changed')
    assets=NativePak(shared/'paks/apex_maps_ui.rpak').assets
    if sorted(a['type'] for a in assets) != ['txtr','uimg']:
        raise ValueError('Shared UI pack must contain exactly one atlas and its texture')
    return dict(companion='ApexMaps.UI', version='0.1.0', custom_ui_atlases=1)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['apply', 'audit'])
    args = p.parse_args()
    results = {n: (scope if args.action == 'apply' else audit)(ROOT / 'northstar' / n / 'paks', m)
               for n, m in MAPS.items()}
    print(json.dumps(results, indent=2))
