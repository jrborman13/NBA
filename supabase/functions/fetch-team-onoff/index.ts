// Supabase Edge Function: Fetch NBA Team On/Off Court Data
// Fetches team on/off court data for all teams and stores in database

import { getSupabaseClient, fetchNBAData, parseNBAResponse, handleError, CURRENT_SEASON } from '../_shared/utils.ts'

Deno.serve(async (req) => {
  try {
    const supabase = getSupabaseClient()
    const { season = CURRENT_SEASON } = await req.json().catch(() => ({}))
    
    console.log(`[fetch-team-onoff] Starting fetch for season ${season}`)
    
    // All 30 NBA team IDs
    const teamIds = [
      1610612737, 1610612738, 1610612739, 1610612740, 1610612741, 1610612742,
      1610612743, 1610612744, 1610612745, 1610612746, 1610612747, 1610612748,
      1610612749, 1610612750, 1610612751, 1610612752, 1610612753, 1610612754,
      1610612755, 1610612756, 1610612757, 1610612758, 1610612759, 1610612760,
      1610612761, 1610612762, 1610612763, 1610612764, 1610612765, 1610612766
    ]
    
    for (const teamId of teamIds) {
      try {
        // Fetch on/off data for this team
        const params = {
          'TeamID': teamId.toString(),
          'Season': season,
          'SeasonType': 'Regular Season',
          'PerMode': 'Totals',
          'MeasureType': 'Advanced',
          'LeagueID': '00'
        }
        
        const apiData = await fetchNBAData('teamplayeronoffdetails', params)
        
        // The API returns multiple result sets - we need to merge them
        // Result set 0: Overall
        // Result set 1: Players Off Court
        // Result set 2: Players On Court
        if (!apiData.resultSets || apiData.resultSets.length < 3) {
          console.warn(`[fetch-team-onoff] Insufficient data for team ${teamId}`)
          continue
        }
        
        const overallHeaders = apiData.resultSets[0].headers
        const overallRows = apiData.resultSets[0].rowSet || []
        const offCourtHeaders = apiData.resultSets[1].headers
        const offCourtRows = apiData.resultSets[1].rowSet || []
        const onCourtHeaders = apiData.resultSets[2].headers
        const onCourtRows = apiData.resultSets[2].rowSet || []
        
        // Merge on/off data
        const mergedData = overallRows.map((row: any[], index: number) => {
          const obj: any = {}
          overallHeaders.forEach((header: string, i: number) => {
            obj[header] = row[i]
          })
          
          // Add off court data
          if (offCourtRows[index]) {
            offCourtHeaders.forEach((header: string, i: number) => {
              obj[`${header}_OFF_COURT`] = offCourtRows[index][i]
            })
          }
          
          // Add on court data
          if (onCourtRows[index]) {
            onCourtHeaders.forEach((header: string, i: number) => {
              obj[`${header}_ON_COURT`] = onCourtRows[index][i]
            })
          }
          
          return obj
        })
        
        if (mergedData.length === 0) {
          console.log(`[fetch-team-onoff] No data for team ${teamId}`)
          continue
        }
        
        // Upsert into database
        const { error } = await supabase
          .from('nba_team_onoff')
          .upsert({
            season,
            team_id: teamId,
            data: mergedData,
            updated_at: new Date().toISOString()
          }, {
            onConflict: 'season,team_id'
          })
        
        if (error) {
          console.error(`[fetch-team-onoff] Database error for team ${teamId}:`, error)
        } else {
          console.log(`[fetch-team-onoff] Successfully stored data for team ${teamId} (${mergedData.length} players)`)
        }
        
        // Delay to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 1000))
      } catch (error) {
        console.error(`[fetch-team-onoff] Error fetching data for team ${teamId}:`, error)
      }
    }
    
    return new Response(
      JSON.stringify({ success: true, message: 'Team on/off data fetched successfully' }),
      { headers: { 'Content-Type': 'application/json' } }
    )
  } catch (error) {
    return handleError(error, 'fetch-team-onoff')
  }
})

