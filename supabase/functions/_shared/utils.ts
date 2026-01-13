// Shared utilities for Supabase Edge Functions
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

// Get Supabase client
export function getSupabaseClient() {
  const supabaseUrl = Deno.env.get('SUPABASE_URL')
  const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
  
  if (!supabaseUrl) {
    throw new Error('SUPABASE_URL environment variable is not set')
  }
  
  if (!supabaseServiceKey) {
    throw new Error('SUPABASE_SERVICE_ROLE_KEY environment variable is not set')
  }
  
  console.log(`[utils] Creating Supabase client with URL: ${supabaseUrl.substring(0, 30)}...`)
  
  return createClient(supabaseUrl, supabaseServiceKey)
}

// NBA API base URL
const NBA_API_BASE = 'https://stats.nba.com/stats'

// Helper to make NBA API requests
export async function fetchNBAData(endpoint: string, params: Record<string, string>): Promise<any> {
  const url = new URL(`${NBA_API_BASE}/${endpoint}`)
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.append(key, value)
  })
  
  console.log(`[utils] Fetching NBA API: ${url.toString().substring(0, 100)}...`)
  
  try {
    // Add timeout to prevent hanging
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
    
    const response = await fetch(url.toString(), {
      headers: {
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
      },
      signal: controller.signal
    })
    
    clearTimeout(timeoutId)
    console.log(`[utils] NBA API response status: ${response.status} ${response.statusText}`)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[utils] NBA API error response: ${errorText.substring(0, 500)}`)
      throw new Error(`NBA API error: ${response.status} ${response.statusText}`)
    }
    
    const jsonData = await response.json()
    console.log(`[utils] NBA API response parsed successfully`)
    return jsonData
  } catch (error) {
    if (error.name === 'AbortError') {
      console.error(`[utils] NBA API request timed out after 30 seconds`)
      throw new Error('NBA API request timed out')
    }
    console.error(`[utils] NBA API fetch failed:`, error)
    throw error
  }
}

// Helper to parse NBA API response
export function parseNBAResponse(data: any): any[] {
  if (!data.resultSets || data.resultSets.length === 0) {
    return []
  }
  
  const resultSet = data.resultSets[0]
  const headers = resultSet.headers
  const rows = resultSet.rowSet || []
  
  return rows.map((row: any[]) => {
    const obj: any = {}
    headers.forEach((header: string, index: number) => {
      obj[header] = row[index]
    })
    return obj
  })
}

// Helper to handle errors
export function handleError(error: any, context: string): Response {
  console.error(`Error in ${context}:`, error)
  return new Response(
    JSON.stringify({ error: error.message || 'Unknown error', context }),
    { status: 500, headers: { 'Content-Type': 'application/json' } }
  )
}

// Current season constant
export const CURRENT_SEASON = '2025-26'

