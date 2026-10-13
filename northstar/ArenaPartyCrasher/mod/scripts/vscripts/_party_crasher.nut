untyped
global function ArenaPartyCrasher_Init
void function ArenaPartyCrasher_Init()
{
    if ( GetMapName() != "mp_party_crasher" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaPartyCrasher_Team )
    AddClientCommandCallback( "party_crasher_where", ArenaPartyCrasher_Where )
    thread ArenaPartyCrasher_KillFloor()
}
void function ArenaPartyCrasher_Team( entity player )
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
bool function ArenaPartyCrasher_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Party Crasher position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ArenaPartyCrasher_KillFloor()
{
    while ( true )
    {
        foreach ( entity p in GetPlayerArray() )
        {
            if ( IsValid( p ) && IsAlive( p ) && p.GetOrigin().z < -5512 )
                p.Die()
        }
        wait 0.25
    }
}
