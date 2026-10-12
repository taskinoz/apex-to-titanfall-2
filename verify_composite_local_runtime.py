"""Native screenshots, source collider contacts and same-process reload."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller
WORK=ROOT/'output/composite/local-repair'
def verify():
 c=Controller();s=c.request('/status');pid=s['game_pid'];assert s['contexts']['client']['level']=='mp_arena_composite'
 result=dict(version='0.6.0',pid_before=pid,views=[],traces=[])
 for name,p,a in [('wall',[-1917,631,252],[-30,135,0]),('wall-wide',[-1917,631,252],[-15,90,0]),('east-wall',[1917,631,252],[-30,45,0]),('lamp',[0,2420,140],[20,-90,0]),('west-support',[-420,190,177],[3,-165,0]),('east-support',[420,190,177],[3,-15,0]),('tanks',[100,1900,-45],[10,146,0]),('court',[0,1950,300],[-6,90,0])]:
  c.camera(p,a,75,1);r=c.capture('dropoff-060-release-'+name);result['views'].append(dict(name=name,capture=r));print(name,r['path'],flush=True)
 for name,p,e in [('upper-tank',[-19,1962,0],[-19,1962,-180]),('lower-tank',[-100,1962,-125],[0,1962,-125]),('west-floor',[-438,132,160],[-438,132,100])]:
  trace=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),map(float,[*p,*e]))));assert trace['ok'] and not trace['data']['startSolid'] and trace['data']['fraction']<1,trace
  result['traces'].append(dict(name=name,trace=trace))
 c.command('client','camera_clear');result['counts']=c.command('server','mode_check');c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
 deadline=time.monotonic()+75
 while time.monotonic()<deadline:
  state=c.request('/status')
  if not state['game_running']:raise RuntimeError('Game exited after match')
  if state['contexts'].get('client',{}).get('level')=='mp_lobby':break
  time.sleep(1)
 else:raise TimeoutError('Postmatch did not return to lobby')
 result['postmatch']=dict(level=state['contexts']['client']['level'],pid=state['game_pid']);print('Postmatch lobby verified',flush=True)
 stock=c.load('mp_coliseum','ps',240);result['stock_reload']=dict(level=stock['contexts']['client']['level'],pid=stock['game_pid']);print('Stock Coliseum verified',flush=True)
 reloaded=c.load('mp_arena_composite','ps',240);result['pid_after']=reloaded['game_pid'];assert result['pid_after']==pid
 c.camera([-1917,631,252],[-30,135,0],75,1);result['reload_capture']=c.capture('dropoff-060-release-reloaded-wall');result['logs']=c.export_logs();assert not result['logs']['script_errors']
 (WORK/'runtime.json').write_text(json.dumps(result,indent=2));print('Same-process reload and clean logs verified',flush=True)
if __name__=='__main__':verify()
