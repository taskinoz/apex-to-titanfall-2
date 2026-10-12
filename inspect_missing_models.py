import json,struct,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from read_vg_static import load
P=ROOT/'output/phase-runner'
def main():
    c=json.loads((ROOT/'logs/center-detail-candidates.json').read_text())
    mapping=json.loads((P/'world-materials/mapping.json').read_text())['materials'];mats={k.rsplit('/',1)[-1]:v for k,v in mapping.items()}
    models=collections.defaultdict(list)
    for p in c['missing']:
        if '/foliage/' not in p['model']:models[p['model']].append(p)
    for model,props in models.items():
        folder=ROOT/'tools/legion/exported_files/models'/Path(model).stem
        try:
            sections,slots,skins=load(folder,0)
            print(Path(model).stem, 'placements',len(props),'QC',bool(props[0]['source_qc']),'tris',sum(map(len,sections)),'materials',[(skins[props[0]['skin']][s],skins[props[0]['skin']][s] in mats) for s in slots])
        except Exception as e:print(Path(model).stem,'ERROR',str(e))
    name='veh_land_msc_truck_mod_police_lrg_01_closed_static';folder=ROOT/'tools/legion/exported_files/models'/name;data=(folder/(name+'.rmdl')).read_bytes();vg=(folder/(name+'.vg')).read_bytes()
    print('TRUCK RMDL offsets',struct.unpack_from('<9i',data,208))
    h=struct.unpack_from('<18Q',vg,16);mo,mc=h[2:4];lo,lc=h[12:14]
    print('VG lods',[struct.unpack_from('<2hf',vg,lo+i*8) for i in range(lc)])
    print('VG meshes',[(i,struct.unpack_from('<18I',vg,mo+i*72)) for i in range(mc)])
    bodies,bo=struct.unpack_from('<2i',data,236)
    for i in range(bodies):
        at=bo+i*16;no,mc,base,off=struct.unpack_from('<4i',data,at);n=at+no;print('BODY',data[n:data.index(0,n)],mc,base,off)
        for j in range(mc):
            atmodel=at+off+j*148;count,mesh=struct.unpack_from('<2i',data,atmodel+76);print('MODEL',j,'at',atmodel,'meshes',count,mesh,'bones',struct.unpack_from('<2i',data,156))
            print('slots',[(struct.unpack_from('<2i',data,atmodel+mesh+k*92)) for k in range(count)])
    print('candidate source qc non-foliage count',len([p for p in c['missing'] if '/foliage/' not in p['model'] and p['source_qc']]))
if __name__=='__main__':main()
