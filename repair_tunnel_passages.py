"""Open only tool-material end caps inside portal apertures; fit frame physics."""
import collections,json,shutil,struct,time
from pathlib import Path
import numpy as np
from audit_world_collision_contents import ROOT,P,load_world
from repair_preview_index_padding import read_lumps
from stage_prop_geometry import rotation
from native_triangle_collision import encode,collision_grid
from compact_preview_bsp import compact
from read_vg_static import load

SOURCE=P/'preview-tunnel-detail/mp_phase_runner_preview.bsp'
TARGET=P/'preview-tunnel-passages/mp_phase_runner_preview.bsp'

def split(poly,n,d):
    inside=[];outside=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=float(a@n-d);db=float(b@n-d)
        (inside if da<=0 else outside).append(a)
        if (da<=0)!=(db<=0):
            p=a+(b-a)*(da/(da-db));inside.append(p);outside.append(p)
    return inside,outside

def subtract_aperture(face,matrix,origin,scale):
    poly=[(v-origin)@matrix/scale for v in face];parts=[]
    # Cut a 32-sided cylindrical opening, aligned with the authored ring.
    planes=[(np.array([0,1.,0]),250.),(np.array([0,-1.,0]),250.)]
    planes += [(np.array([np.cos(a),0,np.sin(a)]),193.5) for a in np.arange(32)*np.pi/16]
    for n,d in planes:
        poly,outside=split(poly,n,d)
        if len(outside)>=3:parts.append(outside)
        if len(poly)<3:return [face],False
    kept=[]
    for p in parts:
        for i in range(1,len(p)-1):
            t=np.asarray([p[0],p[i],p[i+1]])@matrix.T*scale+origin
            t=t.astype('<f4')
            if np.linalg.norm(np.cross(t[1]-t[0],t[2]-t[0]))>1e-5:kept.append(t)
    return kept,True

def remap_grid(bounds,tri_bounds,brush_ids,header_ids):
    grid=collision_grid(bounds,tri_bounds)
    def actual(word):
        kind=word>>24;index=(word>>8)&65535
        return (kind<<24)|((brush_ids[index] if kind==0 else header_ids[index])<<8)|(word&255)
    for at in range(0,len(grid[0x59]),4):struct.pack_into('<I',grid[0x59],at,actual(struct.unpack_from('<I',grid[0x59],at)[0]))
    for at in range(0,len(grid[0x57]),8):
        if struct.unpack_from('<H',grid[0x57],at+2)[0]==1:struct.pack_into('<I',grid[0x57],at+4,actual(struct.unpack_from('<I',grid[0x57],at+4)[0]))
    return grid

def build():
    started=time.monotonic();world,world_headers=load_world()
    labels=json.loads((ROOT/'logs/world-source-materials.json').read_text())
    props=json.loads((P/'static-props.json').read_text());rings=[p for p in props if p['in_arena'] and 'wraith_tt_portal_large' in p['model']]
    mats=[np.asarray(rotation(p['angles'])) for p in rings]
    allowed={'tools/toolsclip','tools/toolsclip_human','tools/toolsnodraw','tools/toolsblack'}
    changed={};events=[];normals=np.cross(world[:,1]-world[:,0],world[:,2]-world[:,0]);normals/=np.linalg.norm(normals,axis=1)[:,None]
    for i,t in enumerate(world):
        if abs(normals[i,2])>.2 or not any(s.lower().replace('\\','/') in allowed for s in labels[i]):continue
        current=[t];affected=[]
        for p,m in zip(rings,mats):
            if abs(normals[i]@m[:,1])<.9:continue
            local=(t-p['origin'])@m/p['scale'];lo=local.min(0);hi=local.max(0)
            if np.any(lo>[194,250,194]) or np.any(hi<[-194,-250,-194]):continue
            next_parts=[];cut=False
            for face in current:
                pieces,did=subtract_aperture(face,m,np.array(p['origin']),p['scale']);next_parts.extend(pieces);cut|=did
            if cut:affected.append(p['index']);current=next_parts
        if affected:
            changed[i]=current;events.append(dict(triangle=i,materials=labels[i],rings=affected,retained_triangles=len(current)))
    if not changed:raise ValueError('No verified tunnel caps found')
    ids=(3,0x42,0x44,0x45,0x60,0x61,0x5c)
    l=read_lumps(SOURCE,ids);headers=list(struct.iter_unpack('<6h4i4f',l[0x45]));old_header_count=len(headers)
    if old_header_count>=65000:raise ValueError('Insufficient native header capacity')
    ownership=json.loads((P/'preview-full-collision/collision-ownership.json').read_text())
    groups=[];disabled_headers=set();cursor=0;replacement_headers={}
    for hidx,h in enumerate(headers[:world_headers]):
        selected=set(range(cursor,cursor+h[4]))&changed.keys()
        if selected:
            disabled_headers.add(hidx);faces=[]
            for i in range(cursor,cursor+h[4]):faces.extend(changed.get(i,[world[i]]))
            first=old_header_count+len(groups)
            for at in range(0,len(faces),96):groups.append(faces[at:at+96])
            replacement_headers[hidx]=dict(first_header=first,headers=old_header_count+len(groups)-first,triangles=len(faces))
        cursor+=h[4]
    sections,slots,skins=load(ROOT/'tools/legion/exported_files/models/wraith_tt_portal_large',0)
    frame=np.array([tri for section,slot in zip(sections,slots) if skins[0][slot]=='trim_metal_01' for tri in section],dtype='<f4')[:,:,:3]
    if len(frame)!=2304:raise ValueError('Unexpected portal frame mesh')
    disabled_brushes=set();owners={o['index']:o for o in ownership['owners']};ring_reports=[]
    for p,m in zip(rings,mats):
        owner=owners[p['index']];old=dict(owner);disabled_brushes.update(range(owner['first_brush'],owner['first_brush']+owner['brushes']))
        tri=(frame@m.T*p['scale']+p['origin']).astype('<f4');first=old_header_count+len(groups)
        for at in range(0,len(tri),96):groups.append(tri[at:at+96])
        owner.update(method='visual_frame_surface_replacement',brushes=0,first_header=first,headers=len(groups)+old_header_count-first,triangles=len(tri),source_faces=len(frame))
        ring_reports.append(dict(index=p['index'],old=old,replacement=dict(owner),energy_disk_nonsolid=True))
    enc,new_bounds=encode(groups,len(l[3])//12)
    for at in range(0,len(enc[0x45]),44):
        struct.pack_into('<i',enc[0x45],at+16,struct.unpack_from('<i',enc[0x45],at+16)[0]+len(l[0x42])//4)
        struct.pack_into('<i',enc[0x45],at+20,struct.unpack_from('<i',enc[0x45],at+20)[0]+len(l[0x44])//16)
    positions=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);tri_bounds=[];header_ids=[]
    for i,h in enumerate(headers):
        if i in disabled_headers:continue
        v=positions[h[6]:h[6]+h[3]];tri_bounds.append((v.min(0).tolist(),v.max(0).tolist()));header_ids.append(i)
    tri_bounds.extend(new_bounds);header_ids.extend(range(old_header_count,old_header_count+len(groups)))
    bounds=[];brush_ids=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
        if i in disabled_brushes:continue
        center=np.array(r[:3]);extent=np.array(r[6:9]);bounds.append(((center-extent).tolist(),(center+extent).tolist()));brush_ids.append(i)
    grid=remap_grid(bounds,tri_bounds,brush_ids,header_ids)
    changes={i:l[i]+enc[i] for i in (3,0x42,0x44,0x45,0x60)};changes.update(grid)
    proof=compact(SOURCE,TARGET,changes)
    report=dict(version='0.1.30',modified_world_triangles=len(changed),disabled_world_headers=sorted(disabled_headers),world_header_replacements=replacement_headers,
        cap_adaptations=events,portal_frame_replacements=ring_reports,disabled_convex_brushes=sorted(disabled_brushes),
        active_convex_brushes=len(brush_ids),active_triangle_headers=len(header_ids),appended_triangle_headers=len(groups),
        cut_radius_source_units=193.5,cut_half_depth_source_units=250,cut_sides=32,allowed_materials=sorted(allowed),
        unmodified_world_and_model_collision_records_byte_preserved=True,original_position_prefix_byte_preserved=True,
        original_tunnel_physics_preserved=True,rendering_lumps_byte_unchanged=True,compaction=proof,
        engine_passage_sweeps_verified=False,client_movement_verified=False,elapsed_seconds=time.monotonic()-started)
    status=json.loads(SOURCE.with_name('source-build.json').read_text());status['tunnel_collision_repair']=report
    status['full_collision_rebuild']['subsequent_tunnel_aperture_adaptations']='See tunnel_collision_repair; full source fidelity excludes the deliberately opened tool caps and visual-frame replacements.'
    status['world_draw_budget_repair']['limitation']='Fixed source LODs with full-detail tunnels; material/PBR approximations remain. Rendering has been confirmed by the user in 0.1.29; tunnel traversal requires separate verification.'
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2));TARGET.with_name('collision-ownership.json').write_text(json.dumps(ownership,indent=2))
    TARGET.with_name('tunnel-collision-repair.json').write_text(json.dumps(report,indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    for f in SOURCE.parent.glob(SOURCE.stem+'_*.ent'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps({k:v for k,v in report.items() if k not in ('cap_adaptations','portal_frame_replacements','world_header_replacements','compaction','disabled_convex_brushes','disabled_world_headers')},indent=2),flush=True)
    print('Modified cap material counts',dict(collections.Counter(s for e in events for s in e['materials'])),flush=True)

if __name__=='__main__':build()
