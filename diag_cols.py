
import os
import json
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
ID_AJUSTES = '1y8bw87uE8xkYFJMhKWbu-9Az1d6D8U3lJ5r_lfrjziI'

def get_google_sheets_service():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        return build('sheets', 'v4', credentials=creds)
    return None

def main():
    service = get_google_sheets_service()
    if not service:
        print("Service account not found.")
        return
        
    ids = {
        "AJUSTES": '1y8bw87uE8xkYFJMhKWbu-9Az1d6D8U3lJ5r_lfrjziI',
        "OCORRENCIAS": '14o86RRH7x5cUylXk6ryEMr14bH12Y94UFDGaz6JOxkM',
        "OCORRENCIAS_FORA": '16noLo9yfByjZLh4ZPbROz8p-RWdFZpxtiU2Uhz6ffhw',
        "PRIORIDADES": '1IAPh05sT-HlQPUdhJ9WYdgDK2Frjb_YLbzHrznVZz5o'
    }
    
    for name, sid in ids.items():
        print(f"\n--- {name} ---")
        try:
            range_name = 'Prioridades!A1:Z1' if name == "PRIORIDADES" else 'A1:Z1'
            result = service.spreadsheets().values().get(spreadsheetId=sid, range=range_name).execute()
            values = result.get('values', [])
            if values:
                print(f"Columns: {values[0]}")
            else:
                print("No values found.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
