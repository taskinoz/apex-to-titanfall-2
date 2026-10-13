"""Keep source palette/layer bytes while disabling an unverified RGB mapping."""
import json,sys
from new_arena_ports import folder
from recover_arena_atmosphere import NativeMaterials


def repair(ident):
    out=folder(ident);m=out/'materials';p=out/'atmosphere-materials.json';receipt=json.loads(p.read_text())
    mapping=json.loads((m/'mapping.json').read_text());manifest=json.loads((m/'build.json').read_text())
    builder=NativeMaterials(m,ident.replace('-','_'),manifest);changed=[]
    for row in receipt['materials']:
        r=mapping['materials'][row['material']];path='material/'+r['name']+'_wld.rpak';cpath='material/'+r['name']+'_colpass_wld.rpak'
        s=json.loads((m/'assets'/path).with_suffix('.json').read_text())
        if not int(s['glueFlags2'],16)&2:continue
        if 'vertex paint' in row['kind']:
            primary,u=builder.material(0x92424EA716974A64);child,cu=builder.material(0x1F8E00B988C71BBB)
            kind='Source albedo tint/PBR; vertex palette interpretation disabled'
            emit=None
        elif 'HDR emission' in row['kind']:
            primary,u=builder.material(0xb3f8d91ef031a62);child,cu=builder.material(int(primary['$colpassMaterial'],16))
            kind=row['kind'];emit=row['source_emissive_tint']
        else:raise ValueError('Unexpected vertex-colour material: '+row['material'])
        builder.write(cpath,r['name']+'_colpass',child,cu,r['textures'],row['source_albedo_tint'],emit)
        builder.write(path,r['name'],primary,u,r['textures'],row['source_albedo_tint'],emit,colpass=cpath)
        row['kind']=kind;row['vertex_palette_disabled_after_native_comparison']=True;r['native_source_channels']=kind;changed.append(row['material'])
    if not changed:raise ValueError('No unverified vertex-colour bindings')
    builder.finish(manifest);(m/'mapping.json').write_text(json.dumps(mapping,indent=2))
    receipt['shaders']+=builder.proof;receipt['limitations'].append('Vertex-colour/palette conversion disabled after native/R5R mismatch; source bytes retained')
    receipt['rejected_vertex_colour_materials']=changed;p.write_text(json.dumps(receipt,indent=2))
    print(ident,'disabled unverified vertex palette on',len(changed),'materials',flush=True)


if __name__=='__main__':repair(sys.argv[1])
