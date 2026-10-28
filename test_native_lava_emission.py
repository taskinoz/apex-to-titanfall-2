"""Protect native shader contracts and source data during the lava repair."""
import struct
import unittest
from new_arena_ports import folder
from native_lava_emission import chunks,patch,patch_msw,instructions,disassembly


def buffers(msw):
    at=struct.unpack_from('<I',msw,29)[0];result={}
    for i in range(msw[at+7]):
        entry=at+16+i*24;size,relative=struct.unpack_from('<2I',msw,entry)
        if size<len(msw):result[i]=msw[entry+relative:entry+relative+size]
    return result


class NativeLavaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=folder('overflow')/'materials/assets/shaderset'
        cls.source=(root/'overflow_native_bm.msw').read_bytes()
        cls.hdr=buffers((root/'overflow_native_bc654af817a04c94.msw').read_bytes())[0]
        cls.changed,cls.proof=patch_msw(cls.source,cls.hdr)
        cls.old=buffers(cls.source);cls.new=buffers(cls.changed)

    def test_vertex_shader_and_debug_variants_are_identical(self):
        a=struct.unpack_from('<I',self.source,33)[0];b=struct.unpack_from('<I',self.changed,33)[0]
        self.assertEqual(self.source[a:],self.changed[b:])
        for index in (4,5,12,13):self.assertEqual(self.old[index],self.new[index])
        self.assertEqual(set(self.old),set(self.new))

    def test_original_lighting_fog_and_motion_instructions_survive(self):
        for index in (0,1,8,9):
            def code(dx):return instructions(next(p for t,p in chunks(dx) if t in (b'SHEX',b'SHDR')))[1]
            before,after=code(self.old[index]),iter(code(self.new[index]))
            for op in before:
                # DCL_TEMPS alone expands; all original executable tokens survive.
                if op[0]&0x7ff==104:
                    self.assertIn([op[0],op[1]+3],code(self.new[index]));continue
                self.assertTrue(any(candidate==op for candidate in after),'Native instruction removed or changed')

    def test_reflection_and_container_checksums_match_new_bindings(self):
        self.assertEqual(struct.unpack_from('<H',self.changed,21)[0],28)
        for index in (0,1,8,9):
            rdef=next(p for t,p in chunks(self.new[index]) if t==b'RDEF')
            count,at=struct.unpack_from('<2I',rdef,8)
            texture_slots={r[5] for r in struct.iter_unpack('<8I',rdef[at:at+count*32]) if r[1]==2}
            self.assertTrue({4,27}<=texture_slots)
        bad=bytearray(self.new[0]);bad[-1]^=1
        with self.assertRaisesRegex(ValueError,'checksum'):chunks(bad)

    def test_emission_is_added_after_compression_before_fog(self):
        for index in (0,1,8,9):
            text=disassembly(self.new[index]);capture=next(i for i,t in enumerate(text) if t.startswith('mov r') and t.endswith(', r0.zzzz'))
            diffuse=next(i for i,t in enumerate(text) if t.startswith('mul r0.xyz, r0.xyzx, r') and t.endswith('.xxxx'))
            emit=next(i for i,t in enumerate(text) if ' t27.' in t and t.startswith('sample'))
            # Native no-fog variants retain their direct output instead.
            fog=next((i for i,t in enumerate(text) if 'cb2[12].w' in t),text.index('ret'))
            self.assertLess(capture,diffuse);self.assertLess(diffuse,emit);self.assertLess(emit,fog)

    def test_patch_cannot_be_applied_twice(self):
        with self.assertRaises(ValueError):patch(self.new[0],self.hdr)


if __name__=='__main__':unittest.main()
