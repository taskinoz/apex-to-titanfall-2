"""Verify local PBR light routing, occlusion, preserved outdoor lighting and optimized assets."""
import unittest,json,struct,tempfile,subprocess,hashlib
from pathlib import Path
from apply_interior_lighting import ROOT,SOURCE,TARGET,INTERIOR,LOCAL_DTYPE,np,WorldLightv3
from repair_preview_index_padding import read_lumps
from optimize_preview_textures import TARGET as MATERIALS,SOURCE as OLD_MATERIALS,dds
from extract_native_material import NativePak

class InteriorTests(unittest.TestCase):
    def test_local_point_light_obeys_an_opaque_wall(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as folder:
            folder=Path(folder);p=np.array([[[-100,-100,0],[100,-100,0],[100,100,0]],
                [[-100,-100,0],[100,100,0],[-100,100,0]],
                [[-10000,-10000,40],[10000,-10000,40],[10000,10000,40]],
                [[-10000,-10000,40],[10000,10000,40],[-10000,10000,40]]],dtype='<f4')
            p.tofile(folder/'tri');dt=np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')])
            jobs=np.zeros(4,dt);jobs['p']=p;jobs['n'][...,2]=1;jobs['uv'][0]=[[0,0],[4,0],[4,4]];jobs['uv'][1]=[[0,0],[4,4],[0,4]];jobs.tofile(folder/'jobs')
            (folder/'light').write_bytes(struct.pack('<7fI',0,0,80,500,1,1,1,2))
            for wall in (False,True):
                np.array([1,1,int(wall),int(wall)],np.uint8).tofile(folder/'casters')
                subprocess.run([str(ROOT/'tools/bake_interior_lighting.exe'),str(folder/'tri'),str(folder/'jobs'),str(folder/'light'),str(folder/'result'),'4','4','1',str(folder/'casters')],capture_output=True,check=True)
                result=np.fromfile(folder/'result',LOCAL_DTYPE)
                self.assertTrue(np.all(result['vis'][:,1]==(0 if wall else 255)))
                if not wall:self.assertTrue(np.all(((result['ids']>>6)&63)==2))

    def test_geometry_collision_visibility_and_walkways_byte_preserved(self):
        changed={5,0x36,0x62,0x69,0x7a,0x7c,0x7e,0x7f}
        for i in range(128):
            if i not in changed and i!=0x23:self.assertEqual(read_lumps(SOURCE,[i])[i],read_lumps(TARGET,[i])[i],f'lump {i:#x}')

    def test_native_light_records_and_table_ranges(self):
        a=read_lumps(SOURCE,[0x36])[0x36];b=read_lumps(TARGET,[0x36,0x7a])
        self.assertTrue(b[0x36].startswith(a));self.assertEqual(len(b[0x36]),112*34)
        for offset in range(len(a),len(b[0x36]),112):
            light=WorldLightv3.from_bytes(b[0x36][offset:offset+112]);self.assertEqual(light.type.name,'POINT')
            self.assertGreater(light.radius,0);self.assertAlmostEqual(light.linear*light.radius,-1,places=5);self.assertEqual(light.quadratic,0)
        self.assertEqual(struct.unpack('<63h',b[0x7a]),(*range(32),*[-1]*31))

    def test_sun_sky_and_unaffected_luxels_preserved(self):
        a=read_lumps(SOURCE,[0x62,0x69]);b=read_lumps(TARGET,[0x62,0x69]);pixels=4096*4096
        sky_stride=pixels*8;rtl_stride=pixels*8+2048*2048*4;lit=0
        for page in range(2):
            self.assertEqual(a[0x62][page*sky_stride+pixels*4:(page+1)*sky_stride],b[0x62][page*sky_stride+pixels*4:(page+1)*sky_stride])
            ia=np.frombuffer(a[0x69],'<u4',pixels,page*rtl_stride);ib=np.frombuffer(b[0x69],'<u4',pixels,page*rtl_stride)
            np.testing.assert_array_equal(ia&0xff00003f,ib&0xff00003f)
            va=np.frombuffer(a[0x69],np.uint8,pixels*4,page*rtl_stride+pixels*4).reshape(-1,4)
            vb=np.frombuffer(b[0x69],np.uint8,pixels*4,page*rtl_stride+pixels*4).reshape(-1,4)
            np.testing.assert_array_equal(va[:,0],vb[:,0]);active=vb[:,1:].any(1);lit+=int(active.sum())
            ra=np.frombuffer(a[0x62],np.uint8,pixels*4,page*sky_stride).reshape(-1,4);rb=np.frombuffer(b[0x62],np.uint8,pixels*4,page*sky_stride).reshape(-1,4)
            np.testing.assert_array_equal(ra[~active],rb[~active]);self.assertFalse(active[(ia&63)==63].any())
            for slot in range(1,4):
                ids=(ib>>(6*slot))&63;valid=ids!=63
                self.assertTrue(np.all((ids[valid]>=2)&(ids[valid]<=31)));self.assertTrue(np.all(vb[:,slot][valid]==255))
        self.assertGreater(lit,80000)

    def test_shadow_batches_keep_every_caster(self):
        def decode(path):
            l=read_lumps(path,[5,0x7c,0x7e,0x7f]);p=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);ix=np.frombuffer(l[0x7e],'<u2');tri=[];at=0
            for base,n,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
                self.assertEqual((opaque,sort),(1,-1));tri.append(p[base+ix[at:at+n*3].astype(np.uint32)]);at+=n*3
            self.assertEqual(at,len(ix));return l,np.concatenate(tri)
        a,ta=decode(SOURCE);b,tb=decode(TARGET);np.testing.assert_array_equal(ta,tb)
        count=len(b[0x7f])//12;self.assertLess(count,len(a[0x7f])//24)
        env=list(struct.iter_unpack('<6i3f',b[5]));self.assertEqual(env[0][5],count);self.assertEqual(env[1][2],count);self.assertEqual(env[1][5],count)

    def test_texture_top_blocks_and_full_mip_chains(self):
        report=json.loads((MATERIALS/'optimization.json').read_text());self.assertEqual(report['unique_textures'],567)
        self.assertLess(report['optimized_dds_bytes'],report['original_dds_bytes']*.7)
        for row in report['textures']:
            source=(OLD_MATERIALS/'assets'/row['path']).with_suffix('.dds').read_bytes();target=(MATERIALS/'assets'/row['path']).with_suffix('.dds').read_bytes()
            a=dds(source);b=dds(target);self.assertEqual(b['mips'],max(b['width'],b['height']).bit_length())
            self.assertEqual(a['format'],b['format'])
            if row['top_blocks_preserved']:
                self.assertEqual(source[a['offset']:a['offset']+a['top_bytes']],target[b['offset']:b['offset']+b['top_bytes']],row['path'])
            else:self.assertLessEqual(max(b['width'],b['height']),1024)
        for old,canonical in report['aliases'].items():
            self.assertEqual(hashlib.sha256((OLD_MATERIALS/'assets'/old).with_suffix('.dds').read_bytes()).digest(),hashlib.sha256((OLD_MATERIALS/'assets'/canonical).with_suffix('.dds').read_bytes()).digest())

    def test_materials_and_native_rpak_mip_residency(self):
        aliases=json.loads((MATERIALS/'optimization.json').read_text())['aliases'];manifest=json.loads((MATERIALS/'build.json').read_text())
        for f in manifest['files']:
            if f['_type']!='matl':continue
            old=OLD_MATERIALS/'assets'/f['_path'];new=MATERIALS/'assets'/f['_path'];a=json.loads(old.with_suffix('.json').read_text());b=json.loads(new.with_suffix('.json').read_text())
            expected={k:aliases.get(v,v) for k,v in a['$textures'].items()};self.assertEqual(expected,b.pop('$textures'));a.pop('$textures');self.assertEqual(a,b)
            self.assertEqual(old.with_suffix('.uber').read_bytes(),new.with_suffix('.uber').read_bytes())
        pak=NativePak(MATERIALS/'build/phase_runner_world.rpak');textures=[a for a in pak.assets if a['type']=='txtr'];self.assertEqual(len(textures),567)
        for a in textures:
            at=pak.address(a['header']);header=pak.data[at:at+a['size']];w,h=struct.unpack_from('<2H',header,16)
            self.assertEqual(header[33],max(w,h).bit_length());self.assertEqual(header[29],0);self.assertEqual(header[34],0)
        self.assertTrue(json.loads((MATERIALS/'validation.json').read_text())['all_dependencies_present'])

if __name__=='__main__':unittest.main()
