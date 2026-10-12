"""Reclaim provably redundant box solids, then add original structural physics."""
import collections,json,math,shutil,struct
from pathlib import Path
from extend_prop_collision import box,slab,area,pack_grid
from read_prop_physics import read_phy,convex_planes,plane
from stage_prop_geometry import rotation,transform
from compact_preview_bsp import compact

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'output/phase-runner'

def merge_boxes(records,world_count):
    boxes=[(lo.copy(),hi.copy(),[i]) for i,(lo,hi,qs) in enumerate(records[:world_count]) if not qs]
    initial=len(boxes)
    while True:
        before=len(boxes)
        for axis in range(3):
            groups=collections.defaultdict(list)
            for lo,hi,ids in boxes:groups[tuple(v for k in range(3) if k!=axis for v in (lo[k],hi[k]))].append((lo,hi,ids))
            boxes=[]
            for entries in groups.values():
                entries.sort(key=lambda b:b[0][axis]);last=None
                for lo,hi,ids in entries:
                    # EXACT equal cross sections and overlapping/touching intervals.
                    # No tolerance bridges a gap, and no convex hull fills a recess.
                    if last is not None and lo[axis]<=last[1][axis]:
                        last[1][axis]=max(last[1][axis],hi[axis]);last[2].extend(ids)
                    else:last=(lo.copy(),hi.copy(),ids.copy());boxes.append(last)
        if len(boxes)==before:break
    remap={};result=[];proof=[]
    for lo,hi,ids in boxes:
        at=len(result);result.append((lo,hi,[]))
        for i in ids:remap[i]=at
        if len(ids)>1:proof.append(dict(original_brushes=ids,replacement=at,bounds=[lo,hi],method='exact_box_interval_union'))
    # Spatial bins avoid comparing every brush against every box.
    bins=collections.defaultdict(set);wide=[];step=512.
    for at,(lo,hi,_) in enumerate(result):
        xa,xb=math.floor(lo[0]/step),math.floor(hi[0]/step);ya,yb=math.floor(lo[1]/step),math.floor(hi[1]/step)
        if (xb-xa+1)*(yb-ya+1)>256:wide.append(at);continue
        for x in range(xa,xb+1):
            for y in range(ya,yb+1):bins[x,y].add(at)
    contained=0
    for i,(lo,hi,qs) in enumerate(records):
        if i in remap:continue
        owner=None
        if i<world_count:
            for at in sorted(bins[math.floor(lo[0]/step),math.floor(lo[1]/step)]|set(wide)):
                a,b,_=result[at]
                if all(a[k]<=lo[k] and b[k]>=hi[k] for k in range(3)):owner=at;break
        if owner is not None:
            remap[i]=owner;contained+=1;proof.append(dict(original_brushes=[i],replacement=owner,method='bounds_completely_inside_solid_box'))
        else:remap[i]=len(result);result.append((lo,hi,qs))
    return result,remap,dict(original_axis_boxes=initial,merged_axis_boxes=len(boxes),
        contained_nonbox_world_brushes_removed=contained,reclaimed_brushes=len(records)-len(result),
        union_preserved=True,proof=proof)

def clear_hull(point,records):
    hmin=(-16.,-16.,0.);hmax=(16.,16.,72.)
    for lo,hi,qs in records:
        if any(point[k]<lo[k]-hmax[k]-.05 or point[k]>hi[k]-hmin[k]+.05 for k in range(3)):continue
        if all(sum(q[k]*point[k] for k in range(3))<=q[3]-sum(min(q[k]*hmin[k],q[k]*hmax[k]) for k in range(3))+.05 for q in qs):return False
    return True

def build():
    source=PROJECT/'preview-prop-physics/mp_phase_runner_preview.bsp';out=PROJECT/'preview-structure-physics/mp_phase_runner_preview.bsp'
    status=json.loads(source.with_name('source-build.json').read_text())
    with source.open('rb') as f:
        h=f.read(2064)
        def lump(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
        oldplanes=lump(1);oldbrushes=lump(0x5c)
    records=[]
    for r in struct.iter_unpack('<3f2BH3fI',oldbrushes):
        qs=list(struct.iter_unpack('<4f',oldplanes[16+r[9]*16:16+(r[9]+r[4])*16]))
        records.append(([r[k]-r[k+6] for k in range(3)],[r[k]+r[k+6] for k in range(3)],qs))
    world_count=status['prop_physics']['unchanged_world_solids']
    records,remap,union=merge_boxes(records,world_count);reclaimed=union['reclaimed_brushes'];begin_count=len(records)
    props=json.loads((PROJECT/'static-props.json').read_text());restored=set()
    for p in PROJECT.glob('*-geometry/report.json'):restored.update(v['index'] for v in json.loads(p.read_text()).get('restored',[]))
    previous=json.loads(source.with_name('prop-collision-placements.json').read_text());already={p['index'] for p in previous['restored']}
    targets=[p for p in props if p['index'] in restored and p['index'] not in already and p['solid_mode'] in (2,6,7)
        and any(w in Path(p['model']).stem for w in ('railing','guard_rail','wall','floor','fence'))]
    def category(p):return 'railing' if any(w in p['model'] for w in ('railing','guard_rail')) else 'structure'
    targets.sort(key=lambda p:(category(p)!='railing',sum(v*v for v in p['origin'][:2]),p['index']))
    cache={};done=[];skipped=[];candidates=[];tube_budget=128
    def append(result,p,kind):
        points,qs=result;lo,hi=box(points);cuts=[q for q in qs if not any(abs(abs(v)-1)<1e-7 for v in q[:3])]
        if len(cuts)>255 or any(abs(v)>32750 for v in lo+hi):raise ValueError('Original structural physics exceeds native brush format')
        at=len(records);records.append((lo,hi,cuts));center=[sum(v[k] for v in points)/len(points) for k in range(3)]
        candidates.append(dict(kind=kind,source_prop=p['index'],brush_index=at,end=center,prop_probe=True))
    for p in targets:
        name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
        if not base.with_suffix('.phy').is_file():skipped.append(dict(index=p['index'],reason='Original convex physics unavailable'));continue
        if name not in cache:
            checksum=struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]
            cache[name]=read_phy(base.with_suffix('.phy'),checksum)
        matrix=rotation(p['angles']);results=[convex_planes([[transform(v,matrix,p['origin'],p['scale']) for v in face] for face in piece]) for piece in cache[name]]
        if any(r is None for r in results):raise ValueError('Original structural piece is not convex')
        if len(records)+len(results)>65535-tube_budget:skipped.append(dict(index=p['index'],reason='Reserved room for tube floors'));continue
        first=len(records)
        for result in results:append(result,p,category(p))
        done.append(dict(index=p['index'],model=p['model'],kind=category(p),method='original_IRPS_convex',first_brush=first,brushes=len(results)))
    portal_reports=[]
    for p in [p for p in props if p['index'] in (16729,16730)]:
        name=Path(p['model']).stem;fs=json.loads((PROJECT/'prop-physics'/(name+'.json')).read_text())['polygons'];matrix=rotation(p['angles'])
        # Retain every previous portal prism and supplement walkable surfaces.
        fs.sort(key=area,reverse=True);old_selected=259;new=[]
        for face in fs[old_selected:]:
            placed=[transform(v,matrix,p['origin'],p['scale']) for v in face];q=plane(placed)
            if q is None or abs(q[2])<.7:continue
            result=slab(placed)
            if result is not None:new.append((area(placed),result))
        new.sort(key=lambda v:-v[0]);first=len(records)
        for size,result in new[:min(tube_budget//2,65535-len(records))]:append(result,p,'tube-floor')
        portal_reports.append(dict(index=p['index'],added_walkable_surface_prisms=len(records)-first,
            added_surface_area=sum(size for size,_ in new[:len(records)-first]),complete=False))
    probes=[];owners=collections.Counter()
    for candidate in candidates:
        kind=candidate['kind'];owner=candidate['source_prop']
        if sum(p['kind']==kind for p in probes)>=8 or owners[owner]>=4:continue
        lo,hi,qs=records[candidate['brush_index']];end=candidate['end'];start=None
        for extra in (80.,160.,320.):
            for axis in (2,0,1):
                for side in (1,-1):
                    p=end.copy();p[axis]=hi[axis]+extra if side>0 else lo[axis]-extra-(72 if axis==2 else 0)
                    if clear_hull(p,records):start=p;break
                if start:break
            if start:break
        if start:probes.append(dict(candidate,start=start,clear_pilot_hull_start_verified=True));owners[owner]+=1
    if any(sum(p['kind']==k for p in probes)<8 for k in ('railing','structure','tube-floor')):raise ValueError('Insufficient independent structural probes')
    for p in status['collision_probes']:p['brush_index']=remap[p['brush_index']]
    status['collision_probes'].extend(probes)
    brushes=bytearray();planes=bytearray(oldplanes[:16]);offsets=bytearray();properties=bytearray();textures=bytearray()
    for i,(lo,hi,qs) in enumerate(records):
        c=[(lo[k]+hi[k])/2 for k in range(3)];e=[(hi[k]-lo[k])/2 for k in range(3)];first=len(offsets)//2
        brushes.extend(struct.pack('<3f2BH3fI',*c,len(qs),len(qs),i,*e,first));properties.extend(struct.pack('<'+'H'*(6+len(qs)),*([0]*6+[1]*len(qs))));textures.extend(bytes(32*(6+len(qs))))
        for q in qs:planes.extend(struct.pack('<4f',*q));offsets.extend(bytes(2))
    replacements={1:planes,0x5c:brushes,0x5d:offsets,0x5e:properties,0x5f:textures,**pack_grid([(lo,hi) for lo,hi,_ in records])}
    report=compact(source,out,replacements)
    status['structure_physics']=dict(reclaimed_brushes=reclaimed,added_brushes=len(records)-begin_count,
        added_original_convex_placements=len(done),railing_placements=sum(p['kind']=='railing' for p in done),
        structure_placements=sum(p['kind']=='structure' for p in done),tube_floor_surfaces=portal_reports,
        existing_world_and_prop_collision_union_preserved=True,strict_new_hull_probes=len(probes),
        original_placement_transforms_and_physics_verified=True,complete=False,client_movement_verified=False,
        limitation='Native brush capacity still limits coverage; tube floor additions are partial. No solid box fills hollow tubes.')
    status['collision_sample_brushes']=len(records);status['final_compaction']=report
    out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('structure-collision-placements.json').write_text(json.dumps(dict(restored=done,skipped=skipped,probes=probes,box_union=union),indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,out.parent/p.name)
    shutil.copy2(source.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
    print(json.dumps(status['structure_physics'],indent=2))

if __name__=='__main__':build()
