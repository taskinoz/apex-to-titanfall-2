"""Use the owned local game harness to choose physically clear spawn locations."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller,write_json

def main():
    c=Controller();layout=json.loads((ROOT/'northstar/PhaseRunner.GameModes/gameplay-layout.json').read_text())
    points=[]
    for p in layout['spawns']:
        if p['classname'] not in ('info_spawnpoint_titan','info_spawnpoint_human_start'):continue
        x,y,z=p['origin']
        for dx,dy in ((0,0),(-128,0),(128,0),(0,-128),(0,128),(-256,0),(256,0),(0,-256),(0,256)):
            points.append([x+dx,y+dy,z])
    results=c.command('server','spawn_probe',points=points)['data']
    write_json(ROOT/'logs/gameplay-spawn-probes.json',results)
    print('Pilot-clear:',sum(p['pilot'] and p['floor'] for p in results),'Titan-clear:',sum(p['titan'] and p['floor'] for p in results))
    for p in results:
        if p['titan'] and p['floor']:print(p['origin'])
if __name__=='__main__':main()
