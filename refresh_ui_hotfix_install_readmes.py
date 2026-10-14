"""Clarify clean upgrades without recompressing already-verified game payloads."""
import hashlib
import json
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS
from package_player_mods import digest

WORK=Path('D:/Games/ApexToTitanfallWork/new-arena-ports/ui-atlas-final-zips')
TITLES={'PhaseRunner':'Phase Runner','ArenaComposite':'Drop-Off','ApexFiringRange':'Firing Range',
        'ArenaPartyCrasher':'Party Crasher','ArenaOverflow':'Overflow'}


def compressed_proof(z):
    result={}
    for info in z.infolist():
        z.fp.seek(info.header_offset)
        header=z.fp.read(30)
        if header[:4]!=b'PK\x03\x04':raise ValueError('Invalid local ZIP header')
        name,extra=struct.unpack_from('<2H',header,26)
        z.fp.seek(name+extra,1)
        remaining=info.compress_size;h=hashlib.sha256()
        while remaining:
            block=z.fp.read(min(remaining,8*1024*1024))
            if not block:raise ValueError('Truncated verified archive')
            h.update(block);remaining-=len(block)
        result[info.filename]=dict(crc=info.CRC,size=info.file_size,method=info.compress_type,compressed_sha256=h.hexdigest())
    if len(result)!=len(z.infolist()):raise ValueError('Duplicate archive members')
    return result


def refresh():
    ledger_path=ROOT/'output/player-distributions.json';ledger=json.loads(ledger_path.read_text())
    for package in MAPS:
        r=ledger[package];original=ROOT/r['path']
        if digest(original)!=r['sha256']:raise ValueError('Initial verified release changed')
        with zipfile.ZipFile(original) as z:
            before=compressed_proof(z);text=z.read(package+'/README.md').decode('utf-8')
        a=text.index('Close Titanfall 2.');b=text.index('Launch from the console:')
        text=text[:a]+('Close Titanfall 2. Move the old folder for this map to a backup outside\n'
            '`R2Northstar/mods/`; replace the folder rather than merging files. Then\n'
            'extract both `'+package+'` and `ApexMaps.UI` into `Titanfall2/R2Northstar/mods/`.\n'
            'Enable both mods and restart. Remove older duplicate map folders from mods/.\n'
            'Update every installed Apex conversion to its UI atlas hotfix version.\n'
            'The five downloads include the same UI companion; install it once.\n'
            'Every player needs matching map and UI versions.\n\n')+text[b:]
        text=text.replace('# '+package+' ', '# '+TITLES[package]+' ',1)
        text=text.replace('textures and lighting are unchanged.', 'world textures and lighting are unchanged.')
        work=WORK/package;work.mkdir(parents=True,exist_ok=True)
        (work/package).mkdir(exist_ok=True)
        (work/package/'README.md').write_bytes(text.encode('utf-8'))
        archive=work/original.name;shutil.copy2(original,archive)
        run=subprocess.run(['C:/Program Files/7-Zip/7z.exe','u',str(archive),package+'/README.md','-y'],
                           cwd=work,capture_output=True,text=True)
        (work/'update.log').write_text(run.stdout+run.stderr);run.check_returncode()
        with zipfile.ZipFile(archive) as z:
            after=compressed_proof(z)
            if before.keys()!=after.keys():raise ValueError('Archive membership changed')
            for name in before:
                if name!=package+'/README.md' and before[name]!=after[name]:
                    raise ValueError('Verified compressed runtime changed: '+name)
            if z.read(package+'/README.md').decode('utf-8')!=text:raise ValueError('Upgrade instructions differ')
        # Retain the first verified package before atomic replacement.
        backup=work/('before-instructions-'+original.name)
        if not backup.exists():shutil.copy2(original,backup)
        temp=original.with_suffix('.zip.docs-verified');shutil.copy2(archive,temp)
        if digest(temp)!=digest(archive):raise ValueError('Final release copy differs')
        temp.replace(original)
        r.update(bytes=original.stat().st_size,sha256=digest(original),verified_files=len(after))
        original.with_suffix('.zip.sha256').write_text(r['sha256']+'  '+original.name+'\n')
        ledger_path.write_text(json.dumps(ledger,indent=2)+'\n')
        print(package,'upgrade README corrected; every compressed runtime byte retained',flush=True)


if __name__=='__main__':refresh()
