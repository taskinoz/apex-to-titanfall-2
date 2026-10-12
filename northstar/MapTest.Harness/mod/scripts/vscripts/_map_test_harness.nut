untyped
global function MapTestHarness_Init

struct
{
    bool started = false
    bool busy = false
    int failures = 0
    string generation = ""
    entity camera = null
} file

string function MTH_Context()
{
#if UI
    return "ui"
#elseif CLIENT
    return "client"
#else
    return "server"
#endif
}

string function MTH_URL( string path )
{
    return "http://127.0.0.1:" + GetConVarInt( "map_harness_port" ) + path
}

HttpRequest function MTH_Request( string path, table body )
{
    HttpRequest r
    r.method = HttpRequestMethod.POST
    r.url = MTH_URL( path )
    r.timeout = 3
    r.headers[ "Authorization" ] <- [ "Bearer " + GetConVarString( "map_harness_token" ) ]
    r.body = EncodeJSON( body )
    return r
}

table function MTH_State()
{
    table s = {}
    s.context <- MTH_Context()
#if UI
    s.generation <- GetConVarString( "map_harness_generation" )
#else
    s.generation <- file.generation
#endif
#if UI
    s.level <- GetActiveLevel()
    s.loading <- uiGlobal.isLoading
    s.ready <- !uiGlobal.isLoading
#else
    s.level <- GetMapName()
    s.loading <- false
#if CLIENT
    entity p = GetLocalClientPlayer()
    s.ready <- IsValid( p )
    s.camera <- IsValid( file.camera )
    if ( IsValid( p ) )
    {
        vector origin = IsValid( file.camera ) ? file.camera.GetOrigin() : p.EyePosition()
        vector angles = IsValid( file.camera ) ? file.camera.GetAngles() : p.EyeAngles()
        s.origin <- [ origin.x, origin.y, origin.z ]
        s.angles <- [ angles.x, angles.y, angles.z ]
        s.alive <- IsAlive( p )
        s.health <- p.GetHealth()
        s.outOfBoundsDeadTime <- p.GetOutOfBoundsDeadTime()
        s.time <- Time()
    }
#else
    s.ready <- true
    s.mode <- GAMETYPE
    s.players <- GetPlayerArray().len()
    foreach ( entity p in GetPlayerArray() )
    {
        vector origin = p.GetOrigin()
        s.playerOrigin <- [ origin.x, origin.y, origin.z ]
    }
#endif
#endif
    return s
}

void function MapTestHarness_Init()
{
    if ( file.started )
        return
    file.started = true
#if SERVER
    // Server autoexec resets these each map. Apply before client authentication,
    // rather than after the delayed HTTP startup.
    if ( GetConVarBool( "map_harness_enabled" ) && GetConVarString( "ip" ) == "127.0.0.1" )
    {
        SetConVarBool( "ns_auth_allow_insecure", true )
        SetConVarBool( "ns_report_server_to_masterserver", false )
        SetConVarBool( "ns_report_sp_server_to_masterserver", false )
    }
#endif
    thread MTH_Start()
}

void function MTH_Start()
{
    // UI callbacks run before the initial +convar commands are executed.
    wait 1.0
    if ( !GetConVarBool( "map_harness_enabled" ) )
        return
    if ( GetConVarString( "map_harness_token" ) == "" || !NSIsHttpEnabled() || !NSIsLocalHttpAllowed() )
    {
        printl( "[MapTest.Harness] disabled: token and -allowlocalhttp required" )
        return
    }
#if SERVER
    if ( GetConVarString( "ip" ) != "127.0.0.1" )
        return
    SetConVarBool( "ns_auth_allow_insecure", true )
    SetConVarBool( "ns_report_server_to_masterserver", false )
    SetConVarBool( "ns_report_sp_server_to_masterserver", false )
#endif
    file.generation = GetConVarString( "map_harness_generation" )
    printl( "[MapTest.Harness] ready " + MTH_Context() )
    thread MTH_Poll()
}

void function MTH_Poll()
{
    wait 0.5
    while ( true )
    {
        if ( !file.busy )
        {
            file.busy = true
            HttpRequest r = MTH_Request( "/poll/" + MTH_Context(), MTH_State() )
            if ( !NSHttpRequest( r, MTH_Response, MTH_Failure ) )
                file.busy = false
        }
        wait 0.25
    }
}

void function MTH_Failure( HttpRequestFailure failure )
{
    file.busy = false
    file.failures++
    if ( file.failures == 1 || file.failures % 40 == 0 )
        printl( "[MapTest.Harness] HTTP unavailable: " + failure.errorMessage )
}

void function MTH_Response( HttpRequestResponse response )
{
    if ( response.statusCode != 200 )
    {
        file.busy = false
        return
    }
    file.failures = 0
    thread MTH_Execute( response.body )
}

vector function MTH_Position( table job )
{
    // .x/.y/.z compile as vector-component reads even on an untyped table.
    return < expect float( job.px ), expect float( job.py ), expect float( job.pz ) >
}

vector function MTH_Angles( table job )
{
    return < expect float( job.pitch ), expect float( job.yaw ), expect float( job.roll ) >
}

void function MTH_Execute( string raw )
{
    table job = {}
    table answer = {}
    string stage = "decode"
    try
    {
        job = DecodeJSON( raw )
        if ( !( "id" in job ) )
        {
            file.busy = false
            return
        }
        answer.id <- string( job.id )
        answer.ok <- true
        answer.context <- MTH_Context()
        string op = string( job.op )
        if ( op == "status" )
            answer.data <- MTH_State()
#if UI
        else if ( op == "load" )
        {
            // UI survives the map change. Replacing a connected local server
            // directly can crash; follow the normal disconnect path first.
            CloseAllDialogs()
            CloseAllMenus()
            SetConVarString( "map_harness_generation", string( job.id ) )
            ClientCommand( "disconnect" )
            wait 2.0
            ClientCommand( "ip 127.0.0.1" )
            ClientCommand( "sv_lan 1" )
            ClientCommand( "setplaylist private_match" )
            ClientCommand( "mp_gamemode " + string( job.mode ) )
            ClientCommand( "map " + string( job.map ) )
            answer.queued <- true
            answer.generation <- string( job.id )
        }
        else if ( op == "console" )
        {
            ClientCommand( string( job.command ) )
            answer.queued <- true
        }
        else if ( op == "screenshot" )
        {
            CloseAllDialogs()
            CloseAllMenus()
            ClientCommand( "hideconsole" )
            wait 0.5
            ClientCommand( "screenshot" )
            answer.queued <- true
        }
        else if ( op == "clear_ui" )
        {
            CloseAllDialogs()
            CloseAllMenus()
            ClientCommand( "hideconsole" )
        }
#elseif CLIENT
        else if ( op == "camera" )
        {
            stage = "camera_position"
            vector origin = MTH_Position( job )
            vector angles = MTH_Angles( job )
            entity player = GetLocalClientPlayer()
            if ( !IsValid( player ) )
                throw "No local client player"
            stage = "camera_create"
            if ( !IsValid( file.camera ) )
                file.camera = CreateClientSidePointCamera( origin, angles, expect float( job.fov ) )
            stage = "camera_apply"
            file.camera.SetOrigin( origin )
            file.camera.SetAngles( angles )
            file.camera.SetFOV( expect float( job.fov ) )
            player.SetMenuCameraEntity( file.camera )
            wait 0.5
            answer.data <- MTH_State()
        }
        else if ( op == "camera_clear" )
        {
            entity player = GetLocalClientPlayer()
            if ( IsValid( player ) )
                player.ClearMenuCameraEntity()
            if ( IsValid( file.camera ) )
                file.camera.Destroy()
            file.camera = null
        }
#else
        else if ( op == "camera_follow" )
        {
            array<entity> players = GetPlayerArray()
            if ( players.len() != 1 || !IsAlive( players[0] ) )
                throw "Camera capture requires exactly one live local player"
            entity p = players[0]
            p.SetInvulnerable()
            p.SetPhysics( MOVETYPE_NOCLIP )
            p.SetOrigin( MTH_Position( job ) )
            p.SnapEyeAngles( MTH_Angles( job ) )
            p.SetVelocity( < 0, 0, 0 > )
            p.FreezeControlsOnServer()
            answer.data <- MTH_State()
        }
        else if ( op == "camera_restore" )
        {
            foreach ( entity p in GetPlayerArray() )
            {
                p.SetPhysics( MOVETYPE_WALK )
                p.UnfreezeControlsOnServer()
                p.ClearInvulnerable()
            }
            answer.data <- MTH_State()
        }
        else if ( op == "spawn_probe" )
        {
            array results = []
            foreach ( point in job.points )
            {
                vector candidate = < expect float( point[0] ), expect float( point[1] ), expect float( point[2] ) >
                TraceResults floor = TraceLine( candidate + < 0, 0, 96 >, candidate - < 0, 0, 256 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
                vector pos = floor.endPos + < 0, 0, 8 >
                TraceResults pilot = TraceHull( pos, pos + < 0, 0, 1 >, < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
                TraceResults titan = TraceHull( pos, pos + < 0, 0, 1 >, < -100, -100, 0 >, < 100, 100, 400 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
                results.append( { origin = [ pos.x, pos.y, pos.z ], floor = !floor.startSolid && floor.fraction < 1.0,
                    pilot = !pilot.startSolid && pilot.fraction >= 0.99, titan = !titan.startSolid && titan.fraction >= 0.99 } )
            }
            answer.data <- results
        }
        else if ( op == "mode_check" )
        {
            table counts = {}
            foreach ( name in [ "info_spawnpoint_human_start", "info_spawnpoint_human", "info_spawnpoint_titan_start", "info_spawnpoint_titan", "info_spawnpoint_flag", "info_hardpoint", "trigger_out_of_bounds", "trigger_hurt", "move_rope", "keyframe_rope" ] )
                counts[name] <- GetEntArrayByClass_Expensive( name ).len()
            answer.data <- { map = GetMapName(), mode = GAMETYPE, entities = counts }
        }
        else if ( op == "respawn" )
        {
            array<entity> players = GetPlayerArray()
            if ( players.len() != 1 )
                throw "Respawn check requires exactly one local player"
            entity p = players[0]
            SetTeam( p, expect int( job.team ) )
            // Exercise native team/start selection without killing the test
            // player, which would end an elimination round with one client.
            entity spawn = FindSpawnPoint( p, false, true )
            p.SetOrigin( spawn.GetOrigin() )
            p.SnapEyeAngles( spawn.GetAngles() )
            p.SetVelocity( < 0, 0, 0 > )
            p.SetInvulnerable()
            p.FreezeControlsOnServer()
            vector pos = p.GetOrigin()
            answer.data <- { team = p.GetTeam(), spawnTeam = spawn.GetTeam(), classname = spawn.GetClassName(), origin = [ pos.x, pos.y, pos.z ] }
        }
        else if ( op == "player" )
        {
            array<entity> players = GetPlayerArray()
            if ( players.len() != 1 )
                throw "Player placement requires exactly one local player"
            entity p = players[0]
            if ( p.GetTeam() != TEAM_IMC && p.GetTeam() != TEAM_MILITIA )
                SetTeam( p, TEAM_IMC )
            if ( !IsAlive( p ) )
                p.RespawnPlayer( null )
            p.SetOrigin( MTH_Position( job ) )
            p.SnapEyeAngles( MTH_Angles( job ) )
            p.SetVelocity( < 0, 0, 0 > )
            if ( "invulnerable" in job && !expect bool( job.invulnerable ) )
                p.ClearInvulnerable()
            else
                p.SetInvulnerable()
            if ( expect bool( job.freeze ) )
                p.FreezeControlsOnServer()
            else
                p.UnfreezeControlsOnServer()
            answer.data <- MTH_State()
        }
        else if ( op == "trace" )
        {
            vector start = MTH_Position( job )
            vector end = < expect float( job.ex ), expect float( job.ey ), expect float( job.ez ) >
            TraceResults r = TraceLine( start, end, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            table t = {}
            t.fraction <- r.fraction
            t.startSolid <- r.startSolid
            t.end <- [ r.endPos.x, r.endPos.y, r.endPos.z ]
            answer.data <- t
        }
#endif
        else
            throw "Unsupported action for " + MTH_Context() + ": " + op
    }
    catch ( e )
    {
        answer.ok <- false
        answer.error <- string( e )
        answer.stage <- stage
        if ( "id" in job && !( "id" in answer ) )
            answer.id <- string( job.id )
        printl( "[MapTest.Harness] command failed: " + string( e ) )
    }
    if ( "id" in answer )
    {
        HttpRequest r = MTH_Request( "/ack", answer )
        NSHttpRequest( r )
    }
    file.busy = false
}
