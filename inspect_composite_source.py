"""Inventory the new arena source without changing an existing conversion."""
import contextlib, io, json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import bsp_tool
from bsp_tool.branches.respawn import apex_legends
path=ROOT/'inputs/composite/client/maps/mp_rr_arena_composite.bsp'
with contextlib.redirect_stdout(io.StringIO()):
    bsp=bsp_tool.load_bsp(str(path)); geo=bsp.external
raw=bytes(geo.GAME_LUMP.sprp)
head=geo.GAME_LUMP.headers['sprp']
report=dict(version=bsp.version,branch=str(bsp.branch),errors=str(geo.loading_errors),
    prop_header=str(head),prop_bytes=len(raw),prop_first_words=list(struct.unpack_from('<8I',raw)),
    models=[str(m) for m in geo.MODELS],meshes=len(geo.MESHES),
    triangles=sum(m.num_triangles for m in geo.MESHES),materials=list(geo.SURFACE_NAMES))
try:
    props=apex_legends.GameLump_SPRP.from_bytes(raw)
    report['prop_models']=list(props.model_names)
    report['props']=[dict(index=i,model=props.model_names[p.model_name],origin=list(p.origin),angles=[p.angles.y,p.angles.z,p.angles.x],scale=p.scale,skin=p.skin,solid=int(p.solid_mode.value),flags=int(p.flags)) for i,p in enumerate(props.props)]
except Exception as e: report['prop_error']=repr(e)
from bsp_tool.branches.shared import Entities
report['entities']={p.name:list(Entities.from_bytes(p.read_bytes().split(b'\n',1)[1].rstrip(b'\0'))) for p in path.parent.glob(path.stem+'*.ent')}
out=ROOT/'output/composite/source-inventory.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('entities','props','materials','prop_models','models')},indent=2))
print('Props:',len(report.get('props',[])))
print('Spawn entities:',[(e.get('classname'),e.get('origin')) for es in report['entities'].values() for e in es if 'spawn' in e.get('classname','')])
