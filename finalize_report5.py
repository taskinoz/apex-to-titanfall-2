"""Publish the 18 October 2026 report round: Party Crasher 0.6.3, Overflow 0.4.1, Phase Runner 1.7.2.

Each staged candidate must carry the validated working map; its map, stream
file and world pack replace the accepted package, the README gains the
release notes, package_player_mods.RELEASES is updated in place and the
player zip (map only; ApexMaps.UI ships separately) is rebuilt.
"""
import json
import re
import shutil
import sys

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import digest
from phase_runner_blend import WORK as PHASE_WORK, PAK as PHASE_PAK

RELEASES = {
    'ArenaPartyCrasher': dict(
        version='0.6.3', baseline='0.6.2', map='mp_party_crasher', candidate=WORK/'report5-candidates/ArenaPartyCrasher',
        work=folder('party-crasher')/'mp_party_crasher.bsp', validation=folder('party-crasher')/'report5-recovery/binary-validation.json',
        files=('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp', 'paks/party_crasher_world.rpak'),
        notes='Fixes the fifth round of reports. The bar counter around the pillar, the glasses on it, and the rubble '
              'and rocks beside the pool are drawn where you could bump into them, and the missing tables are back in '
              'both upper cafes. Table clutter and the out-of-bounds rooftop AC unit and pipes are removed. The "234" '
              'room number no longer blooms, and the pool water is see-through instead of black. Heavy flat-panel '
              'props use simplified meshes to pay for this. Foliage, animated advertisements and AI navigation remain '
              'absent.'),
    'ArenaOverflow': dict(
        version='0.4.1', baseline='0.4.0', map='mp_overflow', candidate=WORK/'overflow-candidates/ArenaOverflow-0.4.1',
        work=folder('overflow')/'mp_overflow.bsp', validation=folder('overflow')/'overlay-repair/binary-validation.json',
        files=('mod/maps/mp_overflow.bsp', 'mod/maps/mp_overflow.stbsp', 'paks/overflow_world.rpak'),
        notes='Fixes z-fighting and flat textures from Apex overlays that were drawn as solid surfaces on top of the '
              'surface below: stencil lettering (REFINERY, the capsules) and arrow signs are now proper decals, the '
              'flat brown dirt sheet over the asphalt is removed, and the lava no longer flickers between its glow and '
              'a grey duplicate. The invisible barrier in the ceiling opening is an Apex player clip and is kept. Known '
              'issue (also in 0.4.0): about one load in five can crash Northstar at spawn; restart and load again.'),
    'PhaseRunner': dict(
        version='1.7.2', baseline='1.7.1', map='mp_phase_runner', candidate=PHASE_WORK/'candidate/PhaseRunner',
        work=PHASE_WORK/'mp_phase_runner.bsp', validation=PHASE_WORK/'binary-validation.json',
        files=('mod/maps/mp_phase_runner.bsp', 'mod/maps/mp_phase_runner.stbsp', f'paks/{PHASE_PAK}.rpak', 'paks/rpak.json'),
        notes='The control-room consoles in both bases are drawn from the full Apex mesh with lighting taken from '
              'their own surface, so their panels no longer look stretched or streaky. Includes 1.7.1: flicker-free '
              'base floors, container frames, smooth catwalks, and 1.7.0 blending, ground tiling and rock collision.'),
}


def persist(name, version, notes):
    """Write the release's version and notes into package_player_mods.RELEASES (source of truth for rebuilds)."""
    path = ROOT/'package_player_mods.py'; s = path.read_text(encoding='utf-8')
    start = s.index(f"    {name!r}: {{"); end = s.index('    },', start)
    block = s[start:end]
    block = re.sub(r"'version': '[^']*'", f"'version': {version!r}", block)
    block = re.sub(r"'notes': .*,\n", f"'notes': {notes!r},\n", block)
    path.write_text(s[:start]+block+s[end:], encoding='utf-8', newline='\n')


def publish(name):
    import importlib
    from map_pack_lifetime import audit, audit_shared
    r = RELEASES[name]; mod = ROOT/'northstar'/name; cand = r['candidate']
    if json.loads((mod/'mod.json').read_text())['Version'] != r['baseline']:
        raise ValueError(name+': unexpected accepted baseline')
    sha = digest(cand/'mod/maps'/(r['map']+'.bsp'))
    if sha != digest(r['work']) or json.loads(r['validation'].read_text())['bsp_sha256'] != sha:
        raise ValueError(name+': stale validation')
    audit_shared(); audit(cand/'paks', r['map'])
    for rel in r['files']+('mod.json',):
        shutil.copy2(cand/rel, mod/rel)
        if digest(cand/rel) != digest(mod/rel):
            raise ValueError(name+': published payload differs '+rel)
    title = json.loads((mod/'mod.json').read_text()).get('Name', name)
    readme = (mod/'README.md').read_text(encoding='utf-8') if (mod/'README.md').exists() else ''
    head = f"# {name} {r['version']}"
    if not readme.startswith(head):
        (mod/'README.md').write_text(f"{head}\n\n{r['notes']}\n\n## Previous release notes\n\n{readme}", encoding='utf-8')
    status_path = mod/'build-status.json'
    if status_path.exists():
        status = json.loads(status_path.read_text()); status.update(version=r['version'], bsp_sha256=sha)
        status_path.write_text(json.dumps(status, indent=2)+'\n')
    docs = ROOT/'docs/candidates'/name/f"port-{r['version']}"; docs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(r['validation'], docs/'binary-validation.json')
    (docs/'README.md').write_text(f"{head}\n\n{r['notes']}\n", encoding='utf-8')
    persist(name, r['version'], r['notes'])
    import package_player_mods; importlib.reload(package_player_mods)
    result = package_player_mods.write_player_zip(mod, ROOT/'output'/f"{name}-{r['version']}-Northstar.zip")
    ledger_path = ROOT/'output/player-distributions.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    ledger[name] = result; ledger_path.write_text(json.dumps(ledger, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    for name in sys.argv[1:] or RELEASES:
        publish(name)
