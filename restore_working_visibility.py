"""Restore the exact archived 0.1.27 package after the failed 0.1.28 experiment."""
import hashlib,json,shutil,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def restore():
    stage=ROOT/'output/phase-runner/rollback-0.1.27'
    stage.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ROOT/'output/PhaseRunner.Preview-0.1.27.zip') as archive:
        for member in archive.infolist():
            target=(stage/member.filename).resolve()
            if not target.is_relative_to(stage.resolve()):raise ValueError('Archive path leaves rollback staging')
        archive.extractall(stage)
    original=stage/'PhaseRunner.Preview'
    checks=json.loads((original/'checksums.json').read_text())
    if json.loads((original/'mod.json').read_text())['Version']!='0.1.27':
        raise ValueError('Unexpected rollback version')
    for relative,expected in checks.items():
        if digest(original/relative)!=expected:raise ValueError('Archived file mismatch: '+relative)
    for destination in (ROOT/'northstar/PhaseRunner.Preview',Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in original.rglob('*'):
            if p.is_file():
                target=destination/p.relative_to(original);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(p,target)
        for relative,expected in checks.items():
            if digest(destination/relative)!=expected:raise ValueError('Restored file mismatch: '+relative)
    report=dict(restored_version='0.1.27',restored_files_verified=len(checks),
        restored_bsp_sha256=checks['mod/maps/mp_phase_runner_preview.bsp'],
        failed_experiment='0.1.28',client_report='No rocks or objects visible',
        visibility_failure_unresolved=True,collision_preserved=True)
    (ROOT/'logs/visibility-0.1.28-rollback.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':restore()
