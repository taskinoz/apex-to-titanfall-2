untyped
global function ArenaThunderdome_Init
void function ArenaThunderdome_Init()
{
    if ( GetMapName() != "mp_thunderdome" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaThunderdome_Team )
    AddClientCommandCallback( "thunderdome_where", ArenaThunderdome_Where )
    thread ArenaThunderdome_KillFloor()
}
void function ArenaThunderdome_Team( entity player )
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
bool function ArenaThunderdome_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Thunderdome position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ArenaThunderdome_KillFloor()
{
    while ( true )
    {
        foreach ( entity p in GetPlayerArray() )
        {
            if ( IsValid( p ) && IsAlive( p ) && p.GetOrigin().z < -2012 )
                p.Die()
        }
        wait 0.25
    }
}
