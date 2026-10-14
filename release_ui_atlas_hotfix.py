"""Package a UI-lifetime hotfix only after combined-install native validation."""
import argparse
import json
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS, audit
from package_player_mods import RELEASES, write_player_zip, digest

VERSIONS = {'PhaseRunner': ('1.6.0','1.6.1'), 'ArenaComposite': ('0.10.0','0.10.1'),
            'ApexFiringRange': ('0.3.0','0.3.1'), 'ArenaPartyCrasher': ('0.3.0','0.3.1'),
            'ArenaOverflow': ('0.3.0','0.3.1')}
NOTE = ('UI atlas hotfix: all five conversions share one original-art UI atlas in ApexMaps.UI, '
        'so installing multiple conversions avoids exhausting the native atlas pool. '
        'Native world material dependency ordering is preserved. Geometry, collision, '
        'textures and lighting are unchanged. All five installed maps were checked together '
        'on one local client; multiplayer load and AI remain unverified.')


def prepare():
    for package, (old, new) in VERSIONS.items():
        mod = ROOT/'northstar'/package
        audit(mod/'paks', MAPS[package])
        path = mod/'mod.json'
        meta = json.loads(path.read_text())
        if meta['Version'] not in (old, new):
            raise ValueError('Unexpected baseline version: '+package)
        meta['Version'] = new
        path.write_text(json.dumps(meta, indent=2)+'\n')
        readme = mod/'README.md'
        text = readme.read_text(encoding='utf-8')
        heading = '# '+package+' '+new+' UI atlas hotfix\n\n'
        if not text.startswith(heading):
            readme.write_text(heading + 'Install and enable the included ApexMaps.UI companion. World materials, '
                              'geometry and collision are unchanged. See the repository\'s '
                              'UI atlas validation receipt for final combined-install checks.\n\n'
                              '## Previous release notes\n\n'+text, encoding='utf-8')


def package_all():
    proof_path = ROOT/'docs/conversion/ui-atlas-lifetime-validation.json'
    proof = json.loads(proof_path.read_text())
    if not proof.get('passed') or not proof.get('multiplayer_lobby_verified') or not proof.get('stock_reload_verified'):
        raise ValueError('Final combined-install/menu/reload proof missing')
    ledger_path = ROOT/'output/player-distributions.json'
    ledger = json.loads(ledger_path.read_text())
    for package, (_, version) in VERSIONS.items():
        mod = ROOT/'northstar'/package
        if digest(mod/'paks/rpak.json') != proof['maps'][package]['config_sha256']:
            raise ValueError('Native proof has stale UI filters: '+package)
        if package not in RELEASES:
            RELEASES[package] = dict(version=version, map=MAPS[package], title=package,
                                    screenshot='northstar/'+package+'/screenshot.png', notes=NOTE)
        else:
            RELEASES[package]['notes'] += ' '+NOTE
        ledger[package] = write_player_zip(mod, ROOT/'output'/(package+'-'+version+'-Northstar.zip'))
        ledger_path.write_text(json.dumps(ledger, indent=2)+'\n')
    print('Five UI-lifetime releases packaged and hash-verified', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','package'])
    a = p.parse_args()
    (prepare if a.action == 'prepare' else package_all)()
