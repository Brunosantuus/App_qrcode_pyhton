from supabase import create_client, Client

SUPABASE_URL = "https://dqtmjcwgzceqfolkbwfk.supabase.co"  # Substitua pela sua URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRxdG1qY3dnemNlcWZvbGtid2ZrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5ODE3MzQsImV4cCI6MjA2MjU1NzczNH0.DTU9dtF39w7igQV2EENZNqKfBNtt50-u6C_hVC9ppt8"  # Substitua pela sua chave API
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("usuarios").select("*").eq("cpf", "12345678900").execute()
print(response.data)