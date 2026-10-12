untyped
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
