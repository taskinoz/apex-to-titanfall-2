"""Native photographs and collision checks for the recovered attachments."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'));sys.path.insert(0,str(ROOT/'test-harness'))
import numpy as np
from harness import Controller
from recover_composite_details import collision,smd_arm
from read_vg_static import load
OUT=ROOT/'output/composite';WORK=OUT/'detail-recovery'

def verify():
    c=Controller();s=c.request('/status')
    if s.get('contexts',{}).get('client',{}).get('level')!='mp_arena_composite':raise ValueError('Wrong active map')
    result=dict(version='0.4.0',traces=[],views=[])
    rows={p['index']:p for p in json.loads((WORK/'result.json').read_text())['placements']}
    for index in (1651,1652,1669,1670,4960,4974,4994,4995):
        p=rows[index];sections=smd_arm()[0] if index in (1651,1652,1669,1670) else load(p['folder'],p['lod'])[0]
        col,method=collision(p,sections);normal=np.cross(col[:,1]-col[:,0],col[:,2]-col[:,0]);area=np.linalg.norm(normal,axis=1)
        j=int(area.argmax());normal=normal[j]/area[j];center=col[j].mean(0);start=center+normal*15;end=center-normal*15
        trace=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),map(float,[*start,*end]))))
        result['traces'].append(dict(index=index,expected_surface=center.tolist(),trace=trace))
    for name,pos,angle in [('west-upper-arm',[-285,4045,330],[12,135,0]),
                           ('east-upper-arm',[285,4045,330],[12,45,0]),
                           ('west-lower-arm',[-580,2640,375],[12,135,0]),
                           ('east-lower-arm',[580,2640,375],[12,45,0]),
                           ('court',[0,1950,300],[-6,90,0]),
                           ('interior',[-3050,1300,225],[0,25,0])]:
        c.camera(pos,angle);result['views'].append(dict(name=name,capture=c.capture('dropoff-040-'+name)))
    c.command('client','camera_clear');result['counts']=c.command('server','mode_check');result['logs']=c.export_logs()
    (WORK/'runtime.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(views=[v['capture']['path'] for v in result['views']],traces=result['traces'],logs=result['logs']),indent=2))

if __name__=='__main__':verify()
