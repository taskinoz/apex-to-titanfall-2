"""Compare user-reported obstructions with actual collision and native bounds."""
import json,struct
from pathlib import Path
import numpy as np
from repair_preview_index_padding import read_lumps

ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'
POINTS=[(186,-5211,-955),(-1716,-3994,-963),(1221,-2481,-7)]

def audit():
    l=read_lumps(P/'preview-aligned/mp_phase_runner_preview.bsp',(1,0x5c,0x51,0x77,0x78,0x79))
    brushes=list(struct.iter_unpack('<3f2BH3fI',l[0x5c]));planes=np.frombuffer(l[1],dtype='<f4').reshape(-1,4)
    lo=np.array([r[:3] for r in brushes])-np.array([r[6:9] for r in brushes]);hi=2*np.array([r[:3] for r in brushes])-lo
    owners={}
    for folder,shift in [('preview-prop-physics',-424),('preview-structure-physics',0)]:
        name='prop-collision-placements.json' if shift else 'structure-collision-placements.json'
        for r in json.loads((P/folder/name).read_text())['restored']:
            for i in range(r['first_brush']+shift,r['first_brush']+shift+r['brushes']):owners[i]=r
    report={'locations':[],'native_bounds':{}}
    for point in POINTS:
        pt=np.array(point);near=np.flatnonzero(np.all(hi>=pt-256,axis=1)&np.all(lo<=pt+np.array([256,256,328]),axis=1))
        result=[]
        for i in near:
            r=brushes[i];qs=planes[1+r[9]:1+r[9]+r[4]]
            support=qs[:,3]-np.minimum(qs[:,:3]*[-16,-16,0],qs[:,:3]*[16,16,72]).sum(axis=1)
            inside=bool(np.all(pt>=lo[i]-[16,16,72]) and np.all(pt<=hi[i]+[16,16,0]) and np.all(qs[:,:3]@pt<=support+.05))
            result.append({'brush':int(i),'bounds':[lo[i].tolist(),hi[i].tolist()],'cuts':r[4],'original_cuts':r[3],'pilot_overlap':inside,'owner':owners.get(i,{'method':'world-surface-prism'})})
        result.sort(key=lambda r:(not r['pilot_overlap'],-np.linalg.norm(np.subtract(*r['bounds']))))
        report['locations'].append({'point':point,'nearby_count':len(result),'overlap_count':sum(r['pilot_overlap'] for r in result),'brushes':result})
    for label,path in [('preview',P/'preview-aligned/mp_phase_runner_preview.bsp'),('homestead',ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp'),('colony',ROOT/'inputs/titanfall2-colony/maps/mp_colony02.bsp')]:
        x=read_lumps(path,(0x51,0x78,0x79));m=np.frombuffer(x[0x51],dtype='<f4').reshape(-1,8);o=np.frombuffer(x[0x79],dtype='<f4').reshape(-1,8);refs=np.frombuffer(x[0x78],dtype='<u2');valid=refs<len(m);selected=m[refs[valid]];ob=o[valid]
        # Compare both possible encodings against referenced native mesh bounds.
        amin=selected[:,:3]-selected[:,4:7];amax=selected[:,:3]+selected[:,4:7]
        errors={
            'minmax':np.max(np.abs(ob[:,:3]-amin),axis=1)+np.max(np.abs(ob[:,4:7]-amax),axis=1),
            'center_extent':np.max(np.abs(ob[:,:3]-selected[:,:3]),axis=1)+np.max(np.abs(ob[:,4:7]-selected[:,4:7]),axis=1)}
        report['native_bounds'][label]={'meshes':len(m),'references':len(refs),'objects':len(o),'mesh_references':int(valid.sum()),'encoding_error_percentiles':{k:np.percentile(v,[0,50,95,100]).tolist() for k,v in errors.items()},'samples':[{'mesh':int(refs[i]),'mesh_bounds':m[refs[i]].tolist(),'object_bounds':o[i].tolist()} for i in np.flatnonzero(valid)[:3]],'mesh_last_float':np.percentile(m[:,7],[0,50,95,100]).tolist()}
    out=P/'reported-locations-0.1.23.json';out.write_text(json.dumps(report,indent=2))
    print(json.dumps({'locations':[{'point':r['point'],'nearby_count':r['nearby_count'],'overlap_count':r['overlap_count'],'first':r['brushes'][:5]} for r in report['locations']],'native_bounds':report['native_bounds']},indent=2))

if __name__=='__main__':audit()
