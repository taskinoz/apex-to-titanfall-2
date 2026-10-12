untyped
global function PhaseRunnerModes_Init
global function PhaseRunnerModes_Check

void function PhaseRunnerModes_Init()
{
    AddCallback_EntitiesDidLoad( PhaseRunnerModes_TitanClearance )
    if ( GAMETYPE == "fastball" )
    {
        SetSpawnpointGamemodeOverride( TEAM_DEATHMATCH )
        FastballAddBuddySpawnForLevel( "mp_phase_runner", TEAM_IMC, BUDDY_0, < 0, 0, 0 > )
        FastballAddBuddySpawnForLevel( "mp_phase_runner", TEAM_MILITIA, BUDDY_1, < 0, 180, 0 > )
        FastballAddPanelSpawnsForLevel( "mp_phase_runner", [ PANEL_POSITIONS ] )
        ClassicMP_SetCustomIntro( GamemodeFastballIntroSetup, 14.5 )
    }
    printl( "Phase Runner gameplay: IMC west / Militia east, native spawns and objectives." )
}

void function PhaseRunnerModes_TitanClearance()
{
    // The native spawn loader drops markers onto terrain after entity parsing.
    // Restore a small standing clearance only when a full Titan hull proves
    // it fits there; this never bypasses collision or invents a floor.
    foreach ( string cls in [ "info_spawnpoint_titan", "info_spawnpoint_titan_start" ] )
    {
        foreach ( entity point in GetEntArrayByClass_Expensive( cls ) )
        {
            vector pos = point.GetOrigin()
            TraceResults atFloor = TraceHull( pos, pos + < 0, 0, 1 >, < -100, -100, 0 >, < 100, 100, 400 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            if ( !atFloor.startSolid && atFloor.fraction >= 0.99 ) continue
            vector lifted = pos + < 0, 0, 8 >
            TraceResults clear = TraceHull( lifted, lifted + < 0, 0, 1 >, < -100, -100, 0 >, < 100, 100, 400 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            TraceResults floor = TraceLine( lifted, lifted - < 0, 0, 32 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            if ( !clear.startSolid && clear.fraction >= 0.99 && !floor.startSolid && floor.fraction < 1.0 )
                point.SetOrigin( lifted )
        }
    }
}

table function PhaseRunnerModes_Check()
{
    if ( GetMapName() != "mp_phase_runner" )
        throw "Gameplay checks require Phase Runner"
    table result = { mode = GAMETYPE, spawns = {}, blocked = [], unsupported = [], objectives = [] }
    foreach ( string cls in [ "info_spawnpoint_human_start", "info_spawnpoint_human", "info_spawnpoint_titan_start", "info_spawnpoint_titan", "info_spawnpoint_flag" ] )
    {
        array<entity> points = GetEntArrayByClass_Expensive( cls )
        table counts = { total = points.len(), imc = 0, militia = 0, neutral = 0 }
        foreach ( entity point in points )
        {
            if ( point.GetTeam() == TEAM_IMC ) counts.imc++
            else if ( point.GetTeam() == TEAM_MILITIA ) counts.militia++
            else counts.neutral++
            vector pos = point.GetOrigin()
            bool titan = cls.find( "titan" ) != null
            vector mins = titan ? < -100, -100, 0 > : < -16, -16, 0 >
            vector maxs = titan ? < 100, 100, 400 > : < 16, 16, 72 >
            TraceResults space = TraceHull( pos, pos + < 0, 0, 1 >, mins, maxs, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            TraceResults floor = TraceLine( pos, pos - < 0, 0, 32 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )
            if ( space.startSolid || space.fraction < 0.99 ) result.blocked.append( point.GetTargetName() )
            if ( floor.startSolid || floor.fraction >= 1.0 ) result.unsupported.append( point.GetTargetName() )
        }
        result.spawns[cls] <- counts
    }
    if ( GAMETYPE == "cp" )
    {
        foreach ( string group in [ "A", "B", "C" ] )
        {
            entity hp = GetGlobalNetEnt( "objective" + group + "Ent" )
            result.objectives.append( { group = group, valid = IsValid( hp ), team = IsValid( hp ) ? hp.GetTeam() : -1,
                progress = GetGlobalNetFloat( "objective" + group + "Progress" ) } )
        }
    }
    if ( GAMETYPE == "ctf" )
    {
        foreach ( string flag in [ "imcFlag", "milFlag" ] )
            result.objectives.append( { name = flag, valid = IsValid( GetGlobalNetEnt( flag ) ) } )
    }
    if ( GAMETYPE == "fastball" )
        result.panels <- GetEntArrayByClass_Expensive( "prop_control_panel" ).len()
    result.ok <- result.blocked.len() == 0 && result.unsupported.len() == 0
    printl( "Phase Runner mode check: " + EncodeJSON( result ) )
    return result
}
