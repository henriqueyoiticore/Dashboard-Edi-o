import os
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
ID_AJUSTES = '1y8bw87uE8xkYFJMhKWbu-9Az1d6D8U3lJ5r_lfrjziI'

def main():
    if not os.path.exists('token.json'):
        print("token.json not found")
        return
        
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    
    result = service.spreadsheets().values().get(spreadsheetId=ID_AJUSTES, range='A:ZZ').execute()
    values = result.get('values', [])
    
    if not values:
        print("No values")
        return
        
    header = values[0]
    print("Columns in Sheets:")
    for i, h in enumerate(header):
        print(f"[{i}] {h}")
        
    col_status = next((c for c in header if 'status' in str(c).lower() or 'demandado' in str(c).lower()), None)
    print(f"\nDetected Status Column: {col_status}")
    if col_status:
        print(f"Index: {header.index(col_status)}")

if __name__ == "__main__":
    main()
