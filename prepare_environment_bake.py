"""Exclude only the photo sky dome, retaining the confirmed atlas and face IDs."""
import json,struct,hashlib
from prepare_lighting_scene import ROOT,SOURCE,OUT,np
from repair_preview_index_padding import read_lumps

def prepare():
    report=json.loads((OUT/'scene.json').read_text())
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=report['source_sha256']:
        raise ValueError('Atlas source changed')
    l=read_lumps(SOURCE,[2,0x2b,0x2c,0x50,0x52])
    names=[]
    for t in struct.iter_unpack('<3f6I',l[2]):
        at=struct.unpack_from('<I',l[0x2c],t[3]*4)[0]
        names.append(l[0x2b][at:l[0x2b].index(0,at)].decode().replace('\\','/'))
    sorts=list(struct.iter_unpack('<4hI',l[0x52]))
    sky=np.array(['phase_runner_sky' in names[sorts[m[-2]][0]] for m in struct.iter_unpack('<I3H6b2h2BHI',l[0x50])])
    atlas=np.load(OUT/'atlas.npz');mask=(~sky[atlas['meshid']]).astype(np.uint8)
    if not (mask==0).any() or not mask.any():raise ValueError('Sky/caster classification failed')
    mask.tofile(OUT/'environment-caster-mask.bin')
    proof=dict(atlas_source_sha256=report['source_sha256'],caster_triangles=int(mask.sum()),
        sky_triangles_excluded=int((mask==0).sum()),atlas_and_face_ids_preserved=True,
        excluded_materials=sorted({names[sorts[m[-2]][0]] for i,m in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])) if sky[i]}))
    (OUT/'environment-casters.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))
if __name__=='__main__':prepare()
