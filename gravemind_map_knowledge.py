"""Publish curated map findings through the configured Gravemind MCP API.

Credentials come only from the process environment and are never saved.
Discovery and publication are separate; saved server content is untrusted reference.
"""
import argparse, hashlib, json, os, tomllib, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/gravemind'

class Client:
    def __init__(self):
        config = tomllib.loads((Path.home()/'.codex/config.toml').read_text())['mcp_servers']['gravemind']
        token = os.environ.get(config['bearer_token_env_var'])
        if not token:
            raise RuntimeError('Configured Gravemind credential unavailable')
        self.url = config['url']
        self.headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json', 'Accept':'application/json, text/event-stream'}
        self.sequence = 0
        self.rpc('initialize', {'protocolVersion':'2024-11-05', 'capabilities':{}, 'clientInfo':{'name':'map-knowledge-import', 'version':'1.0'}})
        self.rpc('notifications/initialized', notification=True)

    def rpc(self, method, params=None, notification=False):
        self.sequence += 1
        payload = {'jsonrpc':'2.0', 'method':method}
        if not notification: payload['id'] = self.sequence
        if params is not None: payload['params'] = params
        request = urllib.request.Request(self.url, json.dumps(payload).encode(), self.headers)
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.headers.get('Mcp-Session-Id'):
                self.headers['Mcp-Session-Id'] = response.headers['Mcp-Session-Id']
            raw = response.read().decode()
        if not raw: return None
        if raw.lstrip().startswith(('event:', 'data:')):
            packets = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
            packet = next((p for p in reversed(packets) if p.get('id')==self.sequence), packets[-1] if packets else {})
        else: packet = json.loads(raw)
        if 'error' in packet: raise RuntimeError(str(packet['error']))
        result = packet.get('result', {})
        if result.get('isError'): raise RuntimeError(str(result))
        return result

    def tool(self, name, **arguments):
        return self.rpc('tools/call', {'name':name, 'arguments':arguments})

def discover():
    client = Client()
    work = {}
    for name, tool, args in [
        ('collections','gravemind_list',dict(limit=100)),
        ('context','gravemind_context',dict(task='Record verified Titanfall 2 and Apex Legends map conversion findings: rBSP 47 to 37, STBSP, collision, portals, engine limits, PBR, lightmaps, native menu stage, Phase Runner and Drop-Off Northstar ports.',limit=20,max_chars=30000)),
        ('titanfall','gravemind_search',dict(query='Titanfall maps',limit=50)),
        ('apex','gravemind_search',dict(query='Apex BSP map conversion',limit=50)),
    ]:
        work[name] = client.tool(tool, **args)
        print(name, json.dumps(work[name]), flush=True)
    (WORK/'discovery.json').write_text(json.dumps(work,indent=2),encoding='utf-8')

def unwrap(result):
    if isinstance(result.get('structuredContent'),dict): return result['structuredContent']
    texts=[p['text'] for p in result.get('content',[]) if p.get('type')=='text']
    if len(texts)==1:
        try: return json.loads(texts[0])
        except json.JSONDecodeError: pass
    return result

ARTICLES = [
    ('README.md','Titanfall 2 and Apex Legends maps: conversion knowledge','Overview of tested map conversion findings, evidence and version scope',['maps','conversion','index'],'verified'),
    ('binary-formats.md','Titanfall 2 and Apex map binary formats','Observed rBSP, game-lump, VG and serialized layouts; coordinate and relocation pitfalls',['rbsp','binary-formats','vg','entities'],'verified'),
    ('collision.md','Apex-to-Titanfall collision decoding and ownership','World BVH, IRPS, native brushes and triangle collision; ownership and tunnel repairs',['collision','bvh','irps','tunnels'],'verified'),
    ('visibility-and-limits.md','Titanfall map visibility, portals and measured limits','Native padded index and draw batch limits; conservative visibility and failed selective portals',['visibility','portals','engine-limits','optimization'],'verified'),
    ('materials-and-streaming.md','Titanfall native materials, PBR and STBSP','Shader dependencies, material slots, alpha, resident catalogue and incomplete spatial streaming',['materials','pbr','stbsp','rpak','streaming'],'verified'),
    ('lighting.md','Titanfall lightmaps, character probes and menu-stage isolation','Native lightmaps and hardware remaps; physical menu-stage isolation and scoped wall rebaking',['lighting','lightmaps','rtl','lightprobes','menu-stage'],'verified'),
    ('entities-and-gameplay.md','Map entities, safety volumes and Northstar gameplay adaptation','Conditional geometry, source ziplines, trigger decoding, team starts and native objectives',['entities','game-modes','spawns','boundaries','ziplines'],'verified'),
    ('port-case-studies.md','Phase Runner and Drop-Off: verified conversion case studies','Versioned current port budgets, recoverable props, remaining omissions and native evidence',['phase-runner','drop-off','composite','case-study'],'verified'),
    ('testing-and-packaging.md','Native Northstar map testing and clean releases','Isolated native harness, screenshots, collision and reload validation, clean packages and rollback',['testing','harness','northstar','packaging'],'verified'),
    ('converter-design.md','Requirements for a future Apex-to-Titanfall map converter','Proposed staged converter and provenance-preserving intermediate representation',['converter-design','intermediate-representation','toolchain'],'proposed'),
    ('r5-testing.md','R5Reloaded source-map testing and paired Northstar captures','Verified local R5R console protocol, native camera/screenshot harness and source-to-port comparison workflow',['r5reloaded','testing','harness','screenshots','comparison'],'verified'),
]

def publish(limit=None,only=None):
    client=Client()
    destination='games/respawn/maps'
    receipt_path=WORK/'publication.json'
    receipts=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    selected = [article for article in ARTICLES if only is None or article[0] == only]
    if not selected: raise ValueError('Unknown article: '+str(only))
    for filename,title,description,tags,status in selected[:limit]:
        body=(WORK/filename).read_text(encoding='utf-8')
        # Only links between our authored articles are rewritten. Never upload credentials or input archives.
        body=body.replace('(README.md)','(index.md)')
        path=destination+'/'+('index.md' if filename=='README.md' else filename)
        sha=hashlib.sha256(body.encode()).hexdigest()
        if path in receipts:
            doc=unwrap(client.tool('gravemind_read',id=path,include_links=True))
            serialized=json.dumps(doc,ensure_ascii=False)
            if body not in serialized and body not in str(doc):
                # JSON escaping requires checking original text fields separately.
                values=[v for v in doc.values() if isinstance(v,str)]
                nested=doc.get('document',{})
                if isinstance(nested,dict):values += [v for v in nested.values() if isinstance(v,str)]
                if not any(body in value for value in values):raise RuntimeError('Published content changed: '+path)
            print('Previously published and read back:',path,flush=True)
            continue
        created=unwrap(client.tool('gravemind_create',title=title,content=body,path=path,collection=destination,
            description=description,tags=['titanfall-2','apex-legends','map-conversion',*tags],
            project='apex-to-titanfall-2',status=status,
            message='User-authorized transfer of project-authored findings; checked against source ledgers and native release receipts on 2026-10-11.'))
        receipts[path]=dict(file=filename,sha256=sha,status=status,create=created,verified_readback=False)
        receipt_path.write_text(json.dumps(receipts,indent=2),encoding='utf-8')
        print('Created',path,json.dumps(created,ensure_ascii=False)[:2200],flush=True)
        read=unwrap(client.tool('gravemind_read',id=path,include_links=True))
        values=[v for v in read.values() if isinstance(v,str)]
        if isinstance(read.get('document'),dict):values += [v for v in read['document'].values() if isinstance(v,str)]
        if not any(body in value for value in values):
            (WORK/'readback-shape.json').write_text(json.dumps(read,indent=2),encoding='utf-8')
            raise RuntimeError('Readback content did not match: '+path)
        receipts[path].update(verified_readback=True,read=read)
        receipt_path.write_text(json.dumps(receipts,indent=2),encoding='utf-8')
        print('Content readback verified:',path,flush=True)
    print('Publication complete:',len(receipts),'documents',flush=True)

def verify_collection():
    client=Client();destination='games/respawn/maps';index=destination+'/index.md'
    receipts=json.loads((WORK/'publication.json').read_text())
    assert len(receipts)==len(ARTICLES) and all(r['verified_readback'] for r in receipts.values())
    report={'collection':destination,'documents':len(receipts),'relationships':[]}
    for path in receipts:
        if path==index:continue
        current=unwrap(client.tool('gravemind_read',id=index,include_links=True))
        links=current.get('links',[])
        if not any(l.get('target_path')==path and l.get('relation')=='related' for l in links):
            result=unwrap(client.tool('gravemind_link',id=index,action='add',target=path,relation='related',expected_revision=current['revision']))
            report['relationships'].append(result)
            print('Linked index to',path,flush=True)
    report['listing']=unwrap(client.tool('gravemind_list',collection=destination,limit=100,sort='path'))
    for term in ['STBSP','collision','lightmaps','Phase Runner','Drop-Off','R5Reloaded']:
        found=unwrap(client.tool('gravemind_search',query=term,collection=destination,limit=10))
        if not found.get('results'):raise RuntimeError('Search did not retrieve articles: '+term)
        report.setdefault('searches',{})[term]=found
        print('Search retrieved',term,len(found['results']),'documents',flush=True)
    report['index']=unwrap(client.tool('gravemind_read',id=index,include_links=True))
    (WORK/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('All',len(receipts),'articles, index relationships and topic searches verified',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['discover','publish','verify']);parser.add_argument('--limit',type=int);parser.add_argument('--only',help='Publish one local article without replacing other documents');args=parser.parse_args()
    WORK.mkdir(exist_ok=True)
    if args.action=='discover':discover()
    elif args.action=='publish':publish(args.limit,args.only)
    else:verify_collection()
