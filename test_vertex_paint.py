"""Binary colour decoding and conservative source matching regressions."""
import struct, unittest
from unittest.mock import patch
import numpy as np
from read_vg_static import decode
from recover_vertex_paint import keys,unique_source

def fixture(colors=True):
    stride=28 if colors else 24
    mesh=160;index=232;vertex=238;lod=vertex+stride*3;strip=lod+8
    d=bytearray(strip+35);struct.pack_into('<2I',d,0,0x47567430,1)
    h=[0]*18;h[2:8]=[mesh,1,index,3,vertex,stride*3];h[12:14]=[lod,1];h[16:18]=[strip,1]
    struct.pack_into('<18Q',d,16,*h)
    m=[0]*18;m[:5]=[0x11 if colors else 1,0,0,stride,3];m[8:10]=[0,3];m[12:14]=[0,1]
    struct.pack_into('<18I',d,mesh,*m);struct.pack_into('<3H',d,index,0,1,2)
    for i in range(3):
        at=vertex+i*stride;struct.pack_into('<3fI',d,at,float(i),0,0,0)
        shift=16
        if colors:struct.pack_into('<4B',d,at+shift,10+i,20+i,30+i,40+i);shift+=4
        struct.pack_into('<2f',d,at+shift,i/2,.25)
    struct.pack_into('<2hf',d,lod,0,1,0);struct.pack_into('<4i',d,strip,3,0,3,0);d[strip+18]=1
    return d

class PaintTests(unittest.TestCase):
    @patch('read_vg_static.compiled_materials',return_value=([0],[['paint_vc']]))
    def test_rgba_follows_reversed_triangle_winding_and_old_api_stays_eight_fields(self,_):
        ordinary=decode(b'',fixture())[0][0][0]
        painted=decode(b'',fixture(),with_colors=True)[0][0][0]
        self.assertEqual([list(v[:8]) for v in painted],[list(v) for v in ordinary])
        self.assertEqual([v[8:] for v in painted],[(12,22,32,42),(11,21,31,41),(10,20,30,40)])

    @patch('read_vg_static.compiled_materials',return_value=([0],[['paint_vc']]))
    def test_no_colour_flag_defaults_to_white_without_moving_uv(self,_):
        row=decode(b'',fixture(False),with_colors=True)[0][0][0][0]
        self.assertEqual(row[6:8],(1.,.75));self.assertEqual(row[8:],(255,255,255,255))

    @patch('read_vg_static.compiled_materials',return_value=([0],[['paint_vc']]))
    def test_truncated_colour_vertex_is_rejected(self,_):
        raw=fixture();struct.pack_into('<I',raw,160+12,24)
        with self.assertRaises(ValueError):decode(b'',raw,with_colors=True)

    def test_conflicting_colour_on_same_attributes_is_not_arbitrarily_chosen(self):
        data=np.array([[0,0,0,0,0,1,0,0,255,10,20,0],[0,0,0,0,0,1,0,0,10,255,20,255],[1,0,0,0,0,1,0,0,5,6,7,0]],float)
        k,d,bad=unique_source(data);self.assertEqual(bad,1);self.assertEqual(len(k),1);self.assertEqual(d[0,8:11].tolist(),[5,6,7])

    def test_alpha_is_not_rgb_paint_and_does_not_create_conflict(self):
        data=np.array([[0,0,0,0,0,1,0,0,255,212,117,0],[0,0,0,0,0,1,0,0,255,212,117,255]],float)
        k,d,bad=unique_source(data);self.assertEqual((len(k),bad),(1,0))

if __name__=='__main__':unittest.main()
