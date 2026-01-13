// Supabase Edge Function: Fetch NBA Drives Stats
// Fetches player and team drives statistics and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-drives-stats] Starting fetch for season ${season}`)
    
    const entityTypes = ['player', 'team']
    const playerOrTeamMap: Record<string, string> = { 'player': 'P', 'team': 'T' }
    
    for (const entityType of entityTypes) {
      try {
        const params = {
          'LeagueID': '00',
          'Season': season,
          'SeasonType': 'Regular Season',
          'PerMode': 'Totals',
          'PlayerOrTeam': playerOrTeamMap[entityType]
        }
        
        // Fetch drives stats from NBA API
        const apiData = await fetchNBAData('leaguedashptstats', params)
        const drivesData = parseNBAResponse(apiData)
        
        if (drivesData.length === 0) {
          console.log(`[fetch-drives-stats] No data for ${entityType}`)
          continue
        }
        
        // Upsert into database
        const { error } = await supabase
          .from('nba_drives_stats')
          .upsert({
            season,
            entity_type: entityType,
            data: drivesData,
            updated_at: new Date().toISOString()
          }, {
            onConflict: 'season,entity_type'
          })
        
        if (error) {
          console.error(`[fetch-drives-stats] Database error for ${entityType}:`, error)
        } else {
          console.log(`[fetch-drives-stats] Successfully stored ${entityType} drives stats (${drivesData.length} records)`)
        }
        
        // Small delay between entity types
        await new Promise(resolve => setTimeout(resolve, 500))
      } catch (error) {
        console.error(`[fetch-drives-stats] Error fetching ${entityType} drives stats:`, error)
      }
    }
    
    return new Response(
      JSON.stringify({ success: true, message: 'Drives stats fetched successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-drives-stats')
  }
})

