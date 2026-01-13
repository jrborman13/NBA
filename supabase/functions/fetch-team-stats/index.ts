// Supabase Edge Function: Fetch NBA Team Stats
// Fetches team stats (advanced, misc, traditional, four factors) and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    console.log(`[fetch-team-stats] Initializing Supabase client...`)
    const supabase = getSupabaseClient()
    
    if (!supabase) {
      throw new Error('Failed to initialize Supabase client')
    }
    
    console.log(`[fetch-team-stats] Supabase client initialized successfully`)
    
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-team-stats] Starting fetch for season ${season}`)
    
    // Start with just season totals to avoid timeout - can expand later
    const measureTypes = ['Advanced', 'Misc', 'Traditional', 'Four Factors']
    const lastNGamesOptions = [null] // Start with just season totals
    const groupQuantityOptions = [null] // Start with just overall stats
    
    let successCount = 0
    let errorCount = 0
    
    for (const measureType of measureTypes) {
      for (const lastNGames of lastNGamesOptions) {
        for (const groupQuantity of groupQuantityOptions) {
          try {
            // Build NBA API parameters
            const params: Record<string, string> = {
              'LeagueID': '00',
              'Season': season,
              'SeasonType': 'Regular Season',
              'MeasureType': measureType === 'Four Factors' ? 'Four Factors' : measureType,
              'PerMode': 'PerGame'
            }
            
            if (lastNGames) {
              params['LastNGames'] = lastNGames.toString()
            }
            
            if (groupQuantity) {
              params['GroupQuantity'] = groupQuantity
            }
            
            // Fetch from NBA API
            console.log(`[fetch-team-stats] Fetching NBA API for ${measureType}...`)
            let apiData
            try {
              apiData = await fetchNBAData('leaguedashteamstats', params)
              console.log(`[fetch-team-stats] NBA API response received for ${measureType}`)
            } catch (apiError) {
              console.error(`[fetch-team-stats] NBA API error for ${measureType}:`, apiError)
              throw apiError
            }
            
            console.log(`[fetch-team-stats] Parsing NBA API response for ${measureType}...`)
            const statsData = parseNBAResponse(apiData)
            console.log(`[fetch-team-stats] Parsed ${statsData.length} teams for ${measureType}`)
            
            if (statsData.length === 0) {
              console.log(`[fetch-team-stats] No data for ${measureType}, last_n_games=${lastNGames}, group=${groupQuantity}`)
              continue
            }
            
            // Upsert into database
            console.log(`[fetch-team-stats] Attempting to upsert ${measureType} data (${statsData.length} teams)...`)
            
            const upsertResult = await supabase
              .from('nba_team_stats')
              .upsert({
                season,
                measure_type: measureType,
                last_n_games: lastNGames,
                group_quantity: groupQuantity,
                data: statsData,
                updated_at: new Date().toISOString()
              }, {
                onConflict: 'season,measure_type,last_n_games,group_quantity'
              })
            
            if (!upsertResult) {
              console.error(`[fetch-team-stats] Upsert returned undefined for ${measureType}`)
              errorCount++
            } else if (upsertResult.error) {
              console.error(`[fetch-team-stats] Database error for ${measureType}:`, upsertResult.error)
              errorCount++
            } else {
              console.log(`[fetch-team-stats] Successfully stored ${measureType}, last_n_games=${lastNGames}, group=${groupQuantity} (${statsData.length} teams)`)
              successCount++
            }
            
            // Small delay to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 500))
          } catch (error) {
            console.error(`[fetch-team-stats] Error fetching ${measureType}, last_n_games=${lastNGames}, group=${groupQuantity}:`, error)
            errorCount++
          }
        }
      }
    }
    
    console.log(`[fetch-team-stats] Completed: ${successCount} successful, ${errorCount} errors`)
    
    return new Response(
      JSON.stringify({ 
        success: true, 
        message: `Team stats fetched: ${successCount} successful, ${errorCount} errors`,
        successCount,
        errorCount
      }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-team-stats')
  }
})

