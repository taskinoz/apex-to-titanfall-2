"""Native limit, full submission, and physical-reference preservation checks."""
import collections,json,random,struct,unittest
from repair_world_batch_order import ROOT,SOURCE,TARGET,BASE,PACKAGE,OUT,reorder
from repair_preview_index_padding import read_lumps,validate_index_padding
from audit_world_draw_budget import WORLD_BATCH_CAPACITY,audit,enforce_camera_bypass_budget
from finalize_lighting_release import digest
from preview_visibility import validate_visibility

def native_bytes(rva,size):
    # Read installed machine instructions directly, without executable changes.
    with open('D:/Games/Titanfall2/bin/x64_retail/engine.dll','rb') as f:
        dos=f.read(64);pe=struct.unpack_from('<I',dos,60)[0];f.seek(pe)
        header=f.read(24);count=struct.unpack_from('<H',header,6)[0]
        optional=struct.unpack_from('<H',header,20)[0];f.seek(optional,1)
        sections=f.read(count*40)
        for at in range(0,len(sections),40):
            virtual_size,virtual,raw_size,raw=struct.unpack_from('<4I',sections,at+8)
            if virtual<=rva and rva+size<=virtual+raw_size:
                f.seek(raw+rva-virtual);return f.read(size)
    raise ValueError('Instruction RVA outside module sections')

def simulate_submission(meshes,visible=None):
    # Native b7160 consumes visible mesh bits in ASCENDING MESH ID order, not
    # visibility-tree reference order. Uniform dynamic-light mask is zero here.
    chosen=range(len(meshes)//28) if visible is None else sorted(visible)
    emitted=[];batches=0;previous=None;indices=0
    for i in chosen:
        r=meshes[i*28:i*28+28]
        key=(r[10],r[22:24])
        count=struct.unpack_from('<H',r,4)[0];needed=3*(count+(count&1))
        if indices+needed>0x300000:break
        if key!=previous:
            if batches==0x800:break
            batches+=1;previous=key
        indices+=needed;emitted.append(i)
    return emitted,batches,indices

class WorldBatchOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=read_lumps(SOURCE,(0xe,0x4f,0x50,0x51,0x52,0x64,0x77,0x78,0x79,0x7b))
        cls.b=read_lumps(TARGET,cls.a.keys())
        cls.report=json.loads((OUT/'batch-order.json').read_text())

    def test_installed_native_batch_limit_and_early_exit(self):
        opcode=native_bytes(0xb7304,13)
        self.assertEqual(opcode[:7],b'\x41\x81\xff'+struct.pack('<I',WORLD_BATCH_CAPACITY))
        self.assertEqual(opcode[7:9],b'\x0f\x84')
        self.assertEqual(0xb7304+13+struct.unpack_from('<i',opcode,9)[0],0xb74c9)
        self.assertEqual(native_bytes(0xb72af,5),b'\x3d'+struct.pack('<I',0x300000))

    def test_prior_draw_reproduces_cutoff_and_all_catwalk_omissions(self):
        emitted,runs,indices=simulate_submission(self.a[0x50])
        self.assertEqual(runs,2048);self.assertEqual(len(emitted),2343)
        self.assertEqual(indices,audit(SOURCE)['prefix_indices'] if len(emitted)==4586 else
                         sum(3*(r[1]+(r[1]&1)) for r in list(struct.iter_unpack('<I3H6b2h2BHI',self.a[0x50]))[:2343]))
        self.assertTrue(set(self.report['catwalk_meshes_before']).isdisjoint(emitted))
        with self.assertRaisesRegex(ValueError,'material-batch runs'):enforce_camera_bypass_budget(SOURCE)

    def test_new_draw_submits_every_mesh_and_visible_subset(self):
        emitted,runs,indices=simulate_submission(self.b[0x50])
        self.assertEqual(emitted,list(range(4586)));self.assertEqual(runs,454)
        self.assertEqual(indices,2652150)
        self.assertTrue(set(self.report['catwalk_meshes_after'])<=set(emitted))
        rng=random.Random(40)
        for _ in range(64):
            visible=sorted(rng.sample(range(4586),rng.randrange(1,4586)))
            drawn,batches,_=simulate_submission(self.b[0x50],visible)
            self.assertEqual(drawn,visible);self.assertLessEqual(batches,454)
        self.assertEqual(audit(TARGET)['static_batch_runs'],454)

    def test_exact_draw_records_bounds_and_physical_references(self):
        order=self.report['new_to_old_mesh'];inverse=self.report['old_to_new_mesh']
        self.assertEqual(sorted(order),list(range(4586)))
        for new,old in enumerate(order):
            self.assertEqual(inverse[old],new)
            self.assertEqual(self.a[0x50][old*28:old*28+28],self.b[0x50][new*28:new*28+28])
            self.assertEqual(self.a[0x51][old*32:old*32+32],self.b[0x51][new*32:new*32+32])
        for (old,),(new,) in zip(struct.iter_unpack('<H',self.a[0x78]),struct.iter_unpack('<H',self.b[0x78])):
            self.assertEqual(new,inverse[old])
        validate_visibility(self.b[0x77],self.b[0x78],self.b[0x79],self.b[0x51])
        validate_index_padding(self.b[0x50],self.b[0x4f],self.b[0x52])

    def test_all_other_bsp_payloads_and_confirmed_assets_exact(self):
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ah=a.read(2064);bh=b.read(2064)
            for lid in range(128):
                if lid in (0x50,0x51,0x78,0x23):continue
                ao,an,av,ap=struct.unpack_from('<4I',ah,16+lid*16);bo,bn,bv,bp=struct.unpack_from('<4I',bh,16+lid*16)
                self.assertEqual((an,av,ap),(bn,bv,bp),hex(lid));a.seek(ao);b.seek(bo)
                for at in range(0,an,8*1024*1024):
                    n=min(8*1024*1024,an-at);self.assertEqual(a.read(n),b.read(n),hex(lid))
        self.assertEqual(digest(SOURCE.with_suffix('.stbsp')),digest(TARGET.with_suffix('.stbsp')))
        for p in BASE.rglob('*'):
            if not p.is_file():continue
            rel=p.relative_to(BASE)
            if rel.as_posix() in ('mod.json','build-status.json','mod/maps/mp_phase_runner.bsp'):continue
            self.assertEqual(digest(p),digest(PACKAGE/rel),str(rel))

    def test_reject_unsupported_layouts(self):
        for lid,payload in ((0xe,bytes(64)),(0x7b,bytes(28)),(0x64,b'\x00\x00')):
            with self.assertRaises(ValueError):reorder({**self.a,lid:payload})

if __name__=='__main__':unittest.main()
