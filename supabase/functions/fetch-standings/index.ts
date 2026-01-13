// Supabase Edge Function: Fetch NBA Standings
// Fetches standings with clutch records and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-standings] Starting fetch for season ${season}`)
    
    // Fetch regular standings
    const standingsParams = {
      'LeagueID': '00',
      'Season': season,
      'SeasonType': 'Regular Season'
    }
    
    const standingsData = await fetchNBAData('leaguestandingsv3', standingsParams)
    const standings = parseNBAResponse(standingsData)
    
    // Fetch clutch team stats for clutch record
    const clutchParams = {
      'LeagueID': '00',
      'Season': season,
      'SeasonType': 'Regular Season',
      'PerMode': 'Totals',
      'ClutchTime': 'Last 5 Minutes',
      'AheadBehind': 'Ahead or Behind',
      'PointDiff': '5'
    }
    
    let clutchData: any[] = []
    try {
      const clutchApiData = await fetchNBAData('leaguedashteamclutch', clutchParams)
      clutchData = parseNBAResponse(clutchApiData)
    } catch (error) {
      console.warn('[fetch-standings] Could not fetch clutch data:', error)
    }
    
    // Merge clutch data with standings
    const standingsWithClutch = standings.map((team: any) => {
      const clutchTeam = clutchData.find((c: any) => c.TEAM_ID === team.TEAM_ID)
      if (clutchTeam) {
        const clutchWins = clutchTeam.W || 0
        const clutchLosses = clutchTeam.L || 0
        team.CLUTCH_RECORD = `${clutchWins}-${clutchLosses}`
      } else {
        team.CLUTCH_RECORD = '0-0'
      }
      return team
    })
    
    if (standingsWithClutch.length === 0) {
      return new Response(
        JSON.stringify({ success: false, message: 'No standings data returned' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }
    
    // Upsert into database
    const { error } = await supabase
      .from('nba_standings')
      .upsert({
        season,
        data: standingsWithClutch,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'season'
      })
    
    if (error) {
      throw error
    }
    
    console.log(`[fetch-standings] Successfully stored ${standingsWithClutch.length} team standings`)
    
    return new Response(
      JSON.stringify({ success: true, message: `Standings fetched successfully (${standingsWithClutch.length} teams)` }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-standings')
  }
})

