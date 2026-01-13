// Supabase Edge Function: Fetch pbpstats.com Data
// Fetches team and opponent stats from pbpstats.com API and stores in database

import { getSupabaseClient, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-pbpstats] Starting fetch for season ${season}`)
    
    const statTypes = ['team', 'opponent']
    
    for (const statType of statTypes) {
      try {
        // pbpstats.com API endpoint
        const url = 'https://api.pbpstats.com/get-totals/nba'
        const params = new URLSearchParams({
          'Season': season,
          'SeasonType': 'Regular Season',
          'Type': statType === 'team' ? 'Team' : 'Opponent'
        })
        
        const response = await fetch(`${url}?${params.toString()}`, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          }
        })
        
        if (!response.ok) {
          throw new Error(`pbpstats API error: ${response.status} ${response.statusText}`)
        }
        
        const apiData = await response.json()
        const statsData = apiData.multi_row_table_data || []
        
        if (statsData.length === 0) {
          console.log(`[fetch-pbpstats] No data for ${statType}`)
          continue
        }
        
        // Upsert into database
        const { error } = await supabase
          .from('nba_pbpstats')
          .upsert({
            season,
            stat_type: statType,
            data: statsData,
            updated_at: new Date().toISOString()
          }, {
            onConflict: 'season,stat_type'
          })
        
        if (error) {
          console.error(`[fetch-pbpstats] Database error for ${statType}:`, error)
        } else {
          console.log(`[fetch-pbpstats] Successfully stored ${statType} stats (${statsData.length} teams)`)
        }
        
        // Small delay between stat types
        await new Promise(resolve => setTimeout(resolve, 500))
      } catch (error) {
        console.error(`[fetch-pbpstats] Error fetching ${statType} stats:`, error)
      }
    }
    
    return new Response(
      JSON.stringify({ success: true, message: 'pbpstats data fetched successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-pbpstats')
  }
})

