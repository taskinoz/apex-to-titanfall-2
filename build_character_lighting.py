"""Add only native moving-model probes, their KD tree and parent range."""
import itertools,json,math,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from scipy.spatial import cKDTree
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
SOURCE=ROOT/'output/phase-runner/phase-runner-catwalks/mp_phase_runner.bsp'
OUT=ROOT/'output/phase-runner/character-lighting'
TARGET=OUT/'mp_phase_runner.bsp'

def positions():
    # Coarse upper/ejection coverage and closer ground-level pilot/Titan samples.
    coarse=list(itertools.product(range(-8192,8193,512),range(-8192,8193,512),[-2048,-1536,-1280,-1024,-768,-512,-256,0,512,1024,2048,4096]))
    dense=list(itertools.product(range(-6400,6401,256),range(-8192,4097,256),[-1408,-1216,-1024,-832,-640,-448,-256,0,384,768]))
    special=[];routes=json.loads((SOURCE.parent/'catwalks.json').read_text())['routes']
    for route in routes:
        p=np.array(route['points']);dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        for d in np.linspace(0,dist[-1],math.ceil(dist[-1]/64)+1):
            k=min(len(p)-2,np.searchsorted(dist,d,side='right')-1);f=(d-dist[k])/(dist[k+1]-dist[k]);q=p[k]*(1-f)+p[k+1]*f
            side=np.array([-(p[k+1,1]-p[k,1]),p[k+1,0]-p[k,0],0]);side/=np.linalg.norm(side)
            for width in (-20,0,20):
                for z in (32,64,144):special.append(q+side*width+[0,0,z])
    fixtures=json.loads((ROOT/'northstar/PhaseRunner.Preview/interior-lights.json').read_text())['lights']
    for light in fixtures:
        p=np.array(light['origin'])
        for x,y,z in itertools.product((-192,-96,0,96,192),(-192,-96,0,96,192),(-128,-32,64)):
            special.append(p+[x,y,z])
    return np.unique(np.array(coarse+dense+[list(p) for p in special],'<f4'),axis=0),fixtures

def make_tree(points):
    nodes=[[0,0]];refs=[]
    def emit(index,ids):
        if len(ids)<=8:
            first=len(refs);refs.extend(ids.tolist());nodes[index]=[(first<<2)|3,len(ids)];return
        axis=int(np.ptp(points[ids],axis=0).argmax());order=ids[np.argsort(points[ids,axis],kind='stable')];mid=len(order)//2
        cut=float((float(points[order[mid-1],axis])+float(points[order[mid],axis]))/2)
        first=len(nodes);nodes.extend([[0,0],[0,0]]);nodes[index]=[(first<<2)|axis,struct.unpack('<I',struct.pack('<f',cut))[0]]
        emit(first,order[:mid]);emit(first+1,order[mid:])
    emit(0,np.arange(len(points)))
    return np.array(nodes,'<u4').tobytes(),np.array(refs,np.int64)

def build():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    l=read_lumps(SOURCE,(4,6,7,0x65,0x67,0x68,0x7c,0x7e,0x7f))
    if any(l[i] for i in (4,6,7,0x65,0x67,0x68)):raise ValueError('Expected unlit moving-model baseline')
    points,fixtures=positions();points.tofile(OUT/'positions.bin')
    # World shadow geometry already excludes the photographic sky.
    p=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);ix=np.frombuffer(l[0x7e],'<u2');tri=[];at=0
    for base,count,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
        if (opaque,sort)!=(1,-1):raise ValueError('Unsupported shadow stream')
        tri.append(p[base+ix[at:at+count*3].astype(np.uint32)].reshape(-1,3,3));at+=count*3
    np.concatenate(tri).tofile(OUT/'casters.bin')
    rows=[[*light['origin'],light['radius'],*light['colour'],light['hardware_index']] for light in fixtures]
    dtype=np.dtype([('position','<f4',3),('radius','<f4'),('colour','<f4',3),('index','<u4')])
    a=np.zeros(len(rows),dtype)
    for i,row in enumerate(rows):a[i]=(row[:3],row[3],row[4:7],row[7])
    a.tofile(OUT/'fixtures.bin')
    result=subprocess.run([str(ROOT/'tools/bake_character_probes.exe'),str(OUT/'casters.bin'),str(OUT/'positions.bin'),str(OUT/'fixtures.bin'),str(OUT/'lighting.bin')],capture_output=True,text=True,check=True)
    (OUT/'bake.log').write_text(result.stdout+result.stderr);print(result.stdout,flush=True)
    values=np.fromfile(OUT/'lighting.bin','<f4').reshape(len(points),24)
    if not np.isfinite(values).all():raise ValueError('Nonfinite lighting')
    probes=bytearray()
    for row in values:
        probes.extend(struct.pack('<16h4B4hI',*np.rint(np.clip(row[:16]*8192,-32768,32767)).astype(int),*row[16:20].astype(int),*row[20:24].astype(int),0))
    # Keep the isolated menu stage lit using native samples, without unrelated point-light links.
    native=read_lumps(ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp',(0x65,0x68));menu=[]
    for x,y,z,probe,unknown in struct.iter_unpack('<3fIi',native[0x68]):
        if abs(x+11776)<1024 and abs(y-11856)<1024 and abs(z-12736)<1024:
            record=bytearray(native[0x65][probe*48:(probe+1)*48]);record[32:44]=bytes(4)+struct.pack('<4h',-1,-1,-1,-1)
            menu.append((x,y,z));probes.extend(record)
    if not menu:raise ValueError('Native menu samples missing')
    allpoints=np.concatenate((points,np.array(menu,'<f4')));tree,order=make_tree(allpoints)
    references=b''.join(struct.pack('<3fIi',*allpoints[i],int(i),0) for i in order)
    parent=struct.pack('<i6I',0,0,len(allpoints),0,len(allpoints),0,len(tree)//8)
    changes={4:parent,0x65:probes,0x67:tree,0x68:references}
    proof=compact(SOURCE,TARGET,changes)
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    np.savez(OUT/'probe-proof.npz',positions=allpoints,values=values,reference_order=order)
    report=dict(version='0.1.38',source_version='0.1.37',map_name=TARGET.stem,gameplay_probes=len(points),menu_probes=len(menu),
        total_probes=len(allpoints),sunlit_probes=int((values[:,15]>.5).sum()),local_lit_probes=int((values[:,16:20]>0).any(1).sum()),
        tree_nodes=len(tree)//8,probe_bytes=len(probes),probe_lookup='Native KD fallback; optional BSP accelerator remains absent.',
        native_decoder_scale=1/8192,native_ambient_layout='Three signed fixed-point XYZ/W directional ambient coefficients, one set per RGB channel.',
        native_probe_stride=48,sky_and_sun_visibility_baked=True,maximum_local_lights=4,local_light_indices='Filtered native hardware world lights; loader adds reserved dynamic-light offset 32.',
        sky_decorative_geometry_excluded=True,bsp_unchanged_except=sorted(changes),world_geometry_collision_visibility_and_surface_lighting_preserved=True,
        probes_include_both_complete_catwalks_buildings_and_ejection_space=True,fixture_count=len(fixtures),
        native_evidence=['logs/native-reader-engine-0xcd050.txt','logs/native-reader-engine-0xc7a90.txt','logs/native-range-0xc7e74.txt','logs/native-range-0xc8fc0.txt'],
        compaction=proof,elapsed_seconds=time.monotonic()-start,client_lighting_verified=False,
        limitations='Direct sun/sky and local visibility with small artistic ambient fill; no bounced GI or new reflection cubemaps. Interior and airborne samples need client visual confirmation.')
    (OUT/'character-lighting.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='compaction'},indent=2),flush=True)
if __name__=='__main__':build()
