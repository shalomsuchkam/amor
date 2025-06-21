import { createClient } from "@supabase/supabase-js";
const supabaseUrl = "https://nyfngmkkcwoptlzycbuu.supabase.co";
const supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im55Zm5nbWtrY3dvcHRsenljYnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk5MDAwNzQsImV4cCI6MjA2NTQ3NjA3NH0.ATVhYEUtFUVyOJg-5hXxYMlqFrHI8-ao9OTxepVcMbQ";
export const supabase = createClient(supabaseUrl, supabaseKey);
