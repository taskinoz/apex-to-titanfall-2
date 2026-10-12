"""Protect the 0.5 collision/lighting while repairing four reported defects."""
import json,struct,unittest
from pathlib import Path
import recover_composite_details as recovery
from repair_preview_index_padding import read_lumps
from repair_composite_source_layout import canon
np=recovery.np;ROOT=recovery.ROOT;OUT=recovery.OUT;MAP=recovery.MAP
OLD=ROOT/'output/repair-backups/20261007-before-local-repair/mp_arena_composite.bsp';WORK=OUT/'local-repair'
class LocalRepairTests(unittest.TestCase):
 def test_source_supports_and_containers_are_complete_and_unmoved(self):
  source={p['index']:p for p in json.loads((OUT/'source-inventory.json').read_text())['props']};rows={p['index']:p for p in json.loads((OUT/'scene.json').read_text())['placements']};plan=json.loads((WORK/'plan.json').read_text())
  self.assertEqual(plan['added_triangles'],910);self.assertEqual({p['index'] for p in plan['placements']},{2914,2916,5287,5288})
  for i in (2914,2916,5287,5288):
   for key in ('origin','angles','scale','skin','model'):self.assertEqual(rows[i][key],source[i][key])
   self.assertEqual(rows[i]['lod'],3);self.assertEqual(rows[i]['collision_triangles'],0)
  self.assertNotIn(5093,rows)
 def test_collision_entities_lights_and_probes_are_byte_identical(self):
  ids=(0,1,4,0x36,0x42,0x44,0x45,0x55,0x56,0x57,0x58,0x59,0x5a,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x65,0x67,0x68,0x7a)
  self.assertEqual(read_lumps(OLD,ids),read_lumps(MAP,ids))
 def test_old_geometry_attributes_and_only_orphan_indices_change(self):
  ids=(3,0x1e,0x49,0x4f,0x7c,0x7e,0x7f);a=read_lumps(OLD,ids);b=read_lumps(MAP,ids)
  for k in (3,0x1e,0x7c,0x7f):self.assertEqual(a[k],b[k][:len(a[k])],k)
  va=np.frombuffer(a[0x49],recovery.DT);vb=np.frombuffer(b[0x49],recovery.DT)[:len(va)].copy();scope=np.load(WORK/'wall-scope.npz');vi=scope['vertices'];scope.close();vb['light'][vi,:2]=va['light'][vi,:2];self.assertEqual(va.tobytes(),vb.tobytes())
  for k in (0x7e,):
   old=np.frombuffer(a[k],'<u2').reshape(-1,3);new=np.frombuffer(b[k][:len(a[k])],'<u2').reshape(-1,3);changed=np.any(old!=new,1);self.assertEqual(int(changed.sum()),24);self.assertTrue((new[changed,0]==new[changed,1]).all());self.assertTrue((new[changed,1]==new[changed,2]).all())
  r=json.loads((WORK/'orphan.json').read_text());self.assertEqual(r['index'],5093)
  # Native page splitting can reorder triangles, but every active old face
  # must survive, with only the exact 24 orphan lamp triangles withdrawn.
  def active_faces(path):
   l=read_lumps(path,(0x49,0x4f,0x50,0x52));ix=np.frombuffer(l[0x4f],'<u2');rows=[]
   for at in range(0,len(l[0x50]),28):
    first,n=struct.unpack_from('<IH',l[0x50],at);si=struct.unpack_from('<H',l[0x50],at+22)[0];base=struct.unpack_from('<I',l[0x52],si*12+8)[0];rows.append(base+ix[first:first+n*3].reshape(-1,3).astype('u4'))
   t=np.concatenate(rows);t=t[(t[:,0]!=t[:,1])&(t[:,1]!=t[:,2])&(t[:,0]!=t[:,2])];t.sort(1);return t
  old=active_faces(OLD);new=active_faces(MAP);new=new[new.max(1)<len(va)];oldkeys=old.view('V12').ravel();newkeys=new.view('V12').ravel();missing=~np.isin(oldkeys,newkeys);self.assertEqual(int(missing.sum()),24);self.assertEqual(len(new),len(old)-24)
  from read_vg_static import load
  from stage_prop_geometry import rotation
  scene=json.loads((OLD.parent/'scene.json').read_text());p=next(p for p in scene['placements'] if p['index']==5093);secs,_,_=load(p['folder'],p['lod']);matrix=np.array(rotation(p['angles']));t=np.concatenate([np.asarray(s,'<f4').reshape(-1,3,8)[:,:,:3]@matrix.T*p['scale']+p['origin'] for s in secs]).astype('<f4');positions=np.frombuffer(a[3],'<f4').reshape(-1,3);self.assertTrue(np.isin(canon(positions[va['pi'][old[missing]]]),canon(t)).all())
 def test_chart_padding_never_imports_another_triangle(self):
  scope=np.load(WORK/'gutter-scope.npz');used=scope['used'];valid=scope['valid'];nearest=scope['nearest'];scope.close();a=read_lumps(OLD,(0x62,0x69));b=read_lumps(MAP,(0x62,0x69));oldcount=json.loads((OLD.parent/'scene.json').read_text())['triangles'];oldused=np.arange(4*512*512).reshape(4,512,512)<oldcount
  for key,stride in ((0x62,2048**2*8),(0x69,2048**2*8+1024**2*4)):
   for page in range(4):
    mask=used[page]&oldused[page]
    for channel in range(2):
     offset=page*stride+channel*2048**2*4;aa=np.frombuffer(a[key],'u1',2048**2*4,offset).reshape(512,4,512,4,4).transpose(0,2,1,3,4)[mask];bb=np.frombuffer(b[key],'u1',2048**2*4,offset).reshape(512,4,512,4,4).transpose(0,2,1,3,4)[mask]
     self.assertTrue(np.array_equal(aa[:,valid],bb[:,valid]),(key,page,channel))
     self.assertTrue(np.array_equal(aa[:,nearest[0],nearest[1]],bb),(key,page,channel))
 def test_added_visuals_have_native_materials_and_budget_headroom(self):
  from audit_world_draw_budget import enforce_camera_bypass_budget
  a=enforce_camera_bypass_budget(MAP);self.assertLess(a['native_padded_indices'],3145728*.9);self.assertEqual(a['real_triangles'],942146)
  mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
  for name in ('mounted_server_01','container_medium_tanks_blue'):self.assertTrue(mapping[name]['recovered']);self.assertFalse(mapping[name]['transparent']);self.assertIn('0',mapping[name]['textures'])
 def test_high_resolution_wall_charts_use_only_unused_atlas_space(self):
  r=json.loads((WORK/'walls.json').read_text());self.assertEqual(r['charts'],1302);self.assertEqual(r['size'],32);self.assertGreater(r['receiver_samples_per_triangle'],300)
  small=json.loads((WORK/'walls-small.json').read_text());self.assertEqual(small['charts'],948);self.assertEqual(small['size'],16);self.assertGreater(small['receiver_samples_per_triangle'],100)
  scope=np.load(WORK/'wall-scope.npz');origins=scope['origins'].astype(int);vi=scope['vertices'];uv=scope['uv'];sizes=scope['sizes'];scope.close();s=np.load(WORK/'gutter-scope.npz');used=s['used'];s.close()
  l=read_lumps(MAP,(0x49,));v=np.frombuffer(l[0x49],recovery.DT);self.assertTrue(np.allclose(v['light'][vi,:2]*2048,uv))
  for (x,y),size in zip(origins,sizes):self.assertFalse(used[3,y//4:(y+size)//4,x//4:(x+size)//4].any())
  l=read_lumps(MAP,(0x4f,0x50,0x52));ix=np.frombuffer(l[0x4f],'<u2');wanted=np.zeros(len(v),bool);wanted[vi.ravel()]=True;count=0
  for at in range(0,len(l[0x50]),28):
   first,n=struct.unpack_from('<IH',l[0x50],at);si=struct.unpack_from('<H',l[0x50],at+22)[0];_,page,_,_,base=struct.unpack_from('<3hHI',l[0x52],si*12);mask=wanted[base+ix[first:first+n*3].reshape(-1,3).astype('u4')].all(1)
   if mask.any():self.assertEqual(page,3);count+=int(mask.sum())
  self.assertEqual(count,2250)
if __name__=='__main__':unittest.main()
