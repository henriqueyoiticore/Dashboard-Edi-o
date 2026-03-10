
import os
import json
import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
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
        
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=ID_AJUSTES, range='A:Z').execute()
    values = result.get('values', [])
    
    if not values:
        print("No values found.")
        return
        
    header = values[0]
    print("Columns found:")
    for i, h in enumerate(header):
        print(f"{i}: '{h}'")

if __name__ == "__main__":
    main()
