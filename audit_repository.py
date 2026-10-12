"""Check staged Git blobs for credentials, private runtime state and large assets."""
import json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PATTERNS={
    'GitHub credential':re.compile(rb'gh[pousr]_[A-Za-z0-9_]{20,}'),
    'fine-grained GitHub credential':re.compile(rb'github_pat_[A-Za-z0-9_]{30,}'),
    'Gravemind credential':re.compile(rb'gm_[A-Za-z0-9_-]{25,}'),
    'notifi credential':re.compile(rb'nfk_[A-Za-z0-9_-]{20,}'),
    'AWS access key':re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}'),
    'private key':re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'literal runtime credential':re.compile(rb'(?i)(?:token|password|secret)["\x27]?\s*[:=]\s*["\x27]([A-Za-z0-9_-]{24,})["\x27]'),
}
FORBIDDEN={'.exe','.dll','.pdb','.dmp','.bsp','.stbsp','.rpak','.starpak','.vpk','.mdl','.rmdl','.vg','.phy','.dds','.vtf','.vmt','.obj','.smd','.qc','.bin','.npz','.npy','.zip','.7z','.tga','.log'}

def audit():
    raw=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT)
    entries=[]
    for line in raw.split(b'\0'):
        if not line:continue
        mode,sha,stagepath=line.split(b' ',2);stage,path=stagepath.split(b'\t',1)
        if mode not in (b'100644',b'100755') or stage!=b'0':raise ValueError('Unexpected staged file mode')
        entries.append((sha.decode(),path.decode('utf-8')))
    if not entries:
        raise ValueError('No staged source files to audit')
    findings=[];total=0;images=0
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for sha,name in entries:
            process.stdin.write(sha.encode()+b'\n');process.stdin.flush()
            header=process.stdout.readline().split()
            if len(header)!=3 or header[1]!=b'blob':raise ValueError('Missing staged blob: '+name)
            size=int(header[2]);blob=process.stdout.read(size)
            if len(blob)!=size or process.stdout.read(1)!=b'\n':raise ValueError('Truncated staged blob')
            total+=size;path=Path(name);parts=path.parts
            if size>=100*1024*1024:findings.append({'file':name,'rule':'GitHub file size limit'})
            if path.suffix.lower() in FORBIDDEN or path.name=='session.json' or path.name.startswith('.env'):
                findings.append({'file':name,'rule':'Excluded runtime/asset file'})
            if parts[0] in ('inputs','output','logs','tools','exported_files') or any(p in ('output','logs','downloads','__pycache__') for p in parts):
                findings.append({'file':name,'rule':'Private/generated directory'})
            if path.suffix.lower() in ('.png','.jpg','.jpeg'):
                images+=1;continue
            for label,pattern in PATTERNS.items():
                for match in pattern.finditer(blob):
                    # Gravemind document IDs are lowercase 26-character ULIDs.
                    # Verified document references are not authentication tokens.
                    if label=='Gravemind credential' and re.fullmatch(rb'gm_[0-7][0-9a-hjkmnp-tv-z]{25}',match.group()):
                        continue
                    findings.append({'file':name,'line':blob[:match.start()].count(b'\n')+1,'rule':label})
    finally:
        process.stdin.close();process.stdout.close();process.wait()
    result={'files':len(entries),'bytes':total,'images':images,'findings':findings}
    print(json.dumps(result,indent=2))
    if findings:raise SystemExit(1)
    return result

if __name__=='__main__':audit()
