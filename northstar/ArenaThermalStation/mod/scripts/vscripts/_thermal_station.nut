untyped
global function ArenaThermalStation_Init
void function ArenaThermalStation_Init()
{
    if ( GetMapName() != "mp_thermal_station" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ArenaThermalStation_Team )
    AddClientCommandCallback( "thermal_station_where", ArenaThermalStation_Where )
    thread ArenaThermalStation_KillFloor()
}
void function ArenaThermalStation_Team( entity player )
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
bool function ArenaThermalStation_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Thermal Station position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ArenaThermalStation_KillFloor()
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
