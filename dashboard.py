import streamlit as st
import pandas as pd
import plotly.express as px
import os
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Escopos necessários para ler o Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

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
            --text-secondary: #334155;
            --border-subtle: rgba(0,0,0,0.06);
            --status-error: #EF4444;
            --status-warning: #F59E0B;
            --status-success: #10B981;
        }

        /* Estrutura Base */
        .stApp {
            background-color: var(--surface-page);
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
        }

        /* Sidebar Customizada */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid var(--border-subtle);
        }

        /* Tipografia */
        h1, h2, h3, .stMetric div {
            font-family: 'Outfit', sans-serif !important;
            color: var(--text-primary) !important;
        }

        /* Metrics Styling */
        [data-testid="stMetricValue"] {
            color: var(--accent-primary) !important;
            font-weight: 700 !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: var(--text-secondary) !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.75rem !important;
            font-weight: 600 !important;
        }

        /* Cards */
        .stMetric {
            background: #FFFFFF !important;
            border: 1px solid var(--border-subtle) !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            border-radius: 12px !important;
            padding: 20px !important;
        }

        /* Botões */
        .stButton button {
            background-color: var(--accent-primary) !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: 600;
            border: none !important;
            padding: 0.5rem 1.5rem;
            transition: opacity 0.2s;
        }
        /* Legibilidade de Legendas e Captions */
        .stCaption, .stMarkdown p {
            color: #334155 !important;
        }

        /* Forçar Header Estilo Studio */
        header, [data-testid="stHeader"] {
            background-color: #FFFFFF !important;
            border-bottom: 1px solid var(--border-subtle);
        }

        /* Esconder Elementos Default Streamlit p/ Limpeza */
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
        for row in data:
            if len(row) < num_cols:
                row.extend([''] * (num_cols - len(row)))
            elif len(row) > num_cols:
                row = row[:num_cols]
            adjusted_data.append(row)

        df = pd.DataFrame(adjusted_data, columns=header)
        return df
    except Exception as e:
        if not silent:
            st.error(f"Erro ao ler a planilha ID {spreadsheet_id}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
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

    df_ajustes = get_sheet_data(service, ID_AJUSTES, 'A:Z')
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

        # Processar Ocorrências
        col_data = find_date_col(df_ocorrencias)
        df_ocorrencias['Data'] = df_ocorrencias[col_data].apply(robust_date_parse)
        df_ocorrencias['Mes_Ano'] = df_ocorrencias['Data'].dt.strftime('%m/%Y').fillna('Desconhecido')
        
        # Processar Erros Fora
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
        df_ocorrencias = df_ocorrencias.sort_values('Data', ascending=False)
        df_ocorrencias_fora = df_ocorrencias_fora.sort_values('Data', ascending=False)
        df_folha = df_folha.sort_values('Data', ascending=False) if not df_folha.empty else df_folha

        # 📌 MANTENDO OS DADOS BRUTOS E CRIANDO O ÍNDICE DE PROLIXIDADE
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

# ---------------- HEADER PRINCIPAL ----------------
st.markdown("""
    <div style="background: white; padding: 24px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.1); display: flex; align-items: center; gap: 24px; margin-bottom: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <div style="background: #8B5CF6; padding: 14px; border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <path d="M23 7l-7 5 7 5V7z"></path>
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
            </svg>
        </div>
        <div>
            <h1 style="margin: 0; font-size: 2rem; font-weight: 800; color: #1E293B; font-family: 'Outfit', sans-serif;">Painel Gerencial - Setor de Edição de Vídeos</h1>
            <p style="margin: 0; color: #334155; font-size: 1rem; font-weight: 600;">Diretoria de Operações | Monitoramento de Edição</p>
        </div>
    </div>
""", unsafe_allow_html=True)

with st.spinner("Initializing FrameControl Engine..."):
    # Como a requisição para API agora precisa do client_secret, ele abrirá o navegador na 1ª vez
    raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_ranking_editores, df_prioridades = carregar_dados()
    
    if raw_ocorrencias is not None and not raw_ocorrencias.empty:
        df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_prioridades = preparar_dados(raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_prioridades)

        # ---------------- FILTRO MENSAL SIDEBAR ----------------
        # Coletar todas as datas de todas as fontes para garantir que o filtro tenha tudo
        todas_datas = []
        for df, col in [(df_ocorrencias, 'Data'), (df_ocorrencias_fora, 'Data'), (df_folha, 'Data'), (df_prioridades, '_Data')]:
            if df is not None and not df.empty and col in df.columns:
                todas_datas.extend(df[col].dropna().unique())
        
        if not todas_datas:
             st.sidebar.warning("Nenhuma data válida encontrada para filtrar.")
             filtro_label = "Todos"
        else:
            df_datas_all = pd.DataFrame({'Data': todas_datas})
            df_datas_all['Data_Base'] = df_datas_all['Data'].dt.to_period('M').dt.to_timestamp()
            
            meses_pt = {
                1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
                7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
            }
            
            datas_ordenadas = sorted(df_datas_all['Data_Base'].unique())
            meses_formatados = [f"{meses_pt[d.month]}/{d.year}" for d in datas_ordenadas]
            map_filtro = {f"{meses_pt[d.month]}/{d.year}": d.strftime('%m/%Y') for d in datas_ordenadas}

            st.sidebar.header("Filtros Visuais")
            filtro_label = st.sidebar.selectbox("Selecione o Mês:", ["Todos"] + meses_formatados)
            
            st.sidebar.divider()
            if st.sidebar.button("🔄 Atualizar Dados"):
                st.cache_data.clear()
                st.rerun()

        # Criar cópia bruta para a Central de Avisos (Não afetada pelos filtros de mês)
        df_prioridades_raw = df_prioridades.copy() if not df_prioridades.empty else pd.DataFrame()

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

        # ---------------- PREPARAÇÃO DO RANKING DE EDITORES (Sempre via Prioridades) ----------------
        df_ranking_editores = pd.DataFrame(columns=['Editor', 'Demandas'])
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
                    df_ranking_editores = df_res
            except Exception as e:
                st.error(f"Erro na agregação de editores: {e}")

        # ---------------- CÁLCULO DE MÉTRICAS (FrameControl Engine) ----------------
        total_ocorrencias_gerais = len(df_ocorrencias)
        total_fora_controle = len(df_ocorrencias_fora)
        
        # SOMA REAL DE VÍDEOS (Folha de Pagamento)
        if not df_folha.empty and '_Producao' in df_folha.columns:
            total_videos = int(df_folha['_Producao'].sum())
        else:
            total_videos = 0

        # ---------------- KPIs PRINCIPAIS (Versão Estável st.metric) ----------------
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Vídeos Produzidos", f"{total_videos:,}".replace(',', '.'))
        with col2:
            st.metric("Incidentes Totais", total_ocorrencias_gerais)
        with col3:
            st.metric("Erros Fora do Controle", total_fora_controle)
        
        st.divider()

        # ---------------- SEÇÃO 2: TIPOS DE OCORRÊNCIA E PRODUÇÃO ----------------
        col_graf_1, col_graf_2 = st.columns([1, 1])

        with col_graf_1:
            st.subheader("📊 Distribuição por Tipo de Ocorrência")
            st.caption("Foco principal dos problemas do setor.")
            
            if 'Tipo_Ocorrência' in df_ocorrencias.columns:
                contagem_tipos = df_ocorrencias['Tipo_Ocorrência'].value_counts().reset_index()
                contagem_tipos.columns = ['Categoria', 'Quantidade']
                total_ocr = contagem_tipos['Quantidade'].sum()
                
                # Criando as labels customizadas com Porcentagem
                contagem_tipos['Percentual'] = (contagem_tipos['Quantidade'] / total_ocr) * 100
                contagem_tipos['LabelText'] = contagem_tipos.apply(lambda row: f"{row['Quantidade']} ({row['Percentual']:.1f}%)", axis=1)
                
                # Lógica de cores FrameControl: Cobrança é STATUS-ERROR, outros são tons de ACCENT-SUBTLE/MUTED
                contagem_tipos['Cor'] = contagem_tipos['Categoria'].apply(lambda x: '#EF4444' if x == 'COBRANÇA DE PRAZO' else '#3F3F46')
                
                # Para Plotly manter a ordem crescente de tamanho (barras horizontais, os maiores ficam em cima)
                contagem_tipos = contagem_tipos.sort_values(by='Quantidade', ascending=True)

                fig_tipos = px.bar(contagem_tipos, x='Quantidade', y='Categoria', orientation='h',
                              text='LabelText')
                
                # Aplicando as cores diretamente nas barras
                fig_tipos.update_traces(marker_color=contagem_tipos['Cor'], textposition='outside', marker_line_width=0)
                
                fig_tipos.update_layout(
                    template="plotly_white",
                    xaxis_title="Quantidade",
                    yaxis_title="",
                    showlegend=False,
                    font_family="Inter",
                    font_color="#1E293B",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis={
                        "showgrid": True, 
                        "gridcolor": "#CBD5E1",
                        "tickfont": {"color": "#1E293B", "size": 12},
                        "title_font": {"color": "#1E293B", "size": 14, "weight": "bold"}
                    },
                    yaxis={
                        "tickfont": {"color": "#1E293B", "size": 12},
                    },
                    margin={"l": 0, "r": 40, "t": 10, "b": 40}
                )
                
                st.plotly_chart(fig_tipos, use_container_width=True)
                
                # Renderiza também a tabela crua resumida em um extensor se quiserem ver os números exatos
                with st.expander("Ver Tabela Detalhada das Categorias"):
                    tabela_resumo = contagem_tipos.sort_values(by='Quantidade', ascending=False)[['Categoria', 'Quantidade', 'Percentual']]
                    tabela_resumo['Percentual'] = tabela_resumo['Percentual'].apply(lambda x: f"{x:.1f}%")
                    st.dataframe(tabela_resumo, use_container_width=True, hide_index=True)

            else:
                 st.info("Dado não encontrado para gerar o gráfico.")

        with col_graf_2:
            st.subheader("🚀 Produção por Editor (Demandas)")
            st.caption("Baseado na aba 'Prioridades' (Dados Reais Filtráveis)")
            
            if not df_ranking_editores.empty:
                df_edit = df_ranking_editores.copy()
                
                # Excluir editores que já saíram
                EDITORES_DEMITIDOS = ['adão', 'adao', 'letícia', 'leticia', 'thiago santos']
                df_edit = df_edit[~df_edit['Editor'].str.lower().str.strip().isin(EDITORES_DEMITIDOS)]
                
                df_edit = df_edit[df_edit['Demandas'] > 0].sort_values('Demandas', ascending=True)
                
                total_demandas = df_edit['Demandas'].sum()
                if total_demandas > 0:
                    df_edit['Percentual'] = (df_edit['Demandas'] / total_demandas * 100).round(1)
                    df_edit['LabelText'] = df_edit.apply(lambda r: f"{r['Demandas']} ({r['Percentual']:.1f}%)", axis=1)
                    
                    fig2 = px.bar(df_edit, x='Demandas', y='Editor', orientation='h', text='LabelText')
                    fig2.update_traces(marker_color='#8B5CF6', textposition='outside', marker_line_width=0)
                    fig2.update_layout(
                        template="plotly_white",
                        xaxis_title="Demandas Realizadas / Pontos",
                        yaxis_title="",
                        showlegend=False,
                        font_family="Inter",
                        font_color="#1E293B",
                        xaxis={
                            "showgrid": True, 
                            "gridcolor": "#CBD5E1",
                            "tickfont": {"color": "#1E293B", "size": 11},
                            "title_font": {"color": "#1E293B", "size": 14, "weight": "bold"}
                        },
                        yaxis={
                            "tickfont": {"color": "#1E293B", "size": 11}
                        },
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        margin={"l": 0, "r": 50, "t": 10, "b": 40}
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Nenhuma demanda encontrada para este período.")
            else:
                st.info("Dados de editores não encontrados na aba Prioridades.")
                
        st.divider()
        
        # ---------------- SEÇÃO 3: OCORRÊNCIAS FORA DE CONTROLE (CRÍTICAS) ----------------
        col_fora_1, col_fora_2 = st.columns([1, 1])
        
        with col_fora_1:
            st.subheader("🚨 Erros Fora da Edição (Tipos)")
            st.caption("Problemas que impactam a edição mas vêm de fora (CS/Mento/Gravação).")
            
            if 'Tipo_Ocorrência' in df_ocorrencias_fora.columns and not df_ocorrencias_fora.empty:
                df_tipos_fora = df_ocorrencias_fora['Tipo_Ocorrência'].value_counts().reset_index()
                df_tipos_fora.columns = ['Categoria', 'Quantidade']
                total_f = df_tipos_fora['Quantidade'].sum()
                
                df_tipos_fora['Percentual'] = (df_tipos_fora['Quantidade'] / total_f * 100)
                df_tipos_fora['LabelText'] = df_tipos_fora.apply(lambda r: f"{r['Quantidade']} ({r['Percentual']:.1f}%)", axis=1)
                df_tipos_fora = df_tipos_fora.sort_values('Quantidade', ascending=True)
                
                fig3 = px.bar(df_tipos_fora, x='Quantidade', y='Categoria', orientation='h', text='LabelText')
                fig3.update_traces(marker_color='#f39c12', textposition='outside') # Laranja para diferenciar
                fig3.update_layout(
                    template="plotly_white",
                    xaxis_title="Quantidade",
                    yaxis_title="",
                    showlegend=False,
                    font_family="Inter",
                    font_color="#1E293B",
                    xaxis={
                        "showgrid": True, 
                        "gridcolor": "#CBD5E1",
                        "tickfont": {"color": "#1E293B", "size": 12},
                        "title_font": {"color": "#1E293B", "size": 14, "weight": "bold"}
                    },
                    yaxis={
                        "tickfont": {"color": "#1E293B", "size": 12}
                    },
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin={"l": 0, "r": 40, "t": 10, "b": 40}
                )
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Nenhuma ocorrência externa registrada neste período.")

        with col_fora_2:
            st.subheader("📋 Lista de Incidentes Externos")
            st.caption("Últimos registros da planilha do gerente.")
            
            if not df_ocorrencias_fora.empty:
                # Sistema de busca por Cliente
                busca_cliente = st.text_input("🔍 Buscar por Cliente", placeholder="Digite o nome do cliente...")
                
                df_filtrado_fora = df_ocorrencias_fora.copy()
                if busca_cliente:
                    # Tentar encontrar a coluna de cliente
                    col_cliente = next((c for c in df_ocorrencias_fora.columns if 'cliente' in c.lower()), None)
                    if col_cliente:
                        df_filtrado_fora = df_filtrado_fora[df_filtrado_fora[col_cliente].astype(str).str.contains(busca_cliente, case=False, na=False)]
                
                # Mostrar as colunas mais relevantes
                cols_view = [c for c in df_filtrado_fora.columns if not c.startswith('_') and c not in ['Mes_Ano', 'Data']]
                st.dataframe(df_filtrado_fora[cols_view], use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados detalhados.")
        
        st.divider()

        # ---------------- SEÇÃO 4: CENTRAL DE AVISOS (ALERTAS CRÍTICOS - FIXO) ----------------
        st.header("🔔 Central de Avisos - Gestão de Prazos")
        
        if not df_prioridades_raw.empty:
            hoje = pd.Timestamp.now().normalize()
            fim_semana = hoje + pd.Timedelta(days=(6 - hoje.weekday()))
            
            # 1. ATRASADOS (Prazo real < hoje E não entregue) - USANDO DADOS BRUTOS (FIXO)
            mask_atrasados = (
                (df_prioridades_raw['_Data'] < hoje) & 
                (df_prioridades_raw['Entregue'].str.lower() != 'entregou')
            )
            df_atrasados = df_prioridades_raw[mask_atrasados].copy()
            
            # 2. NA SEMANA (hoje <= Prazo real <= domingo E não entregue) - USANDO DADOS BRUTOS (FIXO)
            mask_semana = (
                (df_prioridades_raw['_Data'] >= hoje) & 
                (df_prioridades_raw['_Data'] <= fim_semana) &
                (df_prioridades_raw['Entregue'].str.lower() != 'entregou')
            )
            df_semana = df_prioridades_raw[mask_semana].copy()
            
            cols_avisos = ['Nome', 'Editor', 'Prazo real', 'Entregue', 'Bloco']

            # Exibir Atrasados
            with st.container():
                st.markdown("""
                    <div style="background: #FFF1F2; border-left: 4px solid #F43F5E; padding: 1.25rem; border-radius: 8px; margin-bottom: 20px;">
                        <h4 style="margin:0; color: #9F1239; font-size: 1rem; font-weight: 700;">🚨 Atrasados</h4>
                        <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: #BE123C; opacity: 0.8;">Ação imediata requerida para estas demandas.</p>
                    </div>
                """, unsafe_allow_html=True)
                
                if not df_atrasados.empty:
                    st.dataframe(df_atrasados[cols_avisos].sort_values('Prazo real'), use_container_width=True, hide_index=True)
                else:
                    st.success("Tudo em dia! Sem pendências atrasadas.")

            st.write("") 

            # Exibir Na Semana
            with st.container():
                st.markdown("""
                    <div style="background: #F5F3FF; border-left: 4px solid #8B5CF6; padding: 1.25rem; border-radius: 8px; margin-bottom: 20px;">
                        <h4 style="margin:0; color: #5B21B6; font-size: 1rem; font-weight: 700;">📅 Entregas desta Semana</h4>
                        <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: #6D28D9; opacity: 0.8;">Acompanhamento da fila de render desta semana.</p>
                    </div>
                """, unsafe_allow_html=True)
                
                if not df_semana.empty:
                    st.dataframe(df_semana[cols_avisos].sort_values('Prazo real'), use_container_width=True, hide_index=True)
                else:
                    st.info("Fila vazia. Nenhuma entrega prevista para este ciclo.")
        else:
            st.info("Dados de Prioridades não disponíveis para gerar avisos.")

    else:
        st.warning("Aguardando carregamento de dados / Falha na autenticação.")
