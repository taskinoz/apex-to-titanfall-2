untyped
global function ArenaSkulltown_Init
void function ArenaSkulltown_Init()
{
    if ( GetMapName() != "mp_skulltown" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaSkulltown_Team )
    AddClientCommandCallback( "skulltown_where", ArenaSkulltown_Where )
    thread ArenaSkulltown_KillFloor()
}
void function ArenaSkulltown_Team( entity player )
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
bool function ArenaSkulltown_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Skulltown position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ArenaSkulltown_KillFloor()
{
    while ( true )
    {
        foreach ( entity p in GetPlayerArray() )
        {
            if ( IsValid( p ) && IsAlive( p ) && p.GetOrigin().z < -3012 )
                p.Die()
        }
        wait 0.25
    }
}
