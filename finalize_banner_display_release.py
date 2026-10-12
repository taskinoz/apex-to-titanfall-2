"""Publish only the verified texture pass as clean Northstar player packages."""
import json,os,shutil
from package_player_mods import ROOT,RELEASES,digest,write_player_zip,record_existing_releases
from verify_banner_display_runtime import verify
from verify_banner_display_textures import verify as binaries

def atomic_json(path,value):
    temp=path.with_suffix(path.suffix+'.new');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');os.replace(temp,path)

def finalize():
    verify()
    for ident,package in [('drop-off','ArenaComposite'),('phase-runner','PhaseRunner')]:
        binaries(ident);mod=ROOT/'northstar'/package;release=RELEASES[package]
        manifest=json.loads((mod/'mod.json').read_text());manifest['Version']=release['version']
        manifest['Description']='Drop-Off with Northstar banners, source display colours, native PBR, ziplines and preserved collision.' if package=='ArenaComposite' else 'Phase Runner with source display colours, native PBR, team modes, grounded firs and tunnel catwalks.'
        atomic_json(mod/'mod.json',manifest)
        work=ROOT/'output/banner-display-repair'/ident
        validation=json.loads((work/'validation.json').read_text());validation['version']=release['version'];validation['native_validation']='docs/banner-display-textures-2026-10-12.md'
        atomic_json(mod/'banner-display-validation.json',validation)
        shutil.copy2(ROOT/'docs/banner-display-textures-2026-10-12.md',mod/'BANNER_DISPLAYS.md')
        if package=='ArenaComposite':
            dest=mod/'mod/resource/northstar-banner-license.txt';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'art/northstar/NORTHSTAR-LICENSE.txt',dest)
        title=release['title'];old=(mod/'README.md').read_text(encoding='utf-8')
        marker='## Previous release notes'
        if marker not in old:
            (mod/'README.md').write_text(f"# {title} {release['version']} for Northstar\n\n{release['notes']}\n\nThe texture pass is checked with matched native screenshots and same-process\nmap reloads. See BANNER_DISPLAYS.md for the source channels, exact scope and\nlimitations. Geometry submission budgets, collision, visibility, world lights\nand character probes remain unchanged.\n\n{marker}\n\n"+old,encoding='utf-8')
        status=mod/'build-status.json'
        if status.exists():
            info=json.loads(status.read_text());info.update(version=release['version'],banner_display_repair=validation);atomic_json(status,info)
        hashes={p.relative_to(mod).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(mod.rglob('*')) if p.is_file() and p.name!='checksums.json'}
        atomic_json(mod/'checksums.json',hashes)
        write_player_zip(mod,ROOT/'output'/f"{package}-{release['version']}-Northstar.zip")
    record_existing_releases()

if __name__=='__main__':finalize()
