// Supabase Edge Function: Fetch NBA Synergy Data
// Fetches team and player synergy data for all playtypes and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-synergy-data] Starting fetch for season ${season}`)
    
    const playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                      'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']
    const typeGroupings = ['offensive', 'defensive']
    const entityTypes = ['team', 'player'] // 'T' for team, 'P' for player
    
    for (const entityType of entityTypes) {
      const playerOrTeam = entityType === 'team' ? 'T' : 'P'
      
      for (const playtype of playtypes) {
        for (const typeGrouping of typeGroupings) {
          try {
            const params = {
              'LeagueID': '00',
              'Season': season,
              'SeasonType': 'Regular Season',
              'PerMode': 'Totals',
              'PlayerOrTeam': playerOrTeam,
              'PlayType': playtype,
              'TypeGrouping': typeGrouping
            }
            
            // Fetch from NBA API
            const apiData = await fetchNBAData('synergyplaytypes', params)
            const synergyData = parseNBAResponse(apiData)
            
            if (synergyData.length === 0) {
              console.log(`[fetch-synergy-data] No data for ${entityType} ${playtype} ${typeGrouping}`)
              continue
            }
            
            // Upsert into database
            const { error } = await supabase
              .from('nba_synergy_data')
              .upsert({
                season,
                entity_type: entityType,
                playtype,
                type_grouping: typeGrouping,
                data: synergyData,
                updated_at: new Date().toISOString()
              }, {
                onConflict: 'season,entity_type,playtype,type_grouping'
              })
            
            if (error) {
              console.error(`[fetch-synergy-data] Database error for ${entityType} ${playtype} ${typeGrouping}:`, error)
            } else {
              console.log(`[fetch-synergy-data] Successfully stored ${entityType} ${playtype} ${typeGrouping} (${synergyData.length} records)`)
            }
            
            // Small delay to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 500))
          } catch (error) {
            console.error(`[fetch-synergy-data] Error fetching ${entityType} ${playtype} ${typeGrouping}:`, error)
          }
        }
      }
    }
    
    return new Response(
      JSON.stringify({ success: true, message: 'Synergy data fetched successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-synergy-data')
  }
})

