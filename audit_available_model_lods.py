"""Read-only audit of recovered compiled Apex LOD triangle counts."""
import collections,json,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    result=[]
    for folder in (ROOT/'tools/legion/exported_files/models').iterdir():
        path=folder/(folder.name+'.vg')
        if not path.is_file():continue
        data=path.read_bytes()
        if len(data)<160 or struct.unpack_from('<2I',data)!=(0x47567430,1):continue
        header=struct.unpack_from('<18Q',data,16)
        mesh_offset,mesh_count=header[2:4];lod_offset,lod_count=header[12:14]
        lods=[]
        for i in range(lod_count):
            first,count,distance=struct.unpack_from('<2hf',data,lod_offset+i*8)
            if first<0 or count<0 or first+count>mesh_count:raise ValueError('Invalid LOD range')
            triangles=sum(struct.unpack_from('<I',data,mesh_offset+j*72+36)[0]//3
                          for j in range(first,first+count))
            lods.append(dict(first=first,meshes=count,triangles=triangles,distance=distance))
        result.append(dict(model=folder.name,lods=lods))
    (ROOT/'logs/available-vg-lods.json').write_text(json.dumps(result,indent=2))
    print('Models:',len(result),'LOD counts:',dict(collections.Counter(len(x['lods']) for x in result)))
    print(json.dumps([x for x in result if 'tunnel' in x['model'] or 'rock_sharp_lava_moss_desertlands_06' in x['model']],indent=2))


if __name__=='__main__':main()
