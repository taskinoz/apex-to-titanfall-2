"""Exercise map modes, native spawn selection and objective state in one owned client."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller,write_json

def main():
    c=Controller();report=ROOT/'logs/gameplay-runtime.json'
    results=json.loads(report.read_text()) if report.exists() else {}
    for mode in sys.argv[1:] or ['tdm','ps','ctf','cp','aitdm','fastball','lts','ttdm','mfd','ffa']:
        state=c.request('/status').get('contexts',{}).get('server',{})
        if state.get('level')!='mp_phase_runner' or state.get('mode')!=mode:
            c.load('mp_phase_runner',mode,120)
        time.sleep(2)
        r=c.command('server','mode_check')['data']
        if r['mode']!=mode:raise RuntimeError('Requested mode did not activate')
        results[mode]=dict(check=r,teams={})
        print(mode,'spawns',r['spawns'],'blocked',r['blocked'],'unsupported',r['unsupported'],'objectives',r['objectives'],flush=True)
        write_json(ROOT/'logs/gameplay-runtime.json',results)
        if not r['ok']:raise RuntimeError('Unsafe native spawn in '+mode)
        if mode not in ('fastball','ffa','lts','ttdm'):
            for team in (2,3):
                selected=c.command('server','respawn',team=team)['data'];results[mode]['teams'][str(team)]=selected
                if selected['spawnTeam']!=team:raise RuntimeError('Wrong native team start')
        if mode=='cp':
            for group,pos,team in [('A',[-4450,-1700,-892],2),('B',[110,-2700,-1276],2),('C',[4670,-1700,-892],3)]:
                c.command('server','respawn',team=team)
                c.command('server','player',px=pos[0],py=pos[1],pz=pos[2],pitch=0,yaw=90,roll=0,freeze=True)
                time.sleep(15)
                state=c.command('server','mode_check')['data']['objectives']
                hp=next(h for h in state if h['group']==group)
                if hp['team']!=team or hp['progress']<.99:raise RuntimeError('Hardpoint not captured: '+group)
                results[mode].setdefault('capture_tests',{})[group]=hp
            results[mode]['screenshot']=c.capture('hardpoint-captured')
        if mode=='ctf':
            if len(r['objectives'])!=2 or not all(f['valid'] for f in r['objectives']):raise RuntimeError('Missing CTF flags')
            results[mode]['screenshot']=c.capture('militia-ctf-base')
        if mode=='fastball':
            # The native throw intro runs after the client is ready.
            time.sleep(20)
            state=c.command('server','mode_check')['data'];results[mode]['after_intro']=state
            if state.get('panels')!=3:raise RuntimeError('Fastball needs three hacking panels')
            results[mode]['screenshot']=c.capture('fastball-native-intro')
        write_json(ROOT/'logs/gameplay-runtime.json',results)
    print('Native modes validated:',list(results),flush=True)
if __name__=='__main__':main()
