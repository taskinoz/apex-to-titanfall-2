untyped
global function ArenaOverflow_Init
void function ArenaOverflow_Init()
{
    if ( GetMapName() != "mp_overflow" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaOverflow_Team )
    AddClientCommandCallback( "overflow_where", ArenaOverflow_Where )
    thread ArenaOverflow_KillFloor()
}
void function ArenaOverflow_Team( entity player )
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
bool function ArenaOverflow_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Overflow position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ArenaOverflow_KillFloor()
{
    while ( true )
    {
        foreach ( entity p in GetPlayerArray() )
        {
            if ( IsValid( p ) && IsAlive( p ) && p.GetOrigin().z < -6512 )
                p.Die()
        }
        wait 0.25
    }
}
