from pathlib import Path
p=Path('spatial_preview_meshes.py');s=p.read_text().replace("struct.pack_into('<H',mesh,22,len(sorts)//12)","struct.pack_into('<H',mesh,22,si)")
s=s.replace('indices.extend(selected.astype(\'<u2\').tobytes());meshes.extend(mesh);sorts.extend(sort);bounds.extend','indices.extend(selected.astype(\'<u2\').tobytes());meshes.extend(mesh);bounds.extend')
s=s.replace('  world=bytearray(lump(0x0e));','  sorts=bytearray(oldsort)\n  world=bytearray(lump(0x0e));')
s=s.replace('exact_triangle_membership_verified=True,vertex_buffers_materials_and_physics_byte_unchanged=True,','exact_triangle_membership_verified=True,vertex_buffers_materials_and_physics_byte_unchanged=True,\n  material_sort_records_shared=True,material_sorts=len(sorts)//12,')
p.write_text(s)
p=Path('test_prop_physics.py');s=p.read_text().replace('old,new=map(read,paths);proof=',"old,new=map(read,paths);self.assertEqual(old[0x52],new[0x52]);self.assertLess(len(new[0x52])//12,8192);proof=");p.write_text(s)
