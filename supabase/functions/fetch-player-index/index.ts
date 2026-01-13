// Supabase Edge Function: Fetch NBA Player Index
// Fetches player index/roster data and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-player-index] Starting fetch for season ${season}`)
    
    // Fetch player index from NBA API
    const params = {
      'LeagueID': '00',
      'Season': season
    }
    
    const apiData = await fetchNBAData('playerindex', params)
    const playerData = parseNBAResponse(apiData)
    
    if (playerData.length === 0) {
      return new Response(
        JSON.stringify({ success: false, message: 'No player index data returned' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }
    
    // Upsert into database
    const { error } = await supabase
      .from('nba_player_index')
      .upsert({
        season,
        data: playerData,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'season'
      })
    
    if (error) {
      throw error
    }
    
    console.log(`[fetch-player-index] Successfully stored ${playerData.length} player records`)
    
    return new Response(
      JSON.stringify({ success: true, message: `Player index fetched successfully (${playerData.length} players)` }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-player-index')
  }
})

