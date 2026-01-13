// Supabase Edge Function: Fetch NBA Schedule
// Fetches league schedule and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-schedule] Starting fetch for season ${season}`)
    
    // Fetch schedule from NBA API
    const params = {
      'LeagueID': '00',
      'Season': season
    }
    
    const apiData = await fetchNBAData('scheduleleaguev2', params)
    const scheduleData = parseNBAResponse(apiData)
    
    if (scheduleData.length === 0) {
      return new Response(
        JSON.stringify({ success: false, message: 'No schedule data returned' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }
    
    // Upsert into database
    const { error } = await supabase
      .from('nba_schedule')
      .upsert({
        season,
        data: scheduleData,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'season'
      })
    
    if (error) {
      throw error
    }
    
    console.log(`[fetch-schedule] Successfully stored ${scheduleData.length} schedule records`)
    
    return new Response(
      JSON.stringify({ success: true, message: `Schedule fetched successfully (${scheduleData.length} games)` }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-schedule')
  }
})

