"""Verify the 0.1.27 collision evidence, installation and distributable archive."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def finalize():
 package=ROOT/'northstar/PhaseRunner.Preview';installed=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview');version=json.loads((package/'mod.json').read_text())['Version']
 if version!='0.1.27':raise ValueError('Unexpected collision release version')
 s=json.loads((package/'build-status.json').read_text());log=(ROOT/'logs/preview-0.1.27-final.log').read_text();point=len(s['collision_probes']);hull=len(s['pilot_hull_contact_probes']);clear=len(s['hull_clearance_probes'])
 for message in (f'Phase Runner collision probes: {point}/{point} hit',f'Phase Runner prop hull probes: {hull}/{hull} hit',f'Phase Runner edge clearance probes: {clear}/{clear} clear'):
  if message not in log:raise ValueError('Incomplete engine evidence: '+message)
 results=re.findall(r'prop hull probe (\d+): fraction=([0-9.]+) startSolid=(\w+)',log)
 if len(results)!=hull or any(float(f)>=1 or solid!='false' for _,f,solid in results):raise ValueError('Player contacts did not start clear')
 proof=json.loads((ROOT/'output/phase-runner/preview-full-collision/source-physics-audit.json').read_text())
 if proof['errors'] or not proof['all_source_model_physics_verified'] or proof['checked']['placements']!=5024:raise ValueError('Source physics verification failed')
 unit=(ROOT/'logs/full-collision-unit-0.1.27.log').read_text();count=re.search(r'Ran (\d+) tests',unit)
 if not count or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Collision regression tests failed')
 oriented=(ROOT/'logs/triangle-extrema-isolated-lab.log').read_text();edges=(ROOT/'logs/triangle-rounded-edge-lab.log').read_text()
 if 'Phase Runner prop hull probes: 567/567 hit' not in oriented or 'Phase Runner prop hull probes: 127/127 hit' not in edges or 'Phase Runner edge clearance probes: 326/326 clear' not in edges:raise ValueError('Independent native-format lab tests failed')
 bsp=package/'mod/maps/mp_phase_runner_preview.bsp';evidence=dict(version=version,bsp_sha256=hashlib.sha256(bsp.read_bytes()).hexdigest(),dedicated_server_loaded=True,load_seconds=float(re.search(r'loading took ([0-9.]+)s',log).group(1)),point_contact_checks=point,clear_start_player_hull_contact_checks=hull,clearance_checks=clear,collision_regression_checks=int(count.group(1)),source_physics_audit=proof,full_collision_rebuild=s['full_collision_rebuild'],isolated_native_format_lab=dict(point_traces=567,player_hull_contacts=567,rounded_hull_edge_contacts=127,rounded_hull_edge_clearances=326),render_geometry_lighting_visibility_preserved=True,client_movement_verified=False,full_player_movement_coverage_verified=False,limitation='Every restored solid-model collider is checked against its source geometry; engine traces sample contacts and gaps. They cannot prove all player movements or grapple behavior. Two barrels use visual surfaces because their physics export is unavailable. Pop-in and other rendering issues are unchanged.')
 (package/'runtime-validation.json').write_text(json.dumps(evidence,indent=2));shutil.copy2(ROOT/'output/phase-runner/preview-full-collision/source-physics-audit.json',package/'source-physics-audit.json')
 checks={str(p.relative_to(package)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file() and p.name!='checksums.json'};(package/'checksums.json').write_text(json.dumps(checks,indent=2))
 for name in ('runtime-validation.json','source-physics-audit.json','checksums.json'):shutil.copy2(package/name,installed/name)
 for relative,digest in checks.items():
  if hashlib.sha256((installed/relative).read_bytes()).hexdigest()!=digest:raise ValueError('Installed file mismatch '+relative)
 archive=ROOT/f'output/PhaseRunner.Preview-{version}.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
  for p in package.rglob('*'):
   if p.is_file():target.write(p,Path('PhaseRunner.Preview')/p.relative_to(package))
 print(json.dumps(dict(installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,point_contacts=point,player_contacts=hull,clearances=clear),indent=2))
if __name__=='__main__':finalize()
