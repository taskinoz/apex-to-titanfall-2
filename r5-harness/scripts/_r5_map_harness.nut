// Compiled only in the isolated R5R MapHarness installation.
global function R5H_Status
struct
{
    string instance = ""
#if CLIENT
    entity camera
#endif
} file
#if CLIENT
global function R5H_Camera
global function R5H_ClearCamera
#endif
#if SERVER
global function R5H_Player
#endif

void function R5H_Status( string ticket )
{
    if ( file.instance == "" )
        file.instance = ticket
#if CLIENT
    entity player = GetLocalClientPlayer()
    int ready = IsValid( player ) ? 1 : 0
    vector origin = <0,0,0>
    vector angles = <0,0,0>
    if ( IsValid( file.camera ) )
    {
        origin = file.camera.GetOrigin()
        angles = file.camera.GetAngles()
    }
    print( format( "R5H:%s:{\"map\":\"%s\",\"context\":\"client\",\"ready\":%d,\"instance\":\"%s\",\"camera\":%d,\"origin\":[%.4f,%.4f,%.4f],\"angles\":[%.4f,%.4f,%.4f]}", ticket, GetMapName(), ready, file.instance, IsValid(file.camera) ? 1 : 0, origin.x, origin.y, origin.z, angles.x, angles.y, angles.z ) )
#elseif SERVER
    int ready = GetPlayerArray().len() > 0 ? 1 : 0
    print( format( "R5H:%s:{\"map\":\"%s\",\"context\":\"server\",\"ready\":%d,\"instance\":\"%s\"}", ticket, GetMapName(), ready, file.instance ) )
#endif
}

#if CLIENT
void function R5H_Camera( string ticket, vector origin, vector angles, float fov )
{
    entity player = GetLocalClientPlayer()
    if ( !IsValid( player ) )
        return
    if ( !IsValid( file.camera ) )
        file.camera = CreateClientSidePointCamera( origin, angles, fov )
    file.camera.SetOrigin( origin )
    file.camera.SetAngles( angles )
    file.camera.SetFOV( fov )
    player.SetMenuCameraEntity( file.camera )
    R5H_Status( ticket )
}

void function R5H_ClearCamera( string ticket )
{
    entity player = GetLocalClientPlayer()
    if ( IsValid( player ) )
        player.ClearMenuCameraEntity()
    if ( IsValid( file.camera ) )
        file.camera.Destroy()
    R5H_Status( ticket )
}
#endif

#if SERVER
void function R5H_Player( string ticket, vector origin, vector angles )
{
    foreach ( entity player in GetPlayerArray() )
    {
        player.SetOrigin( origin )
        player.SetAngles( angles )
        player.SetVelocity( <0,0,0> )
        player.SetInvulnerable()
    }
    R5H_Status( ticket )
}
#endif
