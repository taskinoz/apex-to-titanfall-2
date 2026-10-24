"""Verify player downloads, publish a beta, and retire remotely archived ZIPs.

Only explicitly inventoried ZIPs in the two known distribution directories may
be removed. Never walk build trees, follow arbitrary links, or delete runtime mods.
GitHub's server-computed SHA-256 and size must match before any local retirement.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import time
import zipfile

from package_player_mods import RELEASES, SHARED_UI, runtime_files

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
STORE = Path('D:/Games/ApexToTitanfallWork/project-storage/output')
BACKUPS = Path('D:/Games/ApexToTitanfallWork/new-arena-ports/distribution-backups-archive')
REPORT = OUTPUT / 'release-cleanup-2026-10-25'
PLAN = REPORT / 'inventory.json'
REPO = 'taskinoz/apex-to-titanfall-2'
BETA = 'maps-beta-2026-10-25'
ARCHIVE = 'build-archive-2026-10-25'
SOURCE = '7ba631943456e227877d50fbb548f940c33fcfa4'
RELEASE_IDS = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.writing')
    with temp.open('w',encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def matching_sidecar(path,digest):
    try:
        return bool(path.is_file() and not path.is_symlink()
                    and path.read_text(encoding='utf-8-sig').split()[0]==digest)
    except (UnicodeError,IndexError,OSError):
        return False


def gh(*args):
    for attempt in range(4):
        p = subprocess.run(['gh', *args], cwd=ROOT, text=True, capture_output=True)
        if not p.returncode:break
        transient=re.search(r'(?i)(HTTP 50[234]|timeout|timed out|connection reset|TLS handshake|unexpected EOF)',p.stderr)
        readonly=args[0]=='api' and '--method' not in args and '-X' not in args
        if not readonly or not transient or attempt==3:break
        time.sleep(2**attempt)
    if p.returncode:
        raise RuntimeError(p.stderr.strip())
    return p.stdout


def api(endpoint):
    return json.loads(gh('api', f'repos/{REPO}/{endpoint}'))


def roots():
    if OUTPUT.resolve() != STORE.resolve():
        raise ValueError('Unexpected output target; review before changing storage')
    if (OUTPUT/'distribution-backups').resolve() != BACKUPS.resolve():
        raise ValueError('Unexpected distribution backup target')
    return {'output': STORE.resolve(), 'backups': BACKUPS.resolve()}


def source(row):
    name = row['name']
    if Path(name).name != name or not name.endswith('.zip'):
        raise ValueError('Only literal ZIP basenames are accepted')
    directory = roots()[row['scope']]
    path = directory/name
    if path.is_symlink() or path.resolve().parent != directory:
        raise ValueError('Archive path escaped its reviewed directory')
    return path


def current_names():
    versions = {name: r['version'] for name, r in RELEASES.items()}
    versions[SHARED_UI] = json.loads((ROOT/'northstar'/SHARED_UI/'mod.json').read_text(encoding='utf-8-sig'))['Version']
    return {f'{name}-{version}-Northstar.zip': (name, version) for name, version in versions.items()}


def verify_zip(path, current=None):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f'Duplicate ZIP member: {path.name}')
        for name in names:
            parts = PurePosixPath(name).parts
            if name.startswith(('/', '\\')) or '\\' in name or '..' in parts or ':' in name:
                raise ValueError(f'Unsafe ZIP member in {path.name}')
        # Never put harness session credentials, launch logs or tokens on GitHub,
        # including the authenticated historical draft archive.
        forbidden = {'session.json', '.env', 'token', 'credentials.json'}
        if any(PurePosixPath(n).name.lower() in forbidden or n.lower().endswith(('.log', '.dmp')) for n in names):
            raise ValueError(f'Private runtime state in {path.name}')
        token_pattern = re.compile(rb'(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|nfk_[A-Za-z0-9_-]{20,}|gm_[A-Za-z0-9_-]{30,})')
        for info in z.infolist():
            if not info.is_dir() and info.filename.lower().endswith(('.json', '.md', '.txt', '.nut', '.py', '.ps1', '.cfg')):
                if info.file_size > 16*1024*1024:
                    raise ValueError(f'Oversized text member needs review: {path.name}')
                if token_pattern.search(z.read(info)):
                    raise ValueError(f'Credential-like text in {path.name}')
        if current is None:
            return {'members':len(names), 'private_state_scan':'passed'}
        name, version = current
        manifest = json.loads(z.read(f'{name}/mod.json').decode('utf-8-sig'))
        if (manifest['Name'], manifest['Version']) != (name, version):
            raise ValueError(f'Wrong current identity: {path.name}')
        mod = ROOT/'northstar'/name
        files = ([mod/'mod.json', *sorted(p for p in (mod/'paks').rglob('*') if p.is_file())]
                 if name == SHARED_UI else runtime_files(mod))
        expected = {name+'/'+p.relative_to(mod).as_posix():p for p in files}
        extras = {name+'/README.md'} | (set() if name == SHARED_UI else {name+'/screenshot.png'})
        if set(names) != set(expected) | extras:
            raise ValueError(f'Unexpected player package membership: {path.name}')
        differences = []
        for arc, original in expected.items():
            h = hashlib.sha256()
            with z.open(arc) as f:
                for b in iter(lambda:f.read(8*1024*1024), b''):
                    h.update(b)
            working_sha = sha(original)
            if h.hexdigest() != working_sha:
                differences.append({'member':arc, 'archive_sha256':h.hexdigest(), 'working_sha256':working_sha})
        for arc in extras:
            z.read(arc)  # Includes CRC checking for every non-runtime member.
        return {'members':len(names), 'runtime_matches':not differences,
                'working_differences':differences, 'version':version, 'mod':name, 'private_state_scan':'passed'}


def inventory():
    if (REPORT/'retired.json').exists():
        raise ValueError('This migration has retired originals; preserve and reuse its existing receipts')
    current = current_names()
    accepted = json.loads((OUTPUT/'player-distributions.json').read_text())
    rows, excluded = [], []
    checkpoint = REPORT/'inventory-checkpoint.json'
    cached = json.loads(checkpoint.read_text()) if checkpoint.exists() else []
    for scope, directory in roots().items():
        for path in sorted(directory.glob('*.zip')):
            is_current = scope == 'output' and path.name in current
            print('Checking', path.name, flush=True)
            stat = path.stat()
            prior = next((r for r in cached if r['scope']==scope and r['name']==path.name
                          and r['bytes']==stat.st_size and r.get('mtime_ns')==stat.st_mtime_ns),None)
            if prior and not is_current:
                rows.append(prior)
                continue
            try:
                check = verify_zip(path, current[path.name] if is_current else None)
            except ValueError as error:
                if is_current:
                    raise
                excluded.append({'scope':scope,'name':path.name,'bytes':stat.st_size,'reason':str(error)})
                print('Retain locally, excluded from upload:',path.name,flush=True)
                continue
            digest = sha(path)
            if is_current:
                receipt = accepted[current[path.name][0]]
                if (digest,path.stat().st_size) != (receipt['sha256'],receipt['bytes']):
                    raise ValueError('Package differs from accepted distribution receipt: '+path.name)
                check['accepted_distribution_hash_matches'] = True
                if check['working_differences']:
                    print('Preserving accepted distribution; working tree differs in',len(check['working_differences']),'files:',path.name,flush=True)
            rows.append({'scope':scope, 'name':path.name, 'bytes':path.stat().st_size,
                         'mtime_ns':stat.st_mtime_ns,'sha256':digest, 'current':is_current, 'checks':check})
            save(checkpoint,rows)
    if {r['name'] for r in rows if r['current']} != set(current):
        raise ValueError('A current player package is absent')
    data = {'date':'2026-10-25', 'inventory_complete':True, 'repository':REPO, 'source_commit':SOURCE,
            'beta_tag':BETA, 'archive_tag':ARCHIVE, 'files':rows,'excluded_retained_locally':excluded}
    save(PLAN, data)
    print(json.dumps({'archives':len(rows), 'current':sum(r['current'] for r in rows),
                      'GiB':round(sum(r['bytes'] for r in rows)/2**30,2)}), flush=True)


def release(tag):
    if tag in RELEASE_IDS:
        info = api('releases/'+str(RELEASE_IDS[tag]))
    else:
        try:
            info = api('releases/tags/'+tag)
        except RuntimeError as error:
            if '404' not in str(error):
                raise
            # Draft releases without a published tag are found via the
            # authenticated release list, not the public tag endpoint.
            pages = json.loads(gh('api',f'repos/{REPO}/releases?per_page=100','--paginate','--slurp'))
            info = next((r for page in pages for r in page if r['tag_name']==tag),None)
            if info is None:
                raise error
        RELEASE_IDS[tag] = info['id']
    pages = json.loads(gh('api',f'repos/{REPO}/releases/{info["id"]}/assets?per_page=100','--paginate','--slurp'))
    info['assets'] = [asset for page in pages for asset in page]
    return info


def prepare():
    data = json.loads(PLAN.read_text())
    current = [r for r in data['files'] if r['current']]
    lines = ['# Apex maps for Northstar — October 2026 beta', '',
             'Seven converted maps, packaged separately. These are preview builds; known limitations remain.', '',
             '**Install `ApexMaps.UI` 0.2.1 once**, then extract the maps you want into `Titanfall2/R2Northstar/mods/`.',
             'Close the game first. Replace older mod folders rather than merging them; keep backups outside `mods/`.',
             'Enable the shared UI companion and each installed map. Server and clients need matching versions.', '',
             '| Map | Version | Console map |', '| --- | --- | --- |']
    for row in current:
        name = row['checks']['mod']
        if name in RELEASES:
            r = RELEASES[name]
            lines.append(f"| {r['title']} | {r['version']} | `{r['map']}` |")
    lines += ['', '## Preview limitations', '']
    for name, r in RELEASES.items():
        lines += [f"**{r['title']} {r['version']}:** {r['notes']}", '']
    lines += ['These are the existing accepted player distributions, preserved byte-for-byte and checked against their recorded SHA-256 receipts. Newer generated working files are not silently repackaged under an existing version. This cleanup does not constitute a fresh gameplay or multiplayer certification.', '',
              'Historical builds are retained separately as an authenticated draft archive, not offered as current downloads.', '',
              'SHA256SUMS.txt and release-manifest.json record the exact uploaded bytes.', '',
              'Original map assets belong to their respective creators. Unofficial community project.']
    (REPORT/'beta-notes.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (REPORT/'archive-notes.md').write_text('# Historical build archive\n\nStorage backup only. Superseded, experimental and report-bearing distributions. Not a supported player download. Kept as a draft so historical development bundles are not publicly promoted. See archive-manifest.json for restoration and SHA-256 checks.\n', encoding='utf-8')
    public = {'date':data['date'], 'source_commit':SOURCE, 'tag':BETA, 'packages':[
        {k:r[k] for k in ('name','bytes','sha256','checks')} | {'url':f'https://github.com/{REPO}/releases/download/{BETA}/{r["name"]}'} for r in current]}
    save(REPORT/'release-manifest.json', public)
    (REPORT/'SHA256SUMS.txt').write_text(''.join(f'{r["sha256"]}  {r["name"]}\n' for r in current), encoding='utf-8')
    save(REPORT/'archive-manifest.json', {'date':data['date'], 'tag':ARCHIVE,
        'files':[{k:r[k] for k in ('scope','name','bytes','sha256')} for r in data['files'] if not r['current']]})
    for tag, title, notes in [(BETA,'Apex maps for Northstar — October 2026 beta','beta-notes.md'),
                              (ARCHIVE,'Historical build archive — 25 October 2026','archive-notes.md')]:
        try:
            info = release(tag)
        except RuntimeError as e:
            if '404' not in str(e):
                raise
            gh('release','create',tag,'--repo',REPO,'--target',SOURCE,'--draft','--prerelease','--title',title,'--notes-file',str(REPORT/notes))
            info = release(tag)
        if not info['draft'] and tag == ARCHIVE:
            raise ValueError('Historical archive must remain a draft')
    print('Draft releases prepared', flush=True)


def upload_one(tag, row, existing):
    path = source(row)
    stat = path.stat()
    if stat.st_size != row['bytes'] or stat.st_mtime_ns != row['mtime_ns']:
        raise ValueError('Local package changed since inventory: '+row['name'])
    # The server hashes the actual uploaded stream and must match the full local
    # inventory hash below. Re-reading every large ZIP before uploading adds no
    # integrity proof. Retirement independently hashes the local file again.
    asset = existing.get(row['name'])
    if asset is None:
        for attempt in range(3):
            try:
                gh('release','upload',tag,str(path),'--repo',REPO)
                break
            except RuntimeError:
                # A lost response may still mean the server completed the upload.
                asset = next((a for a in release(tag)['assets'] if a['name']==row['name']),None)
                if asset and asset.get('state') == 'uploaded':
                    break
                if attempt == 2:
                    raise
                time.sleep(3)
        asset = next(a for a in release(tag)['assets'] if a['name']==row['name'])
    if (asset.get('state'),asset.get('size'),asset.get('digest')) != ('uploaded',row['bytes'],'sha256:'+row['sha256']):
        raise ValueError('Remote asset integrity mismatch: '+row['name'])
    print('Remote SHA-256 verified:',row['name'],flush=True)
    return {'name':row['name'], 'scope':row['scope'], 'tag':tag, 'asset_id':asset['id'],
            'bytes':row['bytes'], 'sha256':row['sha256']}


def upload(scope, workers):
    data = json.loads(PLAN.read_text())
    current = scope == 'current'
    if not current and not data.get('inventory_complete'):
        raise ValueError('Historical inventory is not complete')
    tag = BETA if current else ARCHIVE
    info = release(tag)
    existing = {a['name']:a for a in info['assets']}
    rows = [r for r in data['files'] if r['current'] == current]
    receipts = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(upload_one,tag,r,existing) for r in rows]
        for f in as_completed(futures):
            receipts.append(f.result())
            save(REPORT/(scope+'-uploaded.json'),receipts)
    for name in (['release-manifest.json','SHA256SUMS.txt'] if current else ['archive-manifest.json']):
        path = REPORT/name
        prior = next((a for a in release(tag)['assets'] if a['name']==name),None)
        if prior is None:
            gh('release','upload',tag,str(path),'--repo',REPO)
        elif prior.get('digest') != 'sha256:'+sha(path):
            raise ValueError('Remote manifest differs; never overwrite silently')
    info = release(tag)
    for row in rows:
        asset = next(a for a in info['assets'] if a['name']==row['name'])
        if asset.get('digest') != 'sha256:'+row['sha256']:
            raise ValueError('Final remote verification failed')
    if current and info['draft']:
        gh('release','edit',tag,'--repo',REPO,'--draft=false','--prerelease','--latest=false')
    print('Complete:',scope,len(rows),'packages',flush=True)


def retire(apply=False):
    data = json.loads(PLAN.read_text())
    if not data.get('inventory_complete'):
        raise ValueError('Inventory is not complete; preserve local files')
    info = release(ARCHIVE)
    if not info['draft']:
        raise ValueError('Historical backup is no longer a draft')
    assets = {a['name']:a for a in info['assets']}
    objects_path=REPORT/'archival-objects.json'
    objects=None
    if objects_path.exists():
        backup=json.loads(objects_path.read_text())
        if not backup.get('complete'):
            raise ValueError('Differential archive is incomplete; preserve local files')
        objects={(r['scope'],r['name']):r for r in backup['objects']}
        manifest=assets.get('archival-objects.json')
        if not manifest or manifest.get('digest')!='sha256:'+sha(objects_path):
            raise ValueError('Remote backup manifest differs')
    latest = current_names()
    beta = release(BETA)
    if beta['draft'] or not beta['prerelease']:
        raise ValueError('Current beta must be published before cleanup')
    for name in latest:
        row = next(r for r in data['files'] if r['current'] and r['name']==name)
        asset = next(a for a in beta['assets'] if a['name']==name)
        if asset.get('digest') != 'sha256:'+row['sha256'] or asset['size'] != row['bytes']:
            raise ValueError('Current beta is not intact')
    # Verify the entire remote dependency set before retiring the first ZIP.
    # In particular, a delta is useful only while its reference chain survives.
    if objects is not None:
        current_rows={r['name']:r for r in data['files'] if r['current']}
        for row in (r for r in data['files'] if not r['current']):
            proof=objects.get((row['scope'],row['name']))
            if not proof or not proof.get('remote_verified') or (proof['original_sha256'],proof['original_bytes'],proof['restored_sha256'])!=(row['sha256'],row['bytes'],row['sha256']):
                raise ValueError('Incomplete reconstruction proof')
            asset=assets.get(proof['asset_name'])
            if not asset or (asset.get('state'),asset['size'],asset.get('digest'))!=('uploaded',proof['asset_bytes'],'sha256:'+proof['asset_sha256']):
                raise ValueError('Incomplete remote dependency set')
            if proof.get('encoding')=='zstd-patch':
                if proof['base_tag']==BETA:
                    base=current_rows[proof['base_name']]
                    base_sha=base['sha256']
                elif proof['base_tag']==ARCHIVE:
                    base=objects[(proof['base_scope'],proof['base_name'])]
                    base_sha=base['original_sha256']
                else:raise ValueError('Unexpected reference release')
                if base_sha!=proof['base_sha256']:raise ValueError('Broken reconstruction reference')
    report = REPORT/'retired.json'
    journal = REPORT/'retirement-pending.json'
    retired = json.loads(report.read_text()) if report.exists() else []
    before = shutil.disk_usage(STORE).free
    for row in data['files']:
        if row['current']:
            continue
        path = source(row)
        if row['scope']=='output' and path.name in latest:
            raise ValueError('Refusing to retire a current package')
        proof=objects.get((row['scope'],row['name'])) if objects is not None else None
        if objects is not None:
            if not proof or not proof.get('remote_verified') or (proof['original_sha256'],proof['original_bytes'],proof['restored_sha256'])!=(row['sha256'],row['bytes'],row['sha256']):
                raise ValueError('No exact reconstruction proof: '+row['name'])
        asset_name=proof['asset_name'] if proof else row['name']
        asset_size=proof['asset_bytes'] if proof else row['bytes']
        asset_sha=proof['asset_sha256'] if proof else row['sha256']
        asset = assets.get(asset_name)
        if not asset or (asset.get('state'),asset.get('size'),asset.get('digest')) != ('uploaded',asset_size,'sha256:'+asset_sha):
            raise ValueError('No verified remote backup: '+row['name'])
        if not path.exists():
            if not any(r['name']==row['name'] and r['scope']==row['scope'] for r in retired):
                pending=json.loads(journal.read_text()) if journal.exists() else None
                if not pending or (pending['scope'],pending['name'],pending['sha256'])!=(row['scope'],row['name'],row['sha256']):
                    raise ValueError('Archive disappeared outside this cleanup')
                retired.append({**pending,'recovered_interrupted_receipt':True})
                save(report,retired)
            continue
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise ValueError('Archive changed; preserve it: '+row['name'])
        # source() checks resolved absolute parent against one of two explicit
        # distribution directories. This operation removes one verified file.
        if apply:
            sidecar=path.with_suffix('.zip.sha256')
            remove_sidecar=sidecar.resolve().parent==path.parent and matching_sidecar(sidecar,row['sha256'])
            record={**{k:row[k] for k in ('scope','name','bytes','sha256')},
                    'asset_id':asset['id'],'asset_name':asset_name,
                    'retired_at':datetime.now(timezone.utc).isoformat()}
            save(journal,record)
            path.unlink()
            retired.append(record)
            save(report,retired)
            if remove_sidecar:sidecar.unlink()
        print(('Retired:' if apply else 'Would retire:'),row['name'],flush=True)
    after=shutil.disk_usage(STORE).free
    result={'applied':apply,'retired_archives':len(retired),'logical_bytes':sum(r['bytes'] for r in retired),
            'volume_free_bytes_before':before,'volume_free_bytes_after':after,
            'free_bytes_change_this_run':after-before,'beta_url':beta['html_url'],
            'archive_tag':ARCHIVE,'current_packages_retained':sorted(latest)}
    save(REPORT/('cleanup-result.json' if apply else 'cleanup-dry-run.json'),result)
    print(json.dumps(result),flush=True)


def consolidate_private_history():
    """Move excluded log-bearing ZIPs into one local history folder, never upload."""
    data = json.loads(PLAN.read_text())
    if not data.get('inventory_complete'):
        raise ValueError('Inventory is incomplete')
    directory = REPORT/'retained-private'
    directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink() or not directory.resolve().is_relative_to(STORE.resolve()):
        raise ValueError('Private history escaped reviewed storage')
    receipt = REPORT/'private-retained.json'
    rows = json.loads(receipt.read_text()) if receipt.exists() else []
    for row in data.get('excluded_retained_locally',[]):
        path = source(row)
        target = directory/row['name']
        if target.resolve().parent != directory.resolve() or target.is_symlink():
            raise ValueError('Unexpected retained history target')
        if not path.exists():
            prior = next((r for r in rows if r['name']==row['name'] and r['scope']==row['scope']),None)
            if not prior or not target.is_file() or sha(target)!=prior['sha256']:
                raise ValueError('Missing excluded archive')
            continue
        if target.exists():
            raise ValueError('Private history collision; preserve both files')
        digest = sha(path)
        os.replace(path,target)  # Same volume, explicit checked file paths only.
        rows.append({**row,'sha256':digest,'retained_at':str(target.resolve().relative_to(STORE.resolve()))})
        save(receipt,rows)
        sidecar=path.with_suffix('.zip.sha256')
        if sidecar.resolve().parent==path.parent and matching_sidecar(sidecar,digest):
            destination=target.with_suffix('.zip.sha256')
            if destination.exists():raise ValueError('Retained sidecar exists')
            os.replace(sidecar,destination)
    print('Excluded archives retained locally:',len(rows),flush=True)


def organize_current():
    """Expose one clean beta directory without duplicating large ZIP storage."""
    data=json.loads(PLAN.read_text())
    roots()
    directory=STORE/'releases'/BETA
    directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink() or not directory.resolve().is_relative_to(STORE.resolve()):
        raise ValueError('Release directory escaped reviewed storage')
    beta=release(BETA)
    if beta['draft']:raise ValueError('Beta is not published')
    assets={a['name']:a for a in beta['assets']}
    names=current_names()
    for row in (r for r in data['files'] if r['current']):
        if row['name'] not in names:raise ValueError('Current version changed')
        original=source(row)
        if sha(original)!=row['sha256']:raise ValueError('Current ZIP changed')
        asset=assets[row['name']]
        if (asset['size'],asset.get('digest'))!=(row['bytes'],'sha256:'+row['sha256']):
            raise ValueError('Published ZIP differs')
        target=directory/row['name']
        if target.resolve().parent!=directory.resolve() or target.is_symlink():
            raise ValueError('Unexpected current download path')
        if not target.exists():os.link(original,target)
        if not os.path.samefile(original,target):raise ValueError('Release snapshot already contains a different file')
        target.with_suffix('.zip.sha256').write_text(row['sha256']+'  '+row['name']+'\n',encoding='utf-8')
    for name in ('release-manifest.json','SHA256SUMS.txt'):
        shutil.copyfile(REPORT/name,directory/name)
    (directory/'README.md').write_text(
        '# Apex maps for Northstar — October 2026 beta\n\n'
        'Install ApexMaps.UI 0.2.1 once, plus whichever map ZIPs you want. Close the game, replace older mod folders '
        'rather than merging, and extract into Titanfall2/R2Northstar/mods/. Keep backups outside mods/. '
        'Enable the shared companion and installed maps. Server and clients need matching versions.\n\n'
        'Preview limitations and per-map instructions are in each ZIP and the published release notes:\n'
        f'https://github.com/{REPO}/releases/tag/{BETA}\n\n'
        'These ZIPs are the exact published beta bytes. They are hardlinked to the compatible output paths, '
        'so this folder uses no second copy of their storage. Treat published ZIPs as immutable. '
        'Build a new version instead of editing these files in place.\n',encoding='utf-8')
    print('Clean current beta directory:',directory,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['inventory','prepare','upload','retire','private-history','organize-current'])
    p.add_argument('--scope',choices=['current','historical'],default='current')
    p.add_argument('--workers',type=int,choices=range(1,5),default=3)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    if a.action=='inventory':inventory()
    elif a.action=='prepare':prepare()
    elif a.action=='upload':upload(a.scope,a.workers)
    elif a.action=='private-history':consolidate_private_history()
    elif a.action=='organize-current':organize_current()
    else:retire(a.apply)
