"""Repackage hash-locked, accepted GitHub downloads; never compile game assets in CI."""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
REPO = 'taskinoz/apex-to-titanfall-2'
WEBSITE = 'https://github.com/' + REPO
UI = 'ApexMaps.UI'


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def catalog():
    return json.loads((ROOT/'thunderstore/packages.json').read_text())


def select(packages, selector):
    if selector == 'current':
        chosen = list(packages)
    else:
        chosen = [p for p in packages if selector in (p['mod'], p['tag'])]
    if not chosen:
        raise ValueError('No hash-locked packages match selection; update thunderstore/packages.json')
    if any(p['mod'] != UI for p in chosen):
        chosen += [p for p in packages if p['mod'] == UI]
    return sorted({p['mod']: p for p in chosen}.values(), key=lambda p: (p['mod'] != UI, p['mod']))


def fetch(package, directory):
    target = directory/package['asset']
    directory.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        subprocess.run(['gh', 'release', 'download', package['tag'], '--repo', REPO,
                        '--pattern', package['asset'], '--dir', str(directory)], check=True)
    if target.stat().st_size != package['bytes'] or digest(target) != package['sha256']:
        raise ValueError('Source download size/hash mismatch: ' + target.name)
    return target


def entries(archive, mod):
    seen = set()
    result = []
    for item in archive.infolist():
        name = item.filename
        path = PurePosixPath(name)
        if ('\\' in name or path.is_absolute() or '..' in path.parts or
                not path.parts or path.parts[0] != mod or name.casefold() in seen or
                (item.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError('Unsafe or duplicate ZIP member: ' + name)
        seen.add(name.casefold())
        if item.is_dir():
            continue
        relative = PurePosixPath(*path.parts[1:])
        if relative.as_posix() not in ('mod.json', 'README.md', 'screenshot.png') and (
                len(relative.parts) < 2 or relative.parts[0] not in ('mod', 'paks')):
            raise ValueError('Unexpected development file: ' + name)
        result.append((item, relative.as_posix()))
    return result


def build(package, source, out, namespace='taskinoz'):
    if not re.fullmatch(r'[A-Za-z0-9_]+', namespace):
        raise ValueError('Invalid Thunderstore namespace')
    if source.stat().st_size != package['bytes'] or digest(source) != package['sha256']:
        raise ValueError('Source ZIP does not match locked release')
    mod, name, version = package['mod'], package['name'], package['version']
    if not re.fullmatch(r'[A-Za-z0-9_]+', name) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid package identity/version')
    folder = out/name
    folder.mkdir(parents=True, exist_ok=True)
    icon = ROOT/'thunderstore/icons'/f'{name}.png'
    raw = icon.read_bytes()
    if raw[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', raw[16:24]) != (256, 256):
        raise ValueError('Expected 256x256 PNG icon')
    dependencies = [] if mod == UI else [f'{namespace}-ApexMaps_UI-0.2.1']
    manifest = dict(name=name, version_number=version, website_url=WEBSITE,
                    description=package['description'], dependencies=dependencies)
    if len(manifest['description']) > 250:
        raise ValueError('Description exceeds Thunderstore limit')
    hashes = {}
    with zipfile.ZipFile(source) as old:
        members = entries(old, mod)
        info = json.loads(old.read(mod+'/mod.json').decode('utf-8-sig'))
        if (info['Name'], info['Version']) != (mod, version):
            raise ValueError('Runtime mod identity/version disagrees with catalog')
        if not any(r.startswith('paks/') and r.endswith('.rpak') for _, r in members):
            raise ValueError('Missing native asset pack')
        if mod != UI and not any(r.endswith('.bsp') for _, r in members):
            raise ValueError('Missing map payload')
        original = old.read(mod+'/README.md').decode('utf-8-sig')
        readme = (f'# {package["title"]}\n\n{package["description"]}\n\n'
                  'Install with a Northstar-compatible mod manager. Remove older manually installed copies '
                  'of this mod before enabling the managed copy. Every player needs the same versions.\n\n'
                  + ('The shared ApexMaps UI dependency supplies loading artwork and minimaps.\n\n' if dependencies else '')
                  + 'Preview conversion; original assets belong to their respective creators. '
                  '[Comparisons and known limitations](https://taskinoz.github.io/apex-to-titanfall-2/).\n\n'
                  + original)
        (folder/'README.md').write_text(readme, encoding='utf-8')
        shutil.copyfile(icon, folder/'icon.png')
        target = folder/f'{namespace}-{name}-{version}.zip'
        temporary = target.with_suffix('.packaging')
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as new:
            def write(name, data):
                zi = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o100644 << 16
                new.writestr(zi, data)
            write('manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
            write('README.md', readme.encode())
            write('icon.png', raw)
            for item, rel in sorted(members, key=lambda pair: pair[1]):
                if rel in ('README.md', 'screenshot.png'):
                    continue
                data = old.read(item)
                destination = f'mods/{namespace}.{mod}/{rel}'
                write(destination, data)
                hashes[destination] = hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(temporary) as check:
            for entry_name, expected in hashes.items():
                if hashlib.sha256(check.read(entry_name)).hexdigest() != expected:
                    raise ValueError('Repack changed runtime bytes')
        temporary.replace(target)
    config_path = write_config(package, folder, namespace)
    return dict(mod=mod, name=name, version=version, namespace=namespace,
                path=str(target.resolve()), config=str(config_path.resolve()),
                sha256=digest(target), source_sha256=package['sha256'], runtime_sha256=hashes)


def write_config(package, folder, namespace):
    name, version = package['name'], package['version']
    dependencies = [] if package['mod'] == UI else [f'{namespace}-ApexMaps_UI-0.2.1']
    quoted = json.dumps
    config = ('[config]\nschemaVersion = "0.0.1"\n[package]\n'
              + '\n'.join(f'{key} = {quoted(value)}' for key, value in {
                  'namespace': namespace, 'name': name, 'versionNumber': version,
                  'description': package['description'], 'websiteUrl': WEBSITE}.items())
              + '\ncontainsNsfwContent = false\n[package.dependencies]\n'
              + ''.join(f'{quoted(d.rsplit("-", 1)[0])} = {quoted(d.rsplit("-", 1)[1])}\n' for d in dependencies)
              + '[build]\nicon = "icon.png"\nreadme = "README.md"\noutdir = "."\n'
              + '[publish]\nrepository = "https://thunderstore.io"\ncommunities = ["northstar"]\n'
              + '[publish.categories]\nnorthstar = []\n')
    config_path = folder/'thunderstore.toml'
    config_path.write_text(config, encoding='utf-8')
    return config_path


def reuse(run, out, selector):
    if not re.fullmatch(r'\d+', run):
        raise ValueError('Expected numeric CI run ID')
    info = json.loads(subprocess.check_output(['gh', 'run', 'view', run, '--repo', REPO,
                     '--json', 'headBranch,event,name']))
    if (info['headBranch'] != 'main' or info['event'] != 'workflow_dispatch' or
            info['name'] != 'Publish Northstar maps to Thunderstore'):
        raise ValueError('Reuse requires this trusted main-branch publishing workflow')
    artifacts = json.loads(subprocess.check_output(['gh', 'api',
        f'repos/{REPO}/actions/runs/{run}/artifacts']))['artifacts']
    matching = [a for a in artifacts if a['name'] == 'thunderstore-packages-'+run and not a['expired']]
    if not matching:
        raise ValueError('Verified artifacts are missing or expired')
    # Reruns can produce several artifacts with the same name. Download one ID.
    artifact = max(matching, key=lambda a: a['id'])
    out.mkdir(parents=True, exist_ok=True)
    archive = out/'artifact-download.zip'
    with archive.open('wb') as f:
        subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'], stdout=f, check=True)
    allowed = {'receipts.json'} | {f'{p["name"]}/taskinoz-{p["name"]}-{p["version"]}.zip' for p in catalog()}
    old_downloads = {'downloads/'+p['asset'] for p in catalog()}
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            # First-run artifacts also included accepted source downloads. Do not
            # extract duplicate ZIPs; only restore verified Thunderstore outputs.
            if item.filename in old_downloads:
                continue
            if item.filename not in allowed:
                raise ValueError('Unexpected artifact member')
            z.extract(item, out)
    archive.unlink()
    locked = {p['mod']: p for p in select(catalog(), selector)}
    receipts = []
    for r in json.loads((out/'receipts.json').read_text()):
        if r['mod'] not in locked:
            continue
        p = locked[r['mod']]
        # Migrate only the exact receipt-name bug in the first trusted run;
        # ZIP names, source hashes, runtime hashes and output digests are intact.
        legacy_name = f'mods/taskinoz.{p["mod"]}/paks/rpak.json'
        if r['name'] == legacy_name and legacy_name in r['runtime_sha256']:
            r['name'] = p['name']
        if (r['name'], r['version'], r['namespace'], r['source_sha256']) != (
                p['name'], p['version'], 'taskinoz', p['sha256']):
            raise ValueError('Artifact receipt differs from reviewed catalog')
        folder = out/p['name']
        target = folder/f'taskinoz-{p["name"]}-{p["version"]}.zip'
        if digest(target) != r['sha256']:
            raise ValueError('Artifact ZIP hash mismatch')
        with zipfile.ZipFile(target) as z:
            for name in ('README.md', 'icon.png'):
                (folder/name).write_bytes(z.read(name))
        r.update(path=str(target.resolve()), config=str(write_config(p, folder, 'taskinoz').resolve()))
        receipts.append(r)
    if {r['mod'] for r in receipts} != set(locked):
        raise ValueError('Artifacts do not contain every selected package')
    return sorted(receipts, key=lambda r: (r['mod'] != UI, r['mod']))


def publish(receipts):
    if not os.environ.get('TCLI_AUTH_TOKEN'):
        raise ValueError('Missing repository Actions secret TS_KEY (taskinoz Thunderstore service account)')
    for r in receipts:
        if digest(r['path']) != r['sha256']:
            raise ValueError('Prepared ZIP changed')
        # Thunderstore/CDN negative caching can briefly hide a newly published version.
        url = f'https://thunderstore.io/api/experimental/package/{r["namespace"]}/{r["name"]}/{r["version"]}/?ci={time.time_ns()}'
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'ApexMapPublisher/1.0 (+https://github.com/taskinoz/apex-to-titanfall-2)', 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(request, timeout=60) as response:
                existing = json.load(response)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        else:
            # A published version is immutable: verify runtime payload, never overwrite it.
            remote = Path(r['path']).with_suffix('.remote.zip')
            request = urllib.request.Request(existing['download_url'], headers={'User-Agent': 'ApexMapPublisher/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response, remote.open('wb') as f:
                shutil.copyfileobj(response, f)
            with zipfile.ZipFile(remote) as z, zipfile.ZipFile(r['path']) as local:
                if set(z.namelist()) != set(local.namelist()) or any(z.read(n) != local.read(n) for n in local.namelist()):
                    raise ValueError('Published version differs; bump version instead of overwriting')
            remote.unlink()
            print('Already published and verified:', r['name'], r['version'], flush=True)
            continue
        from thunderstore_upload import submit
        submit(r['path'], r['namespace'], os.environ['TCLI_AUTH_TOKEN'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--select', default='current', help='current, runtime mod name, or locked release tag')
    p.add_argument('--namespace', default='taskinoz')
    p.add_argument('--output', type=Path, default=ROOT/'output/thunderstore')
    p.add_argument('--source-dir', type=Path, help='Use already-downloaded accepted ZIPs')
    p.add_argument('--reuse-run', help='Reuse verified artifacts from this main-branch publishing run')
    p.add_argument('--publish', action='store_true', help='Publish previously prepared receipts in output')
    args = p.parse_args()
    receipt_path = args.output/'receipts.json'
    if args.publish:
        publish(json.loads(receipt_path.read_text()))
        return
    if args.reuse_run:
        receipts = reuse(args.reuse_run, args.output, args.select)
        receipt_path.write_text(json.dumps(receipts, indent=2)+'\n')
        print('Verified and reused', len(receipts), 'packages', flush=True)
        return
    receipts = []
    for package in select(catalog(), args.select):
        source = args.source_dir/package['asset'] if args.source_dir else fetch(package, args.output/'downloads')
        receipts.append(build(package, source, args.output, args.namespace))
        print('Prepared:', package['name'], package['version'], flush=True)
    receipt_path.write_text(json.dumps(receipts, indent=2)+'\n')


if __name__ == '__main__':
    main()
