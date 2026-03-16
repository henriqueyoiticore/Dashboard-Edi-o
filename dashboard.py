import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopos necessários para ler e escrever no Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# IDs das planilhas (Extraídos dos links originais)
ID_AJUSTES = '1y8bw87uE8xkYFJMhKWbu-9Az1d6D8U3lJ5r_lfrjziI'
ID_FOLHA = '1PD2pwNYNUt1laQn_L2ikbVJmRk8Y0KKBHtS-kaV-Lqs'
ID_OCORRENCIAS_1 = '14o86RRH7x5cUylXk6ryEMr14bH12Y94UFDGaz6JOxkM'
ID_OCORRENCIAS_FORA = '16noLo9yfByjZLh4ZPbROz8p-RWdFZpxtiU2Uhz6ffhw'
ID_ORDEM_PRIORIDADE = '1IAPh05sT-HlQPUdhJ9WYdgDK2Frjb_YLbzHrznVZz5o'

# =====================================================================
# CONFIGURAÇÃO INICIAL DA PÁGINA - FrameControl DNA
# =====================================================================
st.set_page_config(
    page_title="FrameControl | Dashboard de Edição",
    page_icon="🎞️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injeção de CSS para Identidade Visual "Precision Cut"
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap');

        :root {
            --surface-page: #F8FAFC;
            --surface-card: #FFFFFF;
            --accent-primary: #8B5CF6;
            --text-primary: #1E293B;
            --text-secondary: #FFFFFF;
            --border-subtle: rgba(0,0,0,0.06);
            --status-error: #EF4444;
            --status-warning: #F59E0B;
            --status-success: #10B981;
        }

        /* Forçar Fundo Branco e Texto Escuro em Tudo sem Quebrar Ícones */
        .stApp {
            background-color: #F8FAFC !important;
        }

        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3 {
            color: #1E293B !important;
            font-family: 'Inter', sans-serif;
        }

        /* Sidebar - Fundo Branco e Texto Escuro */
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
            background-color: #FFFFFF !important;
            border-right: 1px solid var(--border-subtle);
        }
        
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebarNav"] span {
            color: #1E293B !important;
            opacity: 1 !important;
        }

        /* Restaurar Font dos Ícones */
        [data-testid="stIcon"] {
            font-family: "Material Symbols Outlined", "Material Icons", sans-serif !important;
        }

        /* Metrics Styling */
        [data-testid="stMetricValue"] {
            color: var(--accent-primary) !important;
            font-weight: 700 !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #475569 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.75rem !important;
            font-weight: 600 !important;
        }

        /* Cards e Containers */
        .stMetric {
            background: #FFFFFF !important;
            border: 1px solid var(--border-subtle) !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            border-radius: 12px !important;
            padding: 20px !important;
        }

        /* Corrigir inputs (Selectbox) para texto claro (fundo escuro) */
        [data-baseweb="select"] div {
            color: #FFFFFF !important;

        #MainMenu, footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# 1. AUTENTICAÇÃO E EXTRAÇÃO DE DADOS VIA API
# =====================================================================
def get_google_sheets_service():
    """Autentica o acesso ao Sheets (Suporta Modo Local e Cloud)."""
    
    # 1. Tentar Autenticação via Service Account (Recomendado para Streamlit Cloud)
    try:
        if "gcp_service_account" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=SCOPES
            )
            return build('sheets', 'v4', credentials=creds)
    except:
        pass # Ignora erro de segredos não encontrados localmente

    # 2. Modo Local / Fallback (OAuth User Flow)
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Se não temos token e estamos no Cloud, o run_local_server vai falhar
            # Verificamos se client_secret existe para tentar o fluxo local
            if os.path.exists('client_secret.json'):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    st.error("Erro de Autenticação: O servidor não pode abrir um navegador para login.")
                    st.info("👉 Para rodar no nuvem (Streamlit Cloud), você deve usar uma **Service Account**.")
                    st.stop()
            else:
                st.error("Credenciais Google não encontradas (client_secret.json ou st.secrets).")
                st.stop()

    return build('sheets', 'v4', credentials=creds)

def get_sheet_data(service, spreadsheet_id, range_name, silent=False):
    """Puxa os dados de uma aba específica da planilha e converte para Pandas DataFrame."""
    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            return pd.DataFrame()
            
        # Transforma os dados retornados em um DataFrame do Pandas
        header = values[0]
        data = values[1:]
        
        # Garantir colunas únicas (ex: '', '', '' -> 'Unnamed_1', 'Unnamed_2')
        new_header = []
        counts = {}
        for h in header:
            val = str(h).strip()
            if val == "": val = "Unnamed"
            if val in counts:
                counts[val] += 1
                new_header.append(f"{val}_{counts[val]}")
            else:
                counts[val] = 0
                new_header.append(val)
        header = new_header

        # Ajusta as linhas para terem o mesmo tamanho do cabeçalho
        num_cols = len(header)
        adjusted_data = []
        for i, row in enumerate(data):
            if len(row) < num_cols:
                row.extend([''] * (num_cols - len(row)))
            elif len(row) > num_cols:
                row = row[:num_cols]
            row.append(i + 2) # ROW INDEX no Google Sheets (1-indexed + header)
            adjusted_data.append(row)

        header.append('_SheetRowIdx')
        df = pd.DataFrame(adjusted_data, columns=header)
        return df
    except Exception as e:
        if not silent:
            st.error(f"Erro ao ler a planilha ID {spreadsheet_id}: {e}")
        return pd.DataFrame()

def update_sheet_cell(service, spreadsheet_id, row_idx, col_idx, value):
    """Atualiza uma célula específica na planilha."""
    try:
        # Converter col_idx (0-based) para letra da coluna
        dividend = col_idx + 1
        col_letter = ''
        while dividend > 0:
            modulo = (dividend - 1) % 26
            col_letter = chr(65 + modulo) + col_letter
            dividend = int((dividend - modulo) / 26)
        
        range_name = f"{col_letter}{row_idx}"
        body = {'values': [[value]]}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption="USER_ENTERED", body=body).execute()
        return True, ""
    except Exception as e:
        erro_str = str(e)
        print(f"Erro ao atualizar planilha: {erro_str}")
        return False, erro_str

@st.cache_data(ttl=120)
def carregar_dados():
    service = get_google_sheets_service()

    # NOTA: Aqui nós definimos o Range genérico para pegar todas as colunas da primeira aba
    # Se uma planilha tiver um nome de aba específico (ex: 'Ocorrências!A:Z'), podemos ajustar aqui.
    # Por padrão, se não passar o nome da aba, a API vai tentar pegar da primeira aba visível.
    # Para planilhas simples, o range 'A:Z' costuma funcionar bem.
    
    # IMPORTANTE: A API do Sheets precisa do nome da aba + Range se houver múltiplas abas.
    # Como não sei os nomes das abas, vou tentar pegar o Range padrão de Dados. Se falhar, você me avisa os nomes das abas depois.
    # ——— Processar Folha de Pagamento (Múltiplas Abas de Meses) ———
    # Lista de abas que representam meses (baseado na estrutura da planilha)
    abas_meses = ['Outubro', 'Novembro', 'Dezembro', 'Janeiro', 'Fevereiro', 'Março']
    map_mes_pt = {
        'Outubro': '10/2025', 'Novembro': '11/2025', 'Dezembro': '12/2025',
        'Janeiro': '01/2026', 'Fevereiro': '02/2026', 'Março': '03/2026'
    }
    
    dfs_folha = []
    for aba in abas_meses:
        try:
            # Silent=True para não travar se o mês ainda não foi criado na folha
            df_m = get_sheet_data(service, ID_FOLHA, f"'{aba}'!A:Z", silent=True)
            if not df_m.empty:
                df_m['Mes_Ano'] = map_mes_pt.get(aba, 'Desconhecido')
                # Garantir que a coluna 'Vídeos' existe e é tratada como número
                col_v = next((c for c in df_m.columns if 'vídeo' in c.lower() or 'video' in c.lower()), None)
                if col_v:
                    df_m['_Producao'] = pd.to_numeric(df_m[col_v], errors='coerce').fillna(0)
                dfs_folha.append(df_m)
        except: continue
        
    df_folha = pd.concat(dfs_folha, ignore_index=True) if dfs_folha else pd.DataFrame()

    df_ajustes = get_sheet_data(service, ID_AJUSTES, 'A:ZZ')
    df_ocorrencias = get_sheet_data(service, ID_OCORRENCIAS_1, 'A:Z')
    df_ocorrencias_fora = get_sheet_data(service, ID_OCORRENCIAS_FORA, 'A:Z')
    # Aba com ranking consolidado (sem data - usada quando filtro = Todos)
    df_ranking_editores = get_sheet_data(service, ID_ORDEM_PRIORIDADE, 'Ranking editores!A:B')
    # Aba com todas as demandas e datas (usada para filtrar por mês)
    df_prioridades = get_sheet_data(service, ID_ORDEM_PRIORIDADE, 'Prioridades!A:H')
    
    return df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_ranking_editores, df_prioridades


# =====================================================================
# 2. TRATAMENTO DE DADOS (COM ÍNDICE DE PROLIXIDADE)
# =====================================================================
def preparar_dados(df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_prioridades):
    try:
        # Helper para encontrar coluna de data por palavras-chave
        def find_date_col(df):
            keywords = ['data', 'carimbo', 'upload', 'solicita', 'inicio', 'solicitação']
            for col in df.columns:
                if any(k in col.lower() for k in keywords):
                    return col
            return df.columns[0] # Fallback
            
        # Parse robusto de data (especialmente para DD/MM e formatos variados)
        def robust_date_parse(val):
            if not val or str(val).strip().lower() in ['', 'nan', 'none']: 
                return pd.NaT
            s = str(val).strip()
            
            # 1. Tenta formatos com Ano
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    return pd.to_datetime(s, format=fmt)
                except: continue
                
            # 2. Se for DD/MM, tenta inferir o ano (2025 ou 2026)
            # Baseado na proximidade com a data atual ou dados da planilha
            if s.count('/') == 1:
                parts = s.split('/')
                if len(parts) == 2:
                    try:
                        d, m = int(parts[0]), int(parts[1])
                        # Se o mês for alto (ex: Nov), provavelmente é 2025. Se for baixo (Jan), 2026.
                        # Mas melhor tentar converter e ver se faz sentido.
                        # Por padrão, se estamos em 2026, tentamos 2026 primeiro.
                        test_year = 2026
                        if m >= 10: test_year = 2025 # Out/Nov/Dez costumam ser do ano passado nesse contexto
                        return pd.to_datetime(f"{s}/{test_year}", format="%d/%m/%Y")
                    except: pass
            
            # 3. Fallback pandas
            return pd.to_datetime(s, errors='coerce', dayfirst=True)

        # Processar Ajustes (Tickets)
        if not df_ajustes.empty:
            col_data_aj = find_date_col(df_ajustes)
            df_ajustes['DataSort'] = df_ajustes[col_data_aj].apply(robust_date_parse)
            df_ajustes = df_ajustes.sort_values('DataSort', ascending=False)

        # Processar Ocorrências
        if not df_ocorrencias.empty:
            col_data = find_date_col(df_ocorrencias)
            df_ocorrencias['Data'] = df_ocorrencias[col_data].apply(robust_date_parse)
            df_ocorrencias['Mes_Ano'] = df_ocorrencias['Data'].dt.strftime('%m/%Y').fillna('Desconhecido')
        
        # Processar Erros Fora
        if not df_ocorrencias_fora.empty:
            col_data_fora = find_date_col(df_ocorrencias_fora)
            df_ocorrencias_fora['Data'] = df_ocorrencias_fora[col_data_fora].apply(robust_date_parse)
            df_ocorrencias_fora['Mes_Ano'] = df_ocorrencias_fora['Data'].dt.strftime('%m/%Y').fillna('Desconhecido')
        
        # Processar Folha (Já vem com Mes_Ano do carregar_dados)
        if not df_folha.empty:
            # Se já tivermos _Producao, não precisamos de find_date_col pra Folha (ela é mensal)
            # Mas para o filtro global de datas, podemos tentar inferir uma data fictícia do mês
            def inferir_data_folha(mes_ano):
                try:
                    return pd.to_datetime(f"01/{mes_ano}", format="%d/%m/%Y")
                except: return pd.NaT
            df_folha['Data'] = df_folha['Mes_Ano'].apply(inferir_data_folha)

        # Processar Prioridades (Aba Central)
        if not df_prioridades.empty:
            # PRIORIDADE: Usar 'Prazo real' para alinhar com a visualização do usuário
            col_data_pr = next((c for c in df_prioridades.columns if 'prazo' in c.lower()), find_date_col(df_prioridades))
            df_prioridades['_Data'] = df_prioridades[col_data_pr].apply(robust_date_parse)
            df_prioridades['_Mes_Ano'] = df_prioridades['_Data'].dt.strftime('%m/%Y').fillna('Desconhecido')

        # Ordenar por data (Mais recentes primeiro)
        if not df_ocorrencias.empty and 'Data' in df_ocorrencias.columns:
            df_ocorrencias = df_ocorrencias.sort_values('Data', ascending=False)
        if not df_ocorrencias_fora.empty and 'Data' in df_ocorrencias_fora.columns:
            df_ocorrencias_fora = df_ocorrencias_fora.sort_values('Data', ascending=False)
        if not df_folha.empty and 'Data' in df_folha.columns:
            df_folha = df_folha.sort_values('Data', ascending=False)

        # 📌 MANTENDO OS DADOS BRUTOS E CRIANDO O ÍNDICE DE PROLIXIDADE
        if not df_ocorrencias.empty:
            col_descricao = next((col for col in df_ocorrencias.columns if any(k in col.lower() for k in ['detalhamento', 'descri', 'ocorrencia'])), df_ocorrencias.columns[3] if len(df_ocorrencias.columns) > 3 else df_ocorrencias.columns[-1])
            df_ocorrencias['Texto_Bruto'] = df_ocorrencias[col_descricao].fillna("Sem descrição")
            
            # 📌 NOVA CATEGORIZAÇÃO DE OCORRÊNCIAS (SEÇÃO EDIÇÃO)
            def categorizar(texto):
                t = str(texto).lower()
                if any(q in t for q in ['prazo', 'atraso', 'demora', 'quando', 'cade', 'cadê', 'cobrança', 'pronto', 'prontos', 'falta', 'hoje', 'ainda n', 'dia']): return "COBRANÇA DE PRAZO"
                if any(q in t for q in ['simples', 'rápido', 'fácil', 'pequeno', 'tarja', 'logo', 'texto']): return "TAREFA SIMPLES"
                if any(q in t for q in ['problema', 'erro', 'falha', 'técnico', 'áudio', 'render', 'corrompido', 'som', 'ruído']): return "PROBLEMA TÉCNICO"
                if any(q in t for q in ['múltiplos', 'vários', 'lote', 'pacote', 'mais de um', 'dois', 'três', 'bloco']): return "MÚLTIPLOS VÍDEOS"
                if any(q in t for q in ['ajuste', 'correção', 'corrigir', 'mudar', 'alterar', 'refazer', 'cor', 'corte']): return "AJUSTES/CORREÇÕES"
                if any(q in t for q in ['doc', 'documento', 'drive', 'link', 'pasta']): return "CORREÇÕES (VIA DOCS)"
                if any(q in t for q in ['crític', 'urgente', 'cliente', 'pra ontem', 'reclam']): return "CRÍTICO/URGENTE"
                if any(q in t for q in ['status', 'como está', 'andamento', 'feito']): return "STATUS DE CORREÇÕES"
                if any(q in t for q in ['formato', 'reels', 'shorts', 'tiktok', 'quadrado', 'horizontal', 'vertical', 'proporção', 'broll', 'b-roll', 'inserção']): return "MUDANÇA DE FORMATO"
                if any(q in t for q in ['pendente', 'esqueceu', 'não foi']): return "VÍDEOS PENDENTES"
                return "OUTROS"
                
            df_ocorrencias['Tipo_Ocorrência'] = df_ocorrencias['Texto_Bruto'].apply(categorizar)

        # 📌 NOVA CATEGORIZAÇÃO DE OCORRÊNCIAS (FORA DA EDIÇÃO)
        if not df_ocorrencias_fora.empty:
            def categorizar_fora(texto):
                t = str(texto).lower()
                if any(q in t for q in ['status', 'planilha', 'não mudaram', 'não colocaram', 'saber que tem', 'manual']): return "PROCESSO/STATUS (PLANILHA)"
                if any(q in t for q in ['corrompido', 'grava', 'áudio', 'ruim', 'inalterado', 'separado', 'incompleto', 'baixa qualidade']): return "PROB. TÉCNICO (GRAVAÇÃO)"
                if any(q in t for q in ['desorganizado', 'bagunça', 'quebra cabeça', 'procurar', 'pasta', 'drive', 'Dropbox']): return "DESORGANIZAÇÃO DE DRIVE"
                if any(q in t for q in ['upload', 'subiu', 'demora', 'atraso', 'link']): return "ATRASO DE UPLOAD/LINK"
                if any(q in t for q in ['ajuste', 'alteração', 'meses depois', 'tempo depois', 'antigo', 'refazer', 'picado']): return "AJUSTES TARDIOS/PICADOS"
                return "OUTROS"

            col_desc_fora = next((col for col in df_ocorrencias_fora.columns if any(k in col.lower() for k in ['incidente', 'descri', 'ocorrencia'])), df_ocorrencias_fora.columns[1] if len(df_ocorrencias_fora.columns) > 1 else df_ocorrencias_fora.columns[-1])
            df_ocorrencias_fora['Tipo_Ocorrência'] = df_ocorrencias_fora[col_desc_fora].fillna("Sem descrição").apply(categorizar_fora)

    except Exception as e:
        st.warning(f"Aviso no tratamento dos dados: {e}")
        
    return df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_prioridades

# =====================================================================
# INTERFACE DO DASHBOARD
# =====================================================================

def render_header(titulo, subtitulo):
    st.markdown(f"""
<div style="background-color: white; padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border-subtle); margin-bottom: 2rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); display: flex; align-items: center; gap: 1.5rem;">
    <div style="background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%); width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 10px 15px -3px rgba(124, 58, 237, 0.3);">
        <svg viewBox="0 0 24 24" width="32" height="32" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
    </div>
    <div>
        <h1 style="margin: 0; font-size: 1.75rem; color: #1E293B; letter-spacing: -0.025em; font-weight: 800;">{titulo}</h1>
        <p style="margin: 0; color: #64748B; font-size: 0.875rem; font-weight: 500;">{subtitulo}</p>
    </div>
</div>
""", unsafe_allow_html=True)

def render_dashboard(df_ocorrencias, df_ocorrencias_fora, df_folha, df_prioridades, df_ranking_editores, filtro_label, map_filtro):
    render_header("Painel Gerencial - Setor de Edição de Vídeos", "Diretoria de Operações | Monitoramento de Edição")
    
    # ---------------- FILTRO MENSAL SIDEBAR ----------------
    if filtro_label != "Todos":
        filtro_mes = map_filtro[filtro_label]
        if not df_ocorrencias.empty and 'Mes_Ano' in df_ocorrencias.columns:
            df_ocorrencias = df_ocorrencias[df_ocorrencias['Mes_Ano'] == filtro_mes]
        if not df_ocorrencias_fora.empty and 'Mes_Ano' in df_ocorrencias_fora.columns:
            df_ocorrencias_fora = df_ocorrencias_fora[df_ocorrencias_fora['Mes_Ano'] == filtro_mes]
        if not df_folha.empty and 'Mes_Ano' in df_folha.columns:
            df_folha = df_folha[df_folha['Mes_Ano'] == filtro_mes]
        if not df_prioridades.empty and '_Mes_Ano' in df_prioridades.columns:
            df_prioridades = df_prioridades[df_prioridades['_Mes_Ano'] == filtro_mes]

    # ---------------- PREPARAÇÃO DO RANKING DE EDITORES ----------------
    df_ranking_edit_local = pd.DataFrame(columns=['Editor', 'Demandas'])
    if not df_prioridades.empty:
        try:
            col_ed = next((c for c in df_prioridades.columns if 'editor' in c.lower()), None)
            if col_ed:
                col_pt = next((c for c in df_prioridades.columns if 'ponto' in c.lower() or 'quantidade' in c.lower()), None)
                if col_pt:
                    df_prioridades['_P'] = pd.to_numeric(df_prioridades[col_pt], errors='coerce').fillna(0)
                    df_res = df_prioridades.groupby(col_ed)['_P'].sum().reset_index()
                else:
                    df_res = df_prioridades.groupby(col_ed).size().reset_index()
                df_res.columns = ['Editor', 'Demandas']
                df_ranking_edit_local = df_res
        except Exception as e:
            st.error(f"Erro na agregação de editores: {e}")

    # ---------------- CÁLCULO DE MÉTRICAS ----------------
    total_ocorrencias_gerais = len(df_ocorrencias)
    total_fora_controle = len(df_ocorrencias_fora)
    total_videos = int(df_folha['_Producao'].sum()) if not df_folha.empty and '_Producao' in df_folha.columns else 0

    cobrancas_prazo = len(df_ocorrencias[df_ocorrencias['Tipo_Ocorrência'] == 'COBRANÇA DE PRAZO']) if not df_ocorrencias.empty and 'Tipo_Ocorrência' in df_ocorrencias.columns else 0
    ocorrencias_internas = total_ocorrencias_gerais - total_fora_controle - cobrancas_prazo

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Vídeos Produzidos", f"{total_videos:,}".replace(',', '.'))
    with col2: st.metric("Incidentes Totais", total_ocorrencias_gerais)
    with col3: st.metric("Erros Fora do Controle", total_fora_controle)
    with col4: st.metric("Ocorrências Internas Edição", ocorrencias_internas)
    
    st.divider()

    # ---------------- GRAFICOS ----------------
    col_graf_1, col_graf_2 = st.columns([1, 1])
    with col_graf_1:
        st.subheader("📊 Distribuição por Tipo de Ocorrência")
        if 'Tipo_Ocorrência' in df_ocorrencias.columns and not df_ocorrencias.empty:
            contagem_tipos = df_ocorrencias['Tipo_Ocorrência'].value_counts().reset_index()
            contagem_tipos.columns = ['Categoria', 'Quantidade']
            total_ocr = contagem_tipos['Quantidade'].sum()
            contagem_tipos['Percentual'] = (contagem_tipos['Quantidade'] / total_ocr) * 100
            contagem_tipos['LabelText'] = contagem_tipos.apply(lambda row: f"{row['Quantidade']} ({row['Percentual']:.1f}%)", axis=1)
            contagem_tipos['Cor'] = contagem_tipos['Categoria'].apply(lambda x: '#EF4444' if x == 'COBRANÇA DE PRAZO' else '#3F3F46')
            contagem_tipos = contagem_tipos.sort_values(by='Quantidade', ascending=True)

            fig_tipos = px.bar(contagem_tipos, x='Quantidade', y='Categoria', orientation='h', text='LabelText')
            fig_tipos.update_traces(marker_color=contagem_tipos['Cor'], textposition='outside', marker_line_width=0)
            fig_tipos.update_layout(
                template="plotly_white", 
                xaxis_title="Quantidade", 
                yaxis_title="", 
                showlegend=False, 
                font={"color": "#1E293B", "family": "Inter", "size": 12},
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)', 
                margin={"l": 0, "r": 40, "t": 10, "b": 40},
                xaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}, "title_font": {"color": "#1E293B", "weight": "bold"}},
                yaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}}
            )
            st.plotly_chart(fig_tipos, use_container_width=True)
        else: st.info("Sem dados de ocorrência.")

    with col_graf_2:
        st.subheader("🚀 Produção por Editor (Demandas)")
        if not df_ranking_edit_local.empty:
            df_edit = df_ranking_edit_local.copy()
            EDITORES_DEMITIDOS = ['adão', 'adao', 'letícia', 'leticia', 'thiago santos']
            df_edit = df_edit[~df_edit['Editor'].str.lower().str.strip().isin(EDITORES_DEMITIDOS)]
            df_edit = df_edit[df_edit['Demandas'] > 0].sort_values('Demandas', ascending=True)
            if not df_edit.empty:
                total_demandas = df_edit['Demandas'].sum()
                df_edit['Percentual'] = (df_edit['Demandas'] / total_demandas * 100).round(1)
                df_edit['LabelText'] = df_edit.apply(lambda r: f"{r['Demandas']} ({r['Percentual']:.1f}%)", axis=1)
                fig2 = px.bar(df_edit, x='Demandas', y='Editor', orientation='h', text='LabelText')
                fig2.update_traces(marker_color='#8B5CF6', textposition='outside', marker_line_width=0)
                fig2.update_layout(
                    template="plotly_white", 
                    xaxis_title="Demandas/Pontos", 
                    yaxis_title="", 
                    showlegend=False, 
                    font={"color": "#1E293B", "family": "Inter", "size": 12},
                    plot_bgcolor='rgba(0,0,0,0)', 
                    paper_bgcolor='rgba(0,0,0,0)', 
                    margin={"l": 0, "r": 50, "t": 10, "b": 40},
                    xaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}, "title_font": {"color": "#1E293B", "weight": "bold"}},
                    yaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}}
                )
                st.plotly_chart(fig2, use_container_width=True)
            else: st.info("Nenhuma demanda encontrada.")
        else: st.info("Dados de editores não encontrados.")

    st.divider()
    
    # ---------------- ERROS FORA ----------------
    col_fora_1, col_fora_2 = st.columns([1, 1])
    with col_fora_1:
        st.subheader("🚨 Erros Fora da Edição (Tipos)")
        if 'Tipo_Ocorrência' in df_ocorrencias_fora.columns and not df_ocorrencias_fora.empty:
            df_tipos_fora = df_ocorrencias_fora['Tipo_Ocorrência'].value_counts().reset_index()
            df_tipos_fora.columns = ['Categoria', 'Quantidade']
            df_tipos_fora['LabelText'] = df_tipos_fora['Quantidade'].astype(str)
            df_tipos_fora = df_tipos_fora.sort_values('Quantidade', ascending=True)
            fig3 = px.bar(df_tipos_fora, x='Quantidade', y='Categoria', orientation='h', text='LabelText')
            fig3.update_traces(marker_color='#f39c12', textposition='outside')
            fig3.update_layout(
                template="plotly_white", 
                xaxis_title="Quantidade", 
                yaxis_title="", 
                showlegend=False, 
                font={"color": "#1E293B", "family": "Inter", "size": 12},
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}, "title_font": {"color": "#1E293B", "weight": "bold"}},
                yaxis={"tickfont": {"color": "#1E293B", "weight": "bold"}},
                margin={"l": 0, "r": 40, "t": 10, "b": 40}
            )
            st.plotly_chart(fig3, use_container_width=True)
        else: st.info("Sem ocorrências externas.")

    with col_fora_2:
        st.subheader("📋 Lista de Incidentes Externos")
        if not df_ocorrencias_fora.empty:
            busca_cliente = st.text_input("🔍 Buscar por Cliente", key="search_ext")
            df_f_fora = df_ocorrencias_fora.copy()
            if busca_cliente:
                col_c = next((c for c in df_f_fora.columns if 'cliente' in c.lower()), None)
                if col_c: df_f_fora = df_f_fora[df_f_fora[col_c].astype(str).str.contains(busca_cliente, case=False, na=False)]
            cols_v = [c for c in df_f_fora.columns if not c.startswith('_') and c not in ['Mes_Ano', 'Data']]
            st.dataframe(df_f_fora[cols_v], use_container_width=True, hide_index=True)

    st.divider()

    # ---------------- CENTRAL DE AVISOS ----------------
    st.header("🔔 Central de Avisos - Gestão de Prazos")
    df_raw = st.session_state.get('df_prioridades_raw', pd.DataFrame())
    if not df_raw.empty:
        hoje = pd.Timestamp.now().normalize()
        v_atrasados = df_raw[(df_raw['_Data'] < hoje) & (df_raw['Entregue'].str.lower() != 'entregou')]
        v_semana = df_raw[(df_raw['_Data'] >= hoje) & (df_raw['_Data'] <= hoje + pd.Timedelta(days=(6 - hoje.weekday()))) & (df_raw['Entregue'].str.lower() != 'entregou')]
        
        c_v = ['Nome', 'Editor', 'Prazo real', 'Entregue']
        st.markdown('<div style="color:#9F1239; font-weight:700;">🚨 Atrasados</div>', unsafe_allow_html=True)
        if not v_atrasados.empty: st.dataframe(v_atrasados[c_v], use_container_width=True, hide_index=True)
        else: st.success("Tudo em dia!")
        
        st.markdown('<div style="color:#5B21B6; font-weight:700; margin-top:20px;">📅 Entregas desta Semana</div>', unsafe_allow_html=True)
        if not v_semana.empty: st.dataframe(v_semana[c_v], use_container_width=True, hide_index=True)
        else: st.info("Fila vazia para esta semana.")

def render_dossie(df_ocorrencias, df_ocorrencias_fora, df_ajustes, df_prioridades):
    render_header("Dossiê do Cliente", "Histórico Consolidado | Visão 360º")
    
    # Barra de busca centralizada
    col_s1, col_s2, col_s3 = st.columns([1, 2, 1])
    with col_s2:
        # Usar session_state para permitir que botões de sugestão preencham a busca
        if 'search_dossie_val' not in st.session_state:
            st.session_state['search_dossie_val'] = ""
            
        nome_busca = st.text_input("👤 Nome do Cliente", value=st.session_state['search_dossie_val'], placeholder="Digite o nome para gerar o dossiê...", help="Busca em todas as bases de dados")
        btn_gerar = st.button("Gerar Dossiê Completo", use_container_width=True, type="primary")

    if nome_busca or btn_gerar:
        # Normalizar nomes para busca
        termo = str(nome_busca).strip().lower()
        
        if not termo:
            st.warning("Por favor, digite um nome para pesquisar.")
            return

        # 1. Identificar colunas de nome em cada base
        col_n_aj = next((c for c in df_ajustes.columns if 'nome' in c.lower()), None)
        col_n_oc = next((c for c in df_ocorrencias.columns if 'mentorado' in c.lower() or 'cliente' in c.lower()), None)
        col_n_of = next((c for c in df_ocorrencias_fora.columns if 'cliente' in c.lower()), None)
        col_n_pr = next((c for c in df_prioridades.columns if 'nome' in c.lower()), None)

        # 2. Filtrar Dados
        res_aj = df_ajustes[df_ajustes[col_n_aj].astype(str).str.lower().str.contains(termo, na=False)] if col_n_aj else pd.DataFrame()
        res_oc = df_ocorrencias[df_ocorrencias[col_n_oc].astype(str).str.lower().str.contains(termo, na=False)] if col_n_oc else pd.DataFrame()
        res_of = df_ocorrencias_fora[df_ocorrencias_fora[col_n_of].astype(str).str.lower().str.contains(termo, na=False)] if col_n_of else pd.DataFrame()
        res_pr = df_prioridades[df_prioridades[col_n_pr].astype(str).str.lower().str.contains(termo, na=False)] if col_n_pr else pd.DataFrame()

        if res_aj.empty and res_oc.empty and res_of.empty and res_pr.empty:
            st.error(f"Nenhum registro encontrado para '{nome_busca}'.")
            return

        # 3. Métricas de Resumo
        st.subheader("📊 Resumo de Atividades")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tickets de Ajuste", len(res_aj))
        m2.metric("Incidentes (Edição)", len(res_oc))
        m3.metric("Incidentes (Externos)", len(res_of))
        m4.metric("Vídeos em Pauta", len(res_pr))

        # 4. Blocos de Informação
        tab1, tab2, tab3, tab4 = st.tabs(["🕒 Histórico de Ocorrências", "🎫 Tickets de Ajuste", "🎬 Status de Produção", "🚨 Incidentes Externos"])

        with tab1:
            st.markdown("### Histórico Consolidado de Incidentes")
            # Unificar ocorrências internas e externas para linha do tempo
            timeline = []
            
            if not res_oc.empty:
                for _, r in res_oc.iterrows():
                    timeline.append({
                        'Data': r.get('Data', 'N/A'),
                        'Origem': '🛠️ Interno',
                        'Tipo': r.get('Tipo_Ocorrência', 'Outros'),
                        'Descrição': r.get('Texto_Bruto', 'N/A')
                    })
            
            if not res_of.empty:
                col_d_of = next((c for c in df_ocorrencias_fora.columns if 'descri' in c.lower()), 'Descrição')
                for _, r in res_of.iterrows():
                    timeline.append({
                        'Data': r.get('Data', 'N/A'),
                        'Origem': '🚨 Externo',
                        'Tipo': r.get('Tipo_Ocorrência', 'Outros'),
                        'Descrição': r.get(col_d_of, 'N/A')
                    })
            
            if timeline:
                df_timeline = pd.DataFrame(timeline).sort_values('Data', ascending=False)
                st.dataframe(df_timeline, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma ocorrência registrada para este cliente.")

        with tab2:
            st.markdown("### Solicitações de Ajustes (Tickets)")
            if not res_aj.empty:
                cols_aj = [c for c in res_aj.columns if not c.startswith('_') and c not in ['Endereço de e-mail']]
                st.dataframe(res_aj[cols_aj], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum ticket de ajuste encontrado.")

        with tab3:
            st.markdown("### Status Atual na Produção")
            if not res_pr.empty:
                cols_pr = [c for c in res_pr.columns if not c.startswith('_')]
                st.dataframe(res_pr[cols_pr], use_container_width=True, hide_index=True)
                
                # Highlight de Atrasos
                atrasados = res_pr[res_pr['Entregue'].str.lower() != 'entregou']
                if not atrasados.empty:
                    st.warning(f"⚠️ Existem {len(atrasados)} vídeos com entrega pendente para este cliente.")
            else:
                st.info("Cliente não encontrado na pauta de produção atual.")

        with tab4:
            st.markdown("### Incidentes Fora da Edição")
            if not res_of.empty:
                cols_of = [c for c in res_of.columns if not c.startswith('_') and c not in ['Mes_Ano', 'Data']]
                st.dataframe(res_of[cols_of], use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum incidente externo registrado para este cliente.")

    else:
        # Tela inicial do dossiê
        st.info("Use a busca acima para encontrar o histórico de um cliente específico.")

def render_ajustes(df_ajustes):
    render_header("Ajustes de Edição", "Gestão de Tickets | Solicitações de Clientes")
    
    if df_ajustes.empty:
        st.info("Nenhuma solicitação de ajuste encontrada na planilha.")
        return

    # Campo de Busca
    busca = st.text_input("🔍 Buscar por Cliente", placeholder="Digite o nome do cliente...", key="search_ajustes")
    
    # Processar dados para exibição em cards
    # Normalizar nomes de colunas (remover espaços extras e lidar com acentos)
    df_ajustes.columns = [c.strip() for c in df_ajustes.columns]
    
    col_nome = next((c for c in df_ajustes.columns if 'nome e sobrenome' in c.lower()), 'Seu nome e sobrenome')
    col_data = next((c for c in df_ajustes.columns if 'carimbo' in c.lower()), 'Carimbo de data/hora')
    # Detectar colunas de vídeo (lidando com Vídeo, Video, vdeo, etc)
    cols_videos = [c for c in df_ajustes.columns if 'deo' in c.lower()]

    df_display = df_ajustes.copy()
    if busca:
        df_display = df_display[df_display[col_nome].astype(str).str.contains(busca, case=False, na=False)]

    if df_display.empty:
        st.warning("Nenhum ajuste encontrado para os termos buscados.")
        return

    # Encontrar coluna de Status
    col_status = next((c for c in df_ajustes.columns if 'status' in c.lower() or 'demandado' in c.lower()), None)
    idx_status = df_ajustes.columns.get_loc(col_status) if col_status else None

    # Callback para atualizar a planilha quando o checkbox mudar
    def on_demanda_change(t_id, r_idx, c_idx):
        if c_idx is not None:
            val = st.session_state[t_id]
            novo_valor = "SIM" if val else ""
            service = get_google_sheets_service()
            if service:
                try:
                    success, msg = update_sheet_cell(service, ID_AJUSTES, r_idx, c_idx, novo_valor)
                    if success:
                        st.toast(f"Status salvo na planilha!", icon="✅")
                    else:
                        st.session_state['erro_update'] = msg
                except Exception as e:
                    st.session_state['erro_update'] = str(e)
                st.cache_data.clear()

    # Mostrar erro se houver
    if 'erro_update' in st.session_state:
        st.error(f"⚠️ Erro ao salvar (A planilha tem permissão de edição?): {st.session_state['erro_update']}")
        del st.session_state['erro_update']

    # Layout de Grid para Tickets
    cols_per_row = 3
    rows = [df_display.iloc[i:i+cols_per_row] for i in range(0, len(df_display), cols_per_row)]

    for row_df in rows:
        streamlit_cols = st.columns(cols_per_row)
        for idx, (_, ticket) in enumerate(row_df.iterrows()):
            with streamlit_cols[idx]:
                # Identifier único para o checkbox no session_state
                ticket_id = f"demanda_{ticket[col_nome]}_{ticket[col_data]}"
                
                # Estado inicial do checkbox baseado na planilha
                is_demandado = False
                if col_status and pd.notna(ticket.get(col_status)):
                    is_demandado = str(ticket[col_status]).strip().upper() == "SIM"

                # Container do Card com Borda e Checkbox
                demanded = st.checkbox(
                    "Demandado", 
                    value=is_demandado, 
                    key=ticket_id,
                    on_change=on_demanda_change,
                    args=(ticket_id, ticket['_SheetRowIdx'], idx_status)
                )
                
                # Filtrar ajustes para exibir no card (respeitando a regra de ignorar "OK" e vazios)
                lista_ajustes = []
                for c in cols_videos:
                    val = str(ticket[c]).strip()
                    val_lower = val.lower()
                    # Ignorar respostas padrão que não indicam ajuste real
                    ignorados = ["", "ok", "não tinha vídeo", "nenhum", "nada", "-", "não tem video", "nao tem video", "nda", "não tem", "nao tem"]
                    if val_lower not in ignorados:
                        # Extrair um label amigável (ex: Vídeo 1)
                        # Remove prefixos longos e normaliza o nome
                        label = c.replace('Selecione o vdeo para ajuste ', '').replace(' (Vdeo ', ' (Video ').split(' (')[0]
                        lista_ajustes.append(f"<li><strong>{label}:</strong> {val}</li>")
                
                # Se a lista estiver vazia após o filtro, mostra todos os campos não vazios como fallback
                if not lista_ajustes:
                    lista_ajustes = [f"<li>{str(ticket[c])}</li>" for c in cols_videos if str(ticket[c]).strip() != ""]

                bg_color = "#F0FDF4" if demanded else "white"
                border_color = "#10B981" if demanded else "rgba(0,0,0,0.1)"
                
                st.markdown(f"""<div style="background: {bg_color}; padding: 20px; border-radius: 12px; border: 1px solid {border_color}; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); min-height: 250px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
<span style="font-size: 0.75rem; color: #64748B; font-weight: 600;">{ticket[col_data]}</span>
{f'<span style="background: #10B981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.65rem; font-weight: 800;">DEMANDADO</span>' if demanded else ''}
</div>
<h3 style="margin: 0 0 12px 0; font-size: 1.1rem; color: #1E293B; font-weight: 700;">{ticket[col_nome]}</h3>
<div style="font-size: 0.85rem; color: #334155;">
<strong style="color: #1E293B;">Ajustes solicitados:</strong>
<ul style="margin: 8px 0; padding-left: 20px; color: #334155;">
{"".join(lista_ajustes) if lista_ajustes else "<li>Solicitação sem detalhamento de vídeo.</li>"}
</ul>
</div>
</div>""", unsafe_allow_html=True)

# Main Application Logic
with st.spinner("FrameControl Engine Initializing..."):
    raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_ranking_editores, df_prioridades = carregar_dados()
    
    if raw_ocorrencias is not None:
        df_ajustes_p, df_folha_p, df_ocorrencias_p, df_ocorrencias_fora_p, df_prioridades_p = preparar_dados(raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_prioridades)
        
        st.session_state['df_prioridades_raw'] = df_prioridades_p
        
        # Sidebar Navigation
        st.sidebar.title("FrameControl")
        page = st.sidebar.radio("Navegação", ["Dashboard Principal", "Ajustes (Tickets)", "Dossiê do Cliente"])
        st.sidebar.divider()
        
        # Filtros Globais (apenas para Dashboard)
        if page == "Dashboard Principal":
            todas_datas = []
            for df, col in [(df_ocorrencias_p, 'Data'), (df_ocorrencias_fora_p, 'Data'), (df_folha_p, 'Data'), (df_prioridades_p, '_Data')]:
                if df is not None and not df.empty and col in df.columns: todas_datas.extend(df[col].dropna().unique())
            
            if todas_datas:
                df_datas_all = pd.DataFrame({'Data': todas_datas})
                df_datas_all['Data_Base'] = df_datas_all['Data'].dt.to_period('M').dt.to_timestamp()
                meses_pt = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
                datas_ordenadas = sorted(df_datas_all['Data_Base'].unique())
                meses_formatados = [f"{meses_pt[d.month]}/{d.year}" for d in datas_ordenadas]
                map_filtro = {f"{meses_pt[d.month]}/{d.year}": d.strftime('%m/%Y') for d in datas_ordenadas}
                filtro_label = st.sidebar.selectbox("Filtro Mensal", ["Todos"] + meses_formatados)
            else:
                filtro_label = "Todos"
                map_filtro = {}

            if st.sidebar.button("🔄 Atualizar Dados"):
                st.cache_data.clear()
                st.rerun()
                
            render_dashboard(df_ocorrencias_p, df_ocorrencias_fora_p, df_folha_p, df_prioridades_p, df_ranking_editores, filtro_label, map_filtro)
            
        elif page == "Ajustes (Tickets)":
            render_ajustes(df_ajustes_p)
            
        elif page == "Dossiê do Cliente":
            render_dossie(df_ocorrencias_p, df_ocorrencias_fora_p, df_ajustes_p, df_prioridades_p)
    else:
        st.warning("Falha ao carregar dados. Verifique a autenticação.")
