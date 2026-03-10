import pandas as pd
from dashboard import carregar_dados
import streamlit as st

# Simulação simplificada
raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_ranking_editores, df_prioridades = carregar_dados()

def find_date_col(df):
    keywords = ['data', 'carimbo', 'upload', 'solicita', 'inicio', 'solicitação']
    for col in df.columns:
        if any(k in col.lower() for k in keywords):
            return col
    return df.columns[0]

def parse_prioridade_date(val, ref_year):
    try:
        if not val or str(val).strip() == "": return pd.NaT
        # Tenta parse direto
        d = pd.to_datetime(val, errors='coerce', dayfirst=True)
        if pd.notnull(d):
            # Se o ano for o atual mas a string não tem o ano atual, pode ser DD/MM
            # Ex: "30/10" vira 2026-10-30 se hoje for 2026.
            # Se queremos 2025, precisamos substituir.
            val_str = str(val)
            if len(val_str.split('/')) == 2:
                return d.replace(year=ref_year)
            return d
        return pd.NaT
    except: return pd.NaT

if not df_prioridades.empty:
    col_data_pr = find_date_col(df_prioridades)
    print(f"DEBUG: Coluna de data encontrada: {col_data_pr}")
    
    # Simular o ref_year (pegando da Ocorrencias)
    col_data_oc = find_date_col(raw_ocorrencias)
    raw_ocorrencias['Data'] = pd.to_datetime(raw_ocorrencias[col_data_oc], errors='coerce', dayfirst=True)
    ref_year = raw_ocorrencias['Data'].dt.year.mode()[0] if not raw_ocorrencias.empty else 2025
    print(f"DEBUG: Ano de referência (Ocorrencias mode): {ref_year}")
    
    df_prioridades['_Data'] = df_prioridades[col_data_pr].apply(lambda x: parse_prioridade_date(x, ref_year))
    df_prioridades['_Mes_Ano'] = df_prioridades['_Data'].dt.strftime('%m/%Y').fillna('Desconhecido')
    
    print("\nDEBUG: Primeiras 10 linhas processadas:")
    print(df_prioridades[[col_data_pr, '_Mes_Ano']].head(10))
    
    print("\nDEBUG: Meses únicos encontrados:")
    print(df_prioridades['_Mes_Ano'].unique())
