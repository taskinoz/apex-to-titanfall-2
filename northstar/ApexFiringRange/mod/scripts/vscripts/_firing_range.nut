untyped
global function ApexFiringRange_Init
void function ApexFiringRange_Init()
{
    if ( GetMapName() != "mp_apex_firing_range" ) return
    ClassicMP_SetCustomIntro( ClassicMP_DefaultNoIntro_Setup, ClassicMP_DefaultNoIntro_GetLength() )
    ClassicMP_ForceDisableEpilogue( true )
    AddCallback_OnClientConnected( ApexFiringRange_Team )
    AddClientCommandCallback( "firing_range_where", ApexFiringRange_Where )
    thread ApexFiringRange_KillFloor()
}
void function ApexFiringRange_Team( entity player )
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
bool function ApexFiringRange_Where( entity player, array<string> args )
{
    vector p = player.GetOrigin()
    printl( "Firing Range position: " + p.x + " " + p.y + " " + p.z )
    return true
}
void function ApexFiringRange_KillFloor()
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
