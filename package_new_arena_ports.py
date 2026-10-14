"""Stage independent Northstar previews without changing installed releases."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from new_arena_ports import CONFIG, ROOT, WORK, VERSION, folder


def presentation(ident):
    import present_composite as p
    out = folder(ident)
    pictures = list((out / 'legion/exported_files/images').glob('*.png'))
    if len(pictures) != 1:
        raise ValueError('Source loading artwork must be identified unambiguously')
    p.OUT = out / 'presentation'
    p.ART = pictures[0]
    p.OUT.mkdir(parents=True, exist_ok=True)
    p.build(CONFIG[ident]['target'], ident.replace('-', '_'), CONFIG[ident]['name'])


def overview_assets(ident):
    out=folder(ident);tool=out/'legion';log=out/'overview-export.log'
    with log.open('w') as stream:
        run=subprocess.run([str(tool/'LegionPlus.exe'),'--export',str(out/'paks'/(CONFIG[ident]['source']+'.rpak')),
                            '--loaduiimages','--imgfmt','dds'],cwd=tool,stdout=stream,stderr=subprocess.STDOUT)
    run.check_returncode()
    print(ident,'overview atlas files',len(list((tool/'exported_files/atlases').rglob('*.dds'))),flush=True)


def package(ident):
    c = CONFIG[ident]
    out = folder(ident)
    mod = WORK / 'candidates' / c['package']
    slug = ident.replace('-', '_')
    for src, dst in (
        (out / (c['target']+'.bsp'), mod / 'mod/maps' / (c['target']+'.bsp')),
        (out / (c['target']+'.stbsp'), mod / 'mod/maps' / (c['target']+'.stbsp')),
        (out / 'materials/build' / (slug+'_world.rpak'), mod / 'paks' / (slug+'_world.rpak')),
        (out / 'presentation/build' / (slug+'_presentation.rpak'), mod / 'paks' / (slug+'_presentation.rpak'))):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    function = c['package'] + '_Init'
    script = '_' + slug + '.nut'
    (mod / 'mod.json').write_text(json.dumps(dict(Name=c['package'], Version=VERSION, LoadPriority=10,
        Description=c['name']+' native conversion preview. AI navigation and source gameplay systems are incomplete.',
        Scripts=[dict(Path=script, RunOn='SERVER && MP', ServerCallback={'After':function})],
        Localisation=['resource/'+slug+'_%language%.txt']),indent=2))
    mounts=dict(Aliases={c['target']+'.rpak':'mp_coliseum.rpak',
        c['target']+'_loadscreen.rpak':slug+'_presentation.rpak'},Postload={slug+'_world.rpak':'mp_coliseum.rpak'})
    minimap=out/'minimap/build'/(slug+'_minimap.rpak')
    if minimap.exists():
        shutil.copy2(minimap,mod/'paks'/minimap.name);mounts[minimap.name]='^'+c['target']+'$'
    (mod/'paks/rpak.json').write_text(json.dumps(mounts,indent=2))
    scripts=mod/'mod/scripts/vscripts';scripts.mkdir(parents=True,exist_ok=True)
    code='''untyped
global function @INIT@
void function @INIT@()
{
    if ( GetMapName() != "@MAP@" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( @PACKAGE@_Team )
    AddClientCommandCallback( "@SLUG@_where", @PACKAGE@_Where )
    thread @PACKAGE@_KillFloor()
}
void function @PACKAGE@_Team( entity player )
{
    if ( GAMETYPE == "ffa" ) return
    int imc = 0
    int militia = 0
    foreach ( entity p in GetPlayerArray() )
    {
        if ( p == player ) continue
        if ( p.GetTeam() == TEAM_IMC ) imc++
        if ( p.GetTeam() == TEAM_MILITIA ) militia++
    }
    SetTeam( player, imc <= militia ? TEAM_IMC : TEAM_MILITIA )
}
bool function @PACKAGE@_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "@NAME@ position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function @PACKAGE@_KillFloor()
{
    while ( true )
    {
        foreach ( entity p in GetPlayerArray() )
        {
            if ( IsValid( p ) && IsAlive( p ) && p.GetOrigin().z < @KILLZ@ )
                p.Die()
        }
        wait 0.25
    }
}
'''
    for key,value in dict(INIT=function,MAP=c['target'],PACKAGE=c['package'],SLUG=slug,
                          NAME=c['name'],KILLZ=c['bounds'][0][2]-512).items():
        code=code.replace('@'+key+'@',str(value))
    (scripts/script).write_text(code)
    resources=mod/'mod/resource';resources.mkdir(parents=True,exist_ok=True)
    for language in ('english','french','german','italian','japanese','mspanish','polish','portuguese',
                     'russian','spanish','tchinese','schinese','korean'):
        text='"lang"\n{\n "Language" "'+language+'"\n "Tokens"\n {\n "'+c['target']+'" "'+c['name']+'"\n "'+c['target']+'_ALLCAPS" "'+c['name'].upper()+'"\n "'+c['target']+'_CLASSIC_DESC" "An Apex map converted for Titanfall 2."\n }\n}\n'
        (resources/(slug+'_'+language+'.txt')).write_text(text,encoding='utf-16')
    status=json.loads((out/'source-build.json').read_text())
    status.update(version=VERSION,candidate=True,client_verified=False,release_ready=False)
    (mod/'build-status.json').write_text(json.dumps(status,indent=2))
    (mod/'README.md').write_text('# '+c['name']+' conversion preview\n\nMap: `'+c['target']+'`.\n\nThis staged candidate has not yet passed native gameplay and rendering checks.\n')
    from map_pack_lifetime import scope
    scope(mod/'paks', c['target'])
    print('Staged',mod,flush=True)


if __name__=='__main__':
    action,ident=sys.argv[1:3]
    for name in CONFIG if ident=='all' else [ident]:
        dict(presentation=presentation,package=package,overview_assets=overview_assets)[action](name)
