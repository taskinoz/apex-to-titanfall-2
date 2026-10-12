"""Create an explicitly incomplete Phase Runner geometry preview for MRVN-Radiant.

OBJ coordinates/winding compensate for the compiler's Assimp import transform.
The collision sample is thin convex prisms, not the authoritative final port.
"""
import argparse
import collections
import json
import math
from pathlib import Path

TRANSLATION = (26000., 19000., 0.)
MATERIAL = 'textures/world/dev/dev_gray_512'


def subtract(a, b):
    return tuple(x-y for x,y in zip(a,b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def brush(points, thickness=2.):
    normal = cross(subtract(points[1],points[0]),subtract(points[2],points[0]))
    magnitude = math.sqrt(sum(v*v for v in normal))
    if magnitude < 0.01:
        return None
    normal = tuple(v/magnitude for v in normal)
    bottom = [tuple(v[i]-normal[i]*thickness for i in range(3)) for v in points]
    center = tuple(sum(v[i] for v in points+bottom)/(len(points)*2) for i in range(3))
    planes = [points[:3], bottom[:3]]
    for i in range(len(points)):
        planes.append([points[i],points[(i+1)%len(points)],bottom[i]])
    result = ['{']
    for plane in planes:
        # Radiant computes a clockwise normal: cross(p2-p0, p1-p0).
        n = cross(subtract(plane[2],plane[0]),subtract(plane[1],plane[0]))
        if sum(n[i]*(plane[0][i]-center[i]) for i in range(3)) < 0:
            plane = [plane[0],plane[2],plane[1]]
        result.append(' '.join('( '+ ' '.join(f'{v:.6f}' for v in p)+' )' for p in plane)
                      + ' tools/toolsclip 0 0 0 1 1')
    result.append('}')
    return '\n'.join(result)


def build(render_obj, collision_obj, output, collision_limit):
    output.mkdir(parents=True,exist_ok=True)
    model = output/'assets/phase_runner_import.obj'
    model.parent.mkdir(parents=True,exist_ok=True)
    rendered = excluded = 0
    skip = False
    with render_obj.open() as source, model.open('w') as target:
        for line in source:
            if line.startswith('usemtl '):
                skip = line.split()[1].lower().startswith('tools/')
                continue
            if line.startswith(('v ','vn ')):
                p = tuple(map(float,line.split()[1:4]))
                if line.startswith('v '):
                    p = subtract(p,TRANSLATION)
                target.write(f'{line.split()[0]} {p[0]} {p[2]} {-p[1]}\n')
            elif line.startswith('f '):
                if skip:
                    excluded += 1
                else:
                    vertices = line.split()[1:]
                    target.write('f '+' '.join(reversed(vertices))+'\n')
                    rendered += len(vertices)-2
            elif not line.startswith(('mtllib ','g ','o ')):
                target.write(line)
    brushes = []
    probes = []
    recent = []
    contents = 0
    counts = collections.Counter()
    with collision_obj.open() as source:
        for line in source:
            if line.startswith('g contents_'):
                contents = int(line.strip().rsplit('_',1)[1],16)
                recent = []
            elif line.startswith('v '):
                recent.append(subtract(tuple(map(float,line.split()[1:])),TRANSLATION))
            elif line.startswith('f '):
                counts['source_polygons'] += 1
                # Apex's palette flags are not native Source contents flags.
                # For this diagnostic sample only, all recovered surfaces become solid.
                if len(brushes) >= collision_limit:
                    counts['limit_omitted'] += 1
                elif any(abs(v)>32000 for p in recent for v in p):
                    counts['coordinate_limit_omitted'] += 1
                else:
                    text = brush(recent)
                    if text:
                        brushes.append(text)
                        if len(probes)<12:
                            n=cross(subtract(recent[1],recent[0]),subtract(recent[2],recent[0]))
                            length=math.sqrt(sum(v*v for v in n))
                            center=tuple(sum(p[i] for p in recent)/len(recent) for i in range(3))
                            probes.append(dict(start=[center[i]+n[i]/length*16 for i in range(3)],
                                               end=[center[i]-n[i]/length*16 for i in range(3)]))
                    else:
                        counts['degenerate_omitted'] += 1
    # This spawn is an inspection point, not a verified playable spawn.
    origin = (0,0,2048)
    map_text = ['{','"classname" "worldspawn"','"mapversion" "220"',
                '"_geometry" "phase_runner_import.obj"',
                f'"_geometry_material" "{MATERIAL}"',*brushes,'}',
                '{','"classname" "info_player_start"',
                '"origin" "'+' '.join(map(str,origin))+'"','"angles" "0 0 0"','}']
    (output/'mp_phase_runner_preview.map').write_text('\n'.join(map_text)+'\n')
    shaders = output/'assets/shaders'
    shaders.mkdir(parents=True,exist_ok=True)
    (shaders/'preview.shader').write_text(
        f'{MATERIAL}\n{{\n $shadertype UnlitGeneric\n}}\n'
        'textures/tools/toolsclip\n{\n $contentflag solid\n $compileflag nodraw\n}\n')
    report = dict(map='mp_phase_runner_preview',render_triangles=rendered,
                  tool_render_faces_excluded=excluded,collision_sample_brushes=len(brushes),
                  collision_sample_limit=collision_limit,collision_counts=dict(counts),
                  translation=list(TRANSLATION),complete_port=False,in_game_verified=False,
                  collision_probes=probes,
                  collision_contents_translated=False,
                  limitations=['Missing static prop rendering','Sampled approximate world collision; all sample surfaces forced solid',
                               'Native fallback material; no Apex textures','Unverified inspection spawn'])
    (output/'source-build.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('render_obj',type=Path)
    parser.add_argument('collision_obj',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--collision-limit',type=int,default=1024)
    args = parser.parse_args()
    build(args.render_obj,args.collision_obj,args.output,args.collision_limit)
