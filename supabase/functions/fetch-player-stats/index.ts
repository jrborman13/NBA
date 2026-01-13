// Supabase Edge Function: Fetch NBA Player Stats
// Fetches player advanced stats and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-player-stats] Starting fetch for season ${season}`)
    
    // Fetch player advanced stats
    const params = {
      'LeagueID': '00',
      'Season': season,
      'SeasonType': 'Regular Season',
      'MeasureType': 'Advanced',
      'PerMode': 'PerGame'
    }
    
    const apiData = await fetchNBAData('leaguedashplayerstats', params)
    const statsData = parseNBAResponse(apiData)
    
    if (statsData.length === 0) {
      return new Response(
        JSON.stringify({ success: false, message: 'No player stats data returned' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }
    
    // Upsert into database
    const { error } = await supabase
      .from('nba_player_stats')
      .upsert({
        season,
        measure_type: 'Advanced',
        data: statsData,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'season,measure_type'
      })
    
    if (error) {
      throw error
    }
    
    console.log(`[fetch-player-stats] Successfully stored ${statsData.length} player records`)
    
    return new Response(
      JSON.stringify({ success: true, message: `Player stats fetched successfully (${statsData.length} players)` }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-player-stats')
  }
})

