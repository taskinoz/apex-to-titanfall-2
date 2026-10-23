"""Build isolated native previews using the verified arena primitives."""
import argparse
import json
import math
import os
import struct
import sys
from pathlib import Path
from new_arena_ports import CONFIG, ROOT, folder, source_bsp

sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
import numpy as np

SKY = {'overflow': 'aqueduct_sky', 'party-crasher': 'party_crasher_night_sky',
       'firing-range': 'canyonlands_hu_sky', 'thermal-station': 'desertlands_sky_mu1',
       'thunderdome': 'canyonlands_hu_sky'}  # Thunderdome is in Kings Canyon; its skydome is a model material


def collisions(ident):
    from decode_collision import decode
    out = folder(ident)
    decoded = out / 'collision/source'
    if not (decoded / 'collision-recovery.json').exists():
        report = decode(source_bsp(ident), decoded)
        if report['errors']:
            raise ValueError('Source collision has invalid records')
    offset = CONFIG[ident]['offset']
    target = out / 'collision/world-collision-regular.obj'
    with (decoded / target.name).open() as src, target.open('w') as dest:
        for line in src:
            if line.startswith('v '):
                values = [float(a) + b for a, b in zip(line.split()[1:4], offset)]
                dest.write('v ' + ' '.join(map(str, values)) + '\n')
            else:
                dest.write(line)


def materials(ident):
    import prepare_composite_materials as stage
    out = folder(ident)
    stage.OUT = out / 'materials'
    stage.prepare(out / 'scene.json', [out / 'legion/exported_files/materials'],
                  ident.replace('-', '_'), SKY[ident])


def native(ident):
    import build_composite_map as builder
    c = CONFIG[ident]
    out = folder(ident)
    builder.OUT = out
    builder.MAP = c['target']
    builder.SOURCE_BSP = source_bsp(ident)
    builder.PAK_NAME = ident.replace('-', '_') + '_world'
    builder.build()
    configure_native_environment(ident)


def configure_native_environment(ident):
    """Use this source sun and move the complete native menu outside the sky."""
    from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
    from repair_environment_lighting import entities, text_entities
    from repair_preview_index_padding import read_lumps
    from compact_preview_bsp import compact
    c = CONFIG[ident]
    out = folder(ident)
    source = out / (c['target'] + '.bsp')
    report = json.loads((out / 'scene.json').read_text())
    env = report['source_sun']
    l = read_lumps(source, (0, 5, 0x36))
    lights = [WorldLightv3.from_bytes(l[0x36][i:i + 112]) for i in range(0, len(l[0x36]), 112)]
    pitch, yaw = [math.radians(float(v)) for v in env['angles'].split()[:2]]
    normal = [math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), -math.sin(pitch)]
    values = [float(v) for v in env['_light'].split()]
    lights[2].normal = normal
    lights[2].origin = [0, 0, 12000]
    lights[2].intensity = ((np.asarray(values[:3]) / 255) ** 2.2 * min(1.25, values[3] / 510)).tolist()
    # Matching ambient surface/probe bake follows in the lighting stage.
    lights[0].origin = [0, 0, 2048]
    lights[0].intensity = [.055, .07, .085]
    delta = np.asarray([-13224., 12144., 11264.])
    for i in (1, 3):
        lights[i].origin = (np.asarray(list(lights[i].origin)) + delta).tolist()
    rows = entities(source)
    for e in rows:
        if e.get('script_name') in ('menu_scene_ref', 'menu_camera_target') or e.get('lightEnvironmentIndex') == '*1':
            e['origin'] = ' '.join(map(str, np.asarray([float(v) for v in e['origin'].split()]) + delta))
        elif e.get('classname') == 'light_environment' and e.get('lightEnvironmentIndex') == '*0':
            e.update(origin='0 0 12000', angles=env['angles'], pitch=env['pitch'],
                     _light=env['_light'], _ambient=env['_ambient'], targetname=ident + '_sun',
                     cloudoffset='0 0 0 0')
    # Remove the old Composite provisional markers. Source-aligned starts are
    # generated separately and must pass native hull/floor probes before release.
    rows = [e for e in rows if not e.get('classname', '').startswith('info_spawnpoint')
            and e.get('classname') != 'info_player_start']
    starts = initial_starts(ident, report)
    rows.extend(starts)
    shadow = bytearray(l[5])
    struct.pack_into('<3f', shadow, 24, *normal)
    temp = source.with_suffix('.environment.bsp')
    compact(source, temp, {0: text_entities(rows), 5: shadow, 0x36: b''.join(w.as_bytes() for w in lights)})
    os.replace(temp, source)
    (out / 'environment.json').write_text(json.dumps(dict(source_sun=env, native_sun_normal=normal,
        menu_delta=delta.tolist(), starts=starts, starts_native_verified=False), indent=2))


def initial_starts(ident, report):
    """Select source markers as candidates; native contact tests refine them."""
    c = CONFIG[ident]
    source = [e for e in report['source_entities'] if e.get('classname') in
              ('info_spawnpoint_human', 'info_spawnpoint_human_start', 'info_player_start') and 'origin' in e]
    offset = np.asarray(c['offset'])
    local = []
    for e in source:
        p = np.asarray([float(v) for v in e['origin'].split()]) + offset
        if np.all(p >= c['bounds'][0]) and np.all(p <= c['bounds'][1]):
            local.append((p, e.get('angles', '0 0 0')))
    if not local:
        # Authored arena spawn markers can be absent in client partitions.
        guesses = {'overflow': [[-4000, -5400, 320], [3800, -5600, 320]],
                   'party-crasher': [[-3200, -1600, 1100], [3300, 2400, 1100]],
                   'firing-range': [[2000, -500, 0], [-2000, -500, 0]],
                   # R5R deathmatch spawns at the west and east platforms (+ offset).
                   'thermal-station': [[-3019, -28, -10], [2760, -210, 27]]}
        local = [(np.asarray(p), '0 0 0') for p in guesses[ident]]
    if len(local) > 48:
        local = local[::max(1, len(local) // 48)][:48]
    median = float(np.median([p[0] for p, a in local]))
    rows = []
    for p, angle in local:
        team = 2 if p[0] <= median else 3
        origin = ' '.join(map(str, p + [0, 0, 8]))
        for cls, number in (('info_spawnpoint_human_start', team), ('info_spawnpoint_human', 0)):
            rows.append(dict(classname=cls, origin=origin, angles=angle, teamnumber=str(number),
                             gamemode_tdm='1', gamemode_ps='1', gamemode_ffa='1'))
    rows.append(dict(classname='info_player_start', origin=rows[0]['origin'], angles=rows[0]['angles']))
    return rows


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['collision', 'materials', 'native'])
    p.add_argument('map', choices=[*CONFIG, 'all'])
    a = p.parse_args()
    for ident in CONFIG if a.map == 'all' else [a.map]:
        dict(collision=collisions, materials=materials, native=native)[a.action](ident)
