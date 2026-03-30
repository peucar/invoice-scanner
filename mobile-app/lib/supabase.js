import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://vakyznenmjucjdriapoe.supabase.co'
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZha3l6bmVubWp1Y2pkcmlhcG9lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkxODIxMjcsImV4cCI6MjA2NDc1ODEyN30.a4BwRfc48H_JoszD2fSsUH06DzEBYqjy_di9EWKSKbA'

export const supabase = (supabaseUrl && supabaseAnonKey && !supabaseUrl.includes('placeholder')) 
  ? createClient(supabaseUrl, supabaseAnonKey) 
  : null
