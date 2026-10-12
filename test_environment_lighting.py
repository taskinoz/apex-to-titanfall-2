"""Regression checks for the actual ray blocker bug and native menu routing."""
import unittest,tempfile,subprocess,struct
from pathlib import Path
from repair_environment_lighting import ROOT,SOURCE,TARGET,OUT,BAKE,NATIVE,np,entities,WorldLightv3
from repair_preview_index_padding import read_lumps

class EnvironmentLightingTests(unittest.TestCase):
    def test_decorative_ceiling_does_not_block_real_floor(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as folder:
            folder=Path(folder)
            p=np.array([[[-100000,-100000,0],[100000,-100000,0],[100000,100000,0]],
                [[-100000,-100000,0],[100000,100000,0],[-100000,100000,0]],
                [[-100000,-100000,20],[100000,-100000,20],[100000,100000,20]],
                [[-100000,-100000,20],[100000,100000,20],[-100000,100000,20]]],dtype='<f4')
            p.tofile(folder/'tri')
            dt=np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')])
            jobs=np.zeros(4,dt);jobs['p']=p;jobs['n'][...,2]=1
            jobs['uv'][0]=[[0,0],[4,0],[4,4]];jobs['uv'][1]=[[0,0],[4,4],[0,4]]
            jobs.tofile(folder/'jobs')
            for exclude in (False,True):
                np.array([1,1,int(not exclude),int(not exclude)],np.uint8).tofile(folder/'casters')
                subprocess.run([str(ROOT/'tools/bake_phase_environment.exe'),str(folder/'tri'),str(folder/'jobs'),str(folder/'out'),'4','4','1',str(folder/'casters')],check=True,capture_output=True)
                light=np.fromfile(folder/'out','<f4').reshape(16,5)
                self.assertTrue(np.all(light[:,0]==int(exclude)))
                self.assertTrue(np.all(light[:,1]==int(exclude)))

    def test_geometry_materials_visibility_and_collision_unchanged(self):
        allowed={0,5,0x36,0x62,0x63,0x69,0x7c,0x7e,0x7f}
        for i in range(128):
            if i in allowed or i==0x23:continue
            a=read_lumps(SOURCE,[i])[i];b=read_lumps(TARGET,[i])[i]
            self.assertEqual(a,b,f'Unexpected change to BSP lump {i:#x}')

    def test_environment_suns_match_native_indices_and_source_direction(self):
        l=read_lumps(TARGET,[5,0x36,0x63,0x64,0x7a,0x7f])
        self.assertEqual(len(l[0x36]),448);self.assertEqual(len(l[5]),72)
        light=[WorldLightv3.from_bytes(l[0x36][i:i+112]) for i in range(0,448,112)]
        self.assertEqual([x.type.name for x in light],['SKY_AMBIENT','SKY_AMBIENT','SKY_LIGHT','SKY_LIGHT'])
        old=read_lumps(SOURCE,[0x36])[0x36]
        self.assertEqual(list(light[2].normal),list(WorldLightv3.from_bytes(old[112:]).normal))
        self.assertEqual(list(light[2].intensity),list(WorldLightv3.from_bytes(old[112:]).intensity))
        count=len(l[0x7f])//12
        self.assertGreater(count,0)
        for i,s in enumerate(struct.iter_unpack('<6i3f',l[5])):
            self.assertEqual(s[:6],(i,0,0 if i==0 else count,i+1,0,count));np.testing.assert_allclose(s[6:],list(light[i+2].normal))
        self.assertEqual(l[0x63],read_lumps(NATIVE,[0x63])[0x63])
        self.assertEqual(l[0x64],b'')
        self.assertEqual(struct.unpack('<63h',l[0x7a]),(0,*[-1]*62))

    def test_native_shadow_stream_reconstructs_all_actual_casters(self):
        tri=np.fromfile(OUT/'triangles.bin','<f4').reshape(-1,3,3)
        caster=np.fromfile(OUT/'environment-caster-mask.bin',np.uint8).astype(bool)
        expected=tri[caster]
        l=read_lumps(TARGET,[0x7c,0x7e,0x7f])
        verts=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);indices=np.frombuffer(l[0x7e],'<u2')
        offset=0;face=0
        for start,count,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
            self.assertEqual((opaque,sort),(1,-1));self.assertLessEqual(count,8192)
            local=indices[offset:offset+count*3].astype(np.uint32)
            self.assertLess(int(local.max()),65536);self.assertLess(start+int(local.max()),len(verts))
            np.testing.assert_array_equal(verts[start+local].reshape(-1,3,3),expected[face:face+count])
            offset+=count*3;face+=count
        self.assertEqual(face,869050);self.assertEqual(offset,len(indices))

    def test_menu_stage_and_volume_are_outside_gameplay(self):
        e=entities(TARGET)
        env=[x for x in e if x.get('classname')=='light_environment']
        self.assertEqual([x['lightEnvironmentIndex'] for x in env],['*0','*1'])
        scene=[x for x in e if x.get('script_name')=='menu_scene_ref']
        camera=[x for x in e if x.get('script_name')=='menu_camera_target']
        self.assertEqual(len(scene),1);self.assertEqual(len(camera),1)
        self.assertEqual(scene[0]['origin'],'-11776 11856 12736')
        vol=next(x for x in e if x.get('classname')=='light_environment_volume')
        self.assertEqual(vol['lightEnvironmentIndex'],'*1');self.assertNotIn('model',vol)
        center=np.array(list(map(float,vol['origin'].split())))
        points=np.array([[-761,-4444,-991],[-4705,16,-736],[-2414,2933,-542],[1940,3017,-440],[4867,137,-746],[1839,-782,-1201]])
        self.assertTrue(np.all(np.any(np.abs(points-center)>3072,axis=1)))
        self.assertGreater(float(np.linalg.norm(center-points[0])),18000)

    def test_sky_only_exclusion_and_brightness_recovery(self):
        import json
        mask=np.fromfile(OUT/'environment-caster-mask.bin',np.uint8)
        proof=json.loads((OUT/'environment-casters.json').read_text())
        self.assertEqual(int((mask==0).sum()),3968);self.assertEqual(int(mask.sum()),869050)
        self.assertEqual(proof['excluded_materials'],['world/phase_runner_preview/phase_runner_sky'])
        values=np.memmap(BAKE,'<f4','r',shape=(2,4096,4096,5))
        old=np.memmap(OUT/'lighting.bin','<f4','r',shape=values.shape)
        valid=np.memmap(str(BAKE)+'.mask',np.uint8,'r',shape=(2,4096,4096))
        for page in range(2):
            actual=valid[page].astype(bool)&(values[page,...,1]>=0)
            self.assertTrue(np.all(values[page,...,0][actual]>=old[page,...,0][actual]))
            self.assertTrue(np.all(values[page,...,1][actual]+1e-6>=old[page,...,1][actual]))
        # Exclude the dome's own huge lightmap charts from the recovery count.
        self.assertGreater(int(((values[...,0]>old[...,0])&(values[...,1]>=0)&valid.astype(bool)).sum()),500000)

    def test_photo_sky_uses_no_dynamic_sun_table_entries(self):
        values=np.memmap(BAKE,'<f4','r',shape=(2,4096,4096,5))
        l=read_lumps(TARGET,[0x53,0x62,0x69])
        self.assertEqual(l[0x53],read_lumps(SOURCE,[0x53])[0x53])
        rtl_stride=4096*4096*8+2048*2048*4;sky_stride=4096*4096*8
        photo_total=0
        for page in range(2):
            photo=values[page,...,1]<0
            photo_total+=int(photo.sum())
            ids=np.frombuffer(l[0x69],'<u4',4096*4096,page*rtl_stride).reshape(4096,4096)
            self.assertTrue(np.all(ids[photo]==0x00FFFFFF))
            rgbm=np.frombuffer(l[0x62],np.uint8,4096*4096*4,page*sky_stride).reshape(4096,4096,4)[photo]
            decoded=rgbm[:,:3]/255*(rgbm[:,3,None]/255*3.984375+.015625)
            np.testing.assert_allclose(decoded,.8,atol=.005)
        self.assertGreater(photo_total,0)

if __name__=='__main__':unittest.main()
