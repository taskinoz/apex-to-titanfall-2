"""Read-only ownership audit for the user's nine blocked tunnel positions."""
import collections,json
from pathlib import Path
from inspect_full_collision_contact import inspect

POINTS=[[-4704.6,16.5,-735.5],[-4412.6,613.2,-829.7],[-2476.4,2824.9,-644.2],
        [-2413.6,2933.2,-542.2],[-1819.8,3017.7,-446.4],[1940.5,3016.9,-440.0],
        [2627.1,2884.2,-517.4],[4636.4,734.9,-867.3],[4866.9,137.4,-746.4]]

def main():
    results=[]
    for point in POINTS:
        result=inspect(point);results.append(result)
        owners=collections.Counter((str(t['source_prop']),t['model']) for t in result['triangles'])
        print(json.dumps(dict(point=point,triangle_contacts=len(result['triangles']),
            owners=[dict(source_prop=o[0],model=o[1],contacts=n) for o,n in owners.items()],
            brushes=result['brushes'])),flush=True)
    Path('logs/reported-tunnel-barriers.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
