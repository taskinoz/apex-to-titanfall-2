"""Stage the independent Composite mod, keeping the existing Phase Runner intact."""
import json,shutil,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output/composite';MOD=ROOT/'northstar/ArenaComposite';MAP='mp_arena_composite'
def package():
    for source,dest in ((OUT/(MAP+'.bsp'),MOD/'mod/maps'/(MAP+'.bsp')),(OUT/(MAP+'.stbsp'),MOD/'mod/maps'/(MAP+'.stbsp')),(OUT/'materials/build/composite_world.rpak',MOD/'paks/composite_world.rpak'),(OUT/'presentation/build/composite_presentation.rpak',MOD/'paks/composite_presentation.rpak')):
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():dest.unlink()
        os.link(source,dest)
    dependency=MOD/'paks/drop_off_native_dependencies.rpak'
    if dependency.exists():dependency.unlink()
    mod=dict(Name='ArenaComposite',Version='0.6.0',LoadPriority=10,Description='Drop-Off arena port with restored equipment supports and tank containers, corrected lightmap gutters and an isolated menu stage.',Scripts=[dict(Path='_arena_composite.nut',RunOn='SERVER && MP',ServerCallback={'After':'ArenaComposite_Init'})],Localisation=['resource/composite_%language%.txt'])
    (MOD/'mod.json').write_text(json.dumps(mod,indent=2))
    # Keep BSP material dependencies alive for the whole native map lifetime.
    # A map-regex pack is reloaded during repeated map setup and invalidates
    # cached materials; a raw Coliseum dependency preload stalls startup.
    (MOD/'paks/rpak.json').write_text(json.dumps(dict(Aliases={MAP+'.rpak':'mp_coliseum.rpak',MAP+'_loadscreen.rpak':'composite_presentation.rpak'},Postload={'composite_world.rpak':'mp_coliseum.rpak'}),indent=2))
    scripts=MOD/'mod/scripts/vscripts';scripts.mkdir(parents=True,exist_ok=True)
    (scripts/'_arena_composite.nut').write_text('''untyped
global function ArenaComposite_Init
void function ArenaComposite_Init()
{
    if ( GetMapName() != "mp_arena_composite" )
        return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaComposite_Team )
    AddClientCommandCallback( "composite_where", ArenaComposite_Where )
}
void function ArenaComposite_Team( entity player )
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
bool function ArenaComposite_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Drop-Off position: " + p.x + " " + p.y + " " + p.z )
    return true
}
''')
    resources=MOD/'mod/resource';resources.mkdir(parents=True,exist_ok=True)
    for language in ('english','french','german','italian','japanese','mspanish','polish','portuguese','russian','spanish','tchinese','schinese','korean'):
        text='"lang"\n{\n "Language" "'+language+'"\n "Tokens"\n {\n "mp_arena_composite" "Drop-Off"\n "mp_arena_composite_ALLCAPS" "DROP-OFF"\n "mp_arena_composite_CLASSIC_DESC" "An industrial arena converted for Titanfall 2."\n }\n}\n'
        (resources/('composite_'+language+'.txt')).write_text(text,encoding='utf-16')
    shutil.copy2(OUT/'source-build.json',MOD/'build-status.json')
    from map_pack_lifetime import scope
    scope(MOD/'paks', MAP)
    print('Staged',MOD)
if __name__=='__main__':package()
