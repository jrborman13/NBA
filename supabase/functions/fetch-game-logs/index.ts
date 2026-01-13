// Supabase Edge Function: Fetch NBA Game Logs
// Fetches player and team game logs and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-game-logs] Starting fetch for season ${season}`)
    
    // Fetch player game logs
    const playerParams = {
      'Season': season,
      'SeasonType': 'Regular Season',
      'LeagueID': '00'
    }
    
    const playerApiData = await fetchNBAData('playergamelog', playerParams)
    const playerLogs = parseNBAResponse(playerApiData)
    
    if (playerLogs.length > 0) {
      const { error: playerError } = await supabase
        .from('nba_game_logs')
        .upsert({
          season,
          log_type: 'player',
          data: playerLogs,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'season,log_type'
        })
      
      if (playerError) {
        console.error('[fetch-game-logs] Error storing player logs:', playerError)
      } else {
        console.log(`[fetch-game-logs] Successfully stored ${playerLogs.length} player game logs`)
      }
    }
    
    // Small delay before fetching team logs
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // Fetch team game logs (all teams in one call)
    const teamParams = {
      'Season': season,
      'SeasonType': 'Regular Season',
      'LeagueID': '00'
    }
    
    const teamApiData = await fetchNBAData('teamgamelog', teamParams)
    const teamLogs = parseNBAResponse(teamApiData)
    
    if (teamLogs.length > 0) {
      const { error: teamError } = await supabase
        .from('nba_game_logs')
        .upsert({
          season,
          log_type: 'team',
          data: teamLogs,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'season,log_type'
        })
      
      if (teamError) {
        console.error('[fetch-game-logs] Error storing team logs:', teamError)
      } else {
        console.log(`[fetch-game-logs] Successfully stored ${teamLogs.length} team game logs`)
      }
    }
    
    return new Response(
      JSON.stringify({ 
        success: true, 
        message: `Game logs fetched successfully (${playerLogs.length} player logs, ${teamLogs.length} team logs)` 
      }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-game-logs')
  }
})

