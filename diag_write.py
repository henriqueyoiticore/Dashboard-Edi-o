import os
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
ID_AJUSTES = '1y8bw87uE8xkYFJMhKWbu-9Az1d6D8U3lJ5r_lfrjziI'

def update_sheet_cell(service, spreadsheet_id, row_idx, col_idx, value):
    try:
        dividend = col_idx + 1
        col_letter = ''
        while dividend > 0:
            modulo = (dividend - 1) % 26
            col_letter = chr(65 + modulo) + col_letter
            dividend = int((dividend - modulo) / 26)
        
        range_name = f"{col_letter}{row_idx}"
        print(f"Trying to write '{value}' to {range_name}...")
        body = {'values': [[value]]}
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption="USER_ENTERED", body=body).execute()
        print("Success:", result)
        return True
    except Exception as e:
        print(f"Error during update: {e}")
        return False

def main():
    if not os.path.exists('token.json'):
        print("token.json not found")
        return
        
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    
    # Test writing to the first data row (row 2), Status column (index 28)
    update_sheet_cell(service, ID_AJUSTES, 2, 28, "SIM_TEST")

if __name__ == "__main__":
    main()
