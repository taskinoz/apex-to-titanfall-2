from pathlib import Path
p=Path('package_northstar.py');s=p.read_text();a=s.index('    offset,length,_=lumps[0x57]');b=s.index('    return dict(version=',a)
s=s[:a]+'''    primitive_offset,primitive_length,_=lumps.get(0x59,(0,0,0))
    primitive_count=primitive_length//4
    if primitive_length%4 or lumps.get(0x5a,(0,0,0))[1]!=primitive_count*16:
        raise ValueError('Primitive bounds count differs')
    if lumps.get(0x58,(0,0,0))[1]!=sets*16:
        raise ValueError('Geoset bounds count differs')
    def validate_primitive(packed):
        if packed>>24!=0 or (packed>>8 & 65535)>=brush_count or (packed&255)>=palette_count:
            raise ValueError('Collision primitive refers outside brushes/contents')
    for (packed,) in struct.iter_unpack('<I',data[primitive_offset:primitive_offset+primitive_length]):
        validate_primitive(packed)
    offset,length,_=lumps[0x57]
    for geo,(group,count,packed) in enumerate(struct.iter_unpack('<HHI',data[offset:offset+length])):
        if count<1 or (packed&255)>=palette_count:
            raise ValueError(f'Invalid diagnostic geoset {geo}')
        if count==1:validate_primitive(packed)
        elif packed>>24!=0 or (packed>>8 & 65535)+count>primitive_count:
            raise ValueError(f'Compound geoset {geo} exceeds primitive array')
''' + s[b:]
s=s.replace("    if status.get('draw_regression_repair'):mod['Version']='0.1.19'","    if status.get('draw_regression_repair'):mod['Version']='0.1.19'\n    if status.get('prop_physics'):mod['Version']='0.1.20'")
a=s.index("    status['bsp_validation']=checks")
s=s[:a]+'''    if status.get('prop_physics'):
        (output/'README.md').write_text("""# Phase Runner Northstar preview 0.1.20

Restart Northstar and load `map mp_phase_runner_preview`.

Rendering uses smaller spatial mesh sections with the original triangles, materials and vertex attributes. This changes draw granularity and the native visibility tree; remaining pop-in needs client verification. Actual geometry bounds and the restored native rasterizer settings remain in use.

Rock and pipe collision is added at the original prop transforms. Available IRPS physics preserves its convex pieces. Dense rock BVHs use a bounded 26-direction hull approximation, which may fill small concavities. Large portal tubes retain partial thin surface collision; no whole-tube bounding box closes the passage. Smaller hollow elbow decorations remain deferred because the native brush index capacity is full. Existing world solids are retained, with only exact duplicate brushes removed. A compound collision grid shares primitive ranges across cells.

Textures and STBSP catalog are retained. Complete portal/prop collision, spatial texture streaming, original layered shaders, final lighting/shadows and gameplay support remain unfinished. Server probes verify selected surfaces; full movement and GPU rendering require a client check.

See `build-status.json` and `runtime-validation.json` for counts and evidence.
""",encoding='utf-8')
''' + s[a:];p.write_text(s)
