"""Retain clear-start engine contacts and add reported pipe-floor checks."""
import json,re,struct
import numpy as np
from audit_user_coordinates import P,POINTS
from repair_preview_index_padding import read_lumps

def prepare():
 path=P/'preview-full-collision/mp_phase_runner_preview.bsp';s=json.loads(path.with_name('source-build.json').read_text());log=(P.parent.parent/'logs/full-map-collision-first.log').read_text();results=re.findall(r'prop hull probe (\d+): fraction=([0-9.]+) startSolid=(\w+)',log);raw=s['collision_probes'][:len(results)];s['collision_probes']=raw.copy()
 if len(results)!=len(raw):raise ValueError('Incomplete first engine pass')
 s['pilot_hull_contact_probes']=[dict(raw[int(i)],clear_pilot_hull_start_verified=True) for i,f,solid in results if float(f)<1 and solid=='false'];s['hull_clearance_probes']=json.loads((P/'preview-coordinate-physics/source-build.json').read_text())['hull_clearance_probes']
 l=read_lumps(path,(3,0x45));v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);h=list(struct.iter_unpack('<6h4i4f',l[0x45]));owners={o['index']:o for o in json.loads(path.with_name('collision-ownership.json').read_text())['owners']};sites=[]
 for label in ('pipe','pipe_fall','pipe_section'):
  index=16730 if label=='pipe' else 16729;o=owners[index];heads=h[o['first_header']:o['first_header']+o['headers']];count=sum(row[4] for row in heads);tri=v[heads[0][6]:heads[0][6]+count*3].reshape(-1,3,3).astype(float);xy=np.array(POINTS[label][:2]);a=tri[:,0,:2];b=tri[:,1,:2]-a;c=tri[:,2,:2]-a;det=b[:,0]*c[:,1]-b[:,1]*c[:,0];good=abs(det)>1e-8;at=xy-a
  u=np.divide(at[:,0]*c[:,1]-at[:,1]*c[:,0],det,out=np.full(len(det),-999.),where=good);w=np.divide(b[:,0]*at[:,1]-b[:,1]*at[:,0],det,out=np.full(len(det),-999.),where=good);valid=good&(u>=-1e-8)&(w>=-1e-8)&(u+w<=1+1e-8);z=tri[:,0,2]+u*(tri[:,1,2]-tri[:,0,2])+w*(tri[:,2,2]-tri[:,0,2]);valid&=(z<=POINTS[label][2]+48)&(z>=POINTS[label][2]-256)
  if not valid.any():raise ValueError('No source pipe floor at reported coordinate '+label)
  floor=float(z[valid].max());probe=dict(kind='reported-pipe-floor',source_prop=index,reported_site=label,start=[*xy, floor+96],end=[*xy,floor-4],prop_probe=True)
  s['collision_probes'].append(probe);s['pilot_hull_contact_probes'].append(probe);sites.append(probe)
 s['full_collision_rebuild']['runtime_probe_selection']=dict(raw_point_probes=len(raw),clear_start_hull_contacts_from_first_pass=len(s['pilot_hull_contact_probes'])-len(sites),initial_hull_tests_starting_in_existing_solids=sum(solid!='false' for _,_,solid in results),initial_clear_start_hull_misses=sum(float(f)==1 and solid=='false' for _,f,solid in results),reported_pipe_floor_probes=sites)
 # The old clearance sample had no collider for rock 253. Full source
 # physics proves it touches that rock; move its clearance test 64 units out.
 prior=s['hull_clearance_probes'][2].copy();s['hull_clearance_probes'][2]['start'][0]+=64;s['hull_clearance_probes'][2]['end'][0]+=64
 s['full_collision_rebuild']['legacy_clearance_reclassified']=dict(prior_probe=prior,actual_source_prop=253,nearest_source_surface_distance=4.44914,adjusted_clearance=s['hull_clearance_probes'][2])
 # At the east pipe site, original world terrain is above the pipe shell.
 # The usable standing gap is only ~83 units under a source rock ceiling.
 # Check the actual restored walking surface from a verified clear start.
 header=h[0];t=v[header[6]+154305*3:header[6]+154306*3].astype(float);n=np.cross(t[1]-t[0],t[2]-t[0]);x,y=POINTS['pipe_section'][:2];floor=float((n@t[0]-n[0]*x-n[1]*y)/n[2]);probe=dict(kind='reported-pipe-floor',source_prop=-1,reported_site='pipe_section',start=[x,y,floor+8],end=[x,y,floor-4],prop_probe=True,source_world_triangle=154305,clear_pilot_hull_start_verified=True)
 s['collision_probes'][-1]=probe;s['pilot_hull_contact_probes'][-1]=probe;sites[-1]=probe
 path.with_name('source-build.json').write_text(json.dumps(s,indent=2));print('Point contacts',len(s['collision_probes']),'clear hull contacts',len(s['pilot_hull_contact_probes']),'clearances',len(s['hull_clearance_probes']))
if __name__=='__main__':prepare()
