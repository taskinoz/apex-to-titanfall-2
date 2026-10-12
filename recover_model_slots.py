"""Read validated Season 3 RMDL mesh slots instead of trusting SMD labels."""
import re
import struct
from pathlib import Path
from stage_prop_geometry import material_basename


def mesh_slots(data):
    def ints(offset, count):
        if offset < 0 or offset + count * 4 > len(data):
            raise ValueError('Compiled model record exceeds file bounds')
        return struct.unpack_from('<' + 'i' * count, data, offset)
    if len(data) < 244 or data[:4] != b'IDST' or ints(4, 1)[0] != 54:
        raise ValueError('Expected an Apex Season 3 v54 model')
    textures, texture_offset, _, _, skinrefs, families, skin_offset, bodies, body_offset = ints(208, 9)
    if not 0 < textures <= 4096 or not 0 < skinrefs <= 4096 or not 0 < families <= 256:
        raise ValueError('Invalid material or skin table dimensions')
    if skin_offset < 0 or skin_offset + skinrefs * families * 2 > len(data):
        raise ValueError('Compiled skin table exceeds file bounds')
    skins = list(struct.iter_unpack('<' + 'H' * skinrefs,
        data[skin_offset:skin_offset + skinrefs * families * 2]))
    if any(v >= textures for row in skins for v in row):
        raise ValueError('Skin table refers outside material table')
    if bodies != 1:
        raise ValueError('Multiple compiled bodygroups require an explicit section mapping')
    _, models, _, relative_model = ints(body_offset, 4)
    if models != 1:
        raise ValueError('Multiple compiled models require an explicit section mapping')
    model = body_offset + relative_model
    count, relative_mesh = ints(model + 76, 2)
    if not 0 < count <= 4096:
        raise ValueError('Invalid compiled mesh count')
    slots = []
    for i in range(count):
        record = model + relative_mesh + i * 92
        if record + 92 > len(data):
            raise ValueError('Truncated Season 3 mesh table')
        material, backref = ints(record, 2)
        if record + backref != model or not 0 <= material < skinrefs:
            raise ValueError('Unsupported mesh layout or invalid material slot')
        slots.append(material)
    return slots, skins


def load_bound_sections(qc_path, rmdl_path):
    qc = Path(qc_path)
    text = qc.read_text(errors='replace')
    rows = re.findall(r'"[^"\n]*"\s*\{\s*((?:"[^"\n]+"\s*)+)\}', text)
    materials = [[material_basename(m) for m in re.findall(r'"([^"]+)"', row)] for row in rows]
    slots, skins = mesh_slots(Path(rmdl_path).read_bytes())
    if len(materials) != len(skins) or any(len(a) != len(b) for a, b in zip(materials, skins)):
        raise ValueError('QC and compiled skin table dimensions disagree')
    known = {}
    for row, indices in zip(materials, skins):
        for name, index in zip(row, indices):
            if index in known and known[index] != name:
                raise ValueError('QC material family disagrees with compiled skin references')
            known[index] = name
    references = re.findall(r'\bstudio\s+"([^"]+\.smd)"', text)
    if len(references) != 1:
        raise ValueError('Expected one highest-detail SMD bodygroup')
    reference = qc.parent / references[0]
    if not reference.is_file():
        reference = qc.parent / re.sub(r'_body_\d+(?=_LOD\d+\.smd$)', '', references[0])
    lines = reference.read_text().splitlines()
    sections = []
    for start in (i + 1 for i, line in enumerate(lines) if line == 'triangles'):
        try:
            end = lines.index('end', start)
        except ValueError:
            raise ValueError('Truncated SMD section') from None
        if (end - start) % 4:
            raise ValueError('Incomplete SMD triangle records')
        faces = []
        for offset in range(start, end, 4):
            corners = [tuple(map(float, line.split()[1:9])) for line in lines[offset+1:offset+4]]
            if any(len(c) != 8 for c in corners):
                raise ValueError('Incomplete SMD vertex')
            faces.append(corners)
        sections.append(faces)
    if len(sections) != len(slots):
        raise ValueError(f'SMD/compiled mesh count mismatch: {len(sections)} versus {len(slots)}')
    # Each QC family is already ordered by skin reference, including repeats.
    return sections, slots, materials
