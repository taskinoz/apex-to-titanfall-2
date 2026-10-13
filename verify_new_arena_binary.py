"""Independent native range, capacity, dependency and entity checks."""
import hashlib
import json
import struct
import sys
from new_arena_ports import CONFIG,ROOT,WORK,folder
from audit_world_draw_budget import audit
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from repair_environment_lighting import entities
from extract_native_material import NativePak


def check(ident):
    c=CONFIG[ident];mod=WORK/'candidates'/c['package'];bsp=mod/'mod/maps'/(c['target']+'.bsp')
    l=read_lumps(bsp,(0,2,3,4,0xe,0x42,0x45,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x65,0x67,0x68,0x69,0x77,0x78,0x79))
    checks=set()
    def require(condition,label):
        if not condition:raise ValueError(ident+': '+label)
        checks.add(label)
    require(bsp.read_bytes()[:8]==b'rBSP'+struct.pack('<I',37),'Native v37 header')
    validate_index_padding(l[0x50],l[0x4f],l[0x52]);checks.add('Padded native mesh/index ranges')
    validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51]);checks.add('Visibility references and spatial tree')
    budget=audit(bsp);require(budget['native_padded_indices']<3145728*.95,'Conservative world index capacity')
    require(budget['static_batch_runs']<512,'Static batch headroom for dynamic light masks')
    require(len(l[0x52])//12<8192,'Native material-sort capacity')
    require(len(l[0x50])//28<65535,'Native mesh reference capacity')
    vertices=len(l[3])//12;words=len(l[0x42])//4
    raw_words=struct.unpack('<'+'I'*words,l[0x42]);triangles=0
    for h in struct.iter_unpack('<6h4i4f',l[0x45]):
        require(h[7]>=0 and h[7]+h[4]<=words,'Collision triangle range')
        for value in raw_words[h[7]:h[7]+h[4]]:
            a=h[6]+(value&1023)
            require(max(a,a+(value>>10&127),a+(value>>17&127))<vertices,'Collision vertex reference')
        triangles+=h[4]
    require(len(l[0x45])//44<65535,'Native collision header capacity')
    require(len(l[0x65])%48==0 and len(l[0x68])%20==0 and len(l[0x67])%8==0,'Native probe record strides')
    pages=[struct.unpack_from('<I2H',l[0x53],i) for i in range(0,len(l[0x53]),8)]
    require(len(l[0x62])==sum(w*h*8 for v,w,h in pages),'Sky lightmap page lengths')
    require(len(l[0x69])==sum(w*h*8+(w//2)*(h//2)*4 for v,w,h in pages),'RTL lightmap page lengths')
    rows=entities(bsp);starts=[e for e in rows if e['classname']=='info_spawnpoint_human_start']
    require({e['teamnumber'] for e in starts}=={'2','3'},'Opposing team starts present')
    require(all(not any(k.startswith('*coll') for k in e) for e in rows),'No unsupported source collision blobs retained')
    known=set()
    for path in (ROOT/'inputs/tf2-rpak-work/common.raw.rpak',ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak'):
        pak=NativePak(path);known.update(a['guid'] for a in pak.assets)
    packages=[NativePak(p) for p in (mod/'paks').glob('*.rpak')]
    known.update(a['guid'] for p in packages for a in p.assets)
    for p in packages:
        for a in p.assets:
            if a['type']!='matl':continue
            spec,uber=p.material(a)
            refs=[spec['shaderSet'],*spec['$textures'].values(),*[spec[k] for k in
                ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]
            require(all(not int(v,16) or int(v,16) in known for v in refs),'Mounted material dependency closure')
    receipt=dict(map=c['target'],bsp_sha256=hashlib.sha256(bsp.read_bytes()).hexdigest(),
        passed_checks=len(checks),checks=sorted(checks),budget=budget,collision_triangles=triangles,
        native_player_validation_required=True)
    (folder(ident)/'binary-validation.json').write_text(json.dumps(receipt,indent=2))
    print(ident,'binary checks',len(checks), 'passed',flush=True)


if __name__=='__main__':
    for ident in CONFIG if sys.argv[1]=='all' else [sys.argv[1]]:check(ident)
