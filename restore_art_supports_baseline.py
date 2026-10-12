"""Restore the complete verified 0.1.42 snapshot after a client-loading regression."""
import json,os,shutil
from pathlib import Path
from finalize_lighting_release import digest
ROOT=Path(__file__).resolve().parent
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.42-before-art-supports'
BASE=ROOT/'northstar/PhaseRunner.Preview'
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')

def main():
    if json.loads((BACKUP/'mod.json').read_text())['Version']!='0.1.42':raise ValueError('Unexpected snapshot')
    expected=json.loads((BACKUP/'checksums.json').read_text())
    for rel,sha in expected.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Snapshot corrupt '+rel)
    release=json.loads((ROOT/'logs/art-supports-0.1.43-release.json').read_text())
    if not release['archive_hashes_verified'] or not Path(release['archive']).exists():raise ValueError('Failed candidate archive unavailable')
    files={p.relative_to(BACKUP).as_posix():digest(p) for p in BACKUP.rglob('*') if p.is_file()}
    removed={}
    for destination in (BASE,INSTALLED):
        if json.loads((destination/'mod.json').read_text())['Version']!='0.1.43':raise ValueError('Unexpected installed version')
        extras=[p for p in destination.rglob('*') if p.is_file() and p.relative_to(destination).as_posix() not in files]
        for source in BACKUP.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(BACKUP);dest=destination/rel
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe target')
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and digest(dest)==files[rel.as_posix()]:continue
            # Never overwrite an inode shared with an archived build.
            if dest.exists():dest.unlink()
            if destination==BASE and source.stat().st_size>10*1024*1024:os.link(source,dest)
            else:shutil.copy2(source,dest)
        for extra in extras:
            if not extra.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe extra')
            extra.unlink()
        removed[str(destination)]=[p.relative_to(destination).as_posix() for p in extras]
        for rel,sha in files.items():
            if digest(destination/rel)!=sha:raise ValueError('Restore mismatch '+rel)
    shutil.copy2(BASE/'REMAINING_OBJECTS.md',ROOT/'REMAINING_OBJECTS.md')
    proof=dict(restored_version='0.1.42',previous_version='0.1.43',reason='User reports client load hangs; native dedicated validation had passed.',
        full_files_verified=len(files),failed_candidate_preserved=release['archive'],removed_candidate_extras=removed,client_reload_verified=False)
    (ROOT/'logs/art-supports-loading-rollback.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2),flush=True)
if __name__=='__main__':main()
