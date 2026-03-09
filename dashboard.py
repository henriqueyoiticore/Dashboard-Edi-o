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
# CONFIGURAÇÃO INICIAL DA PÁGINA
# =====================================================================
st.set_page_config(
    page_title="Dashboard de Monitoramento | Edição Vídeos",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 0rem; }
        .stMetric { border: 1px solid #333; padding: 10px; border-radius: 5px; box-shadow: 1px 1px 5px rgba(0,0,0,0.1); }
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

def get_sheet_data(service, spreadsheet_id, range_name):
    """Puxa os dados de uma aba específica da planilha e converte para Pandas DataFrame."""
    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            return pd.DataFrame()
            
        # Transforma os dados retornados em um DataFrame do Pandas usando a 1ª linha como cabeçalho
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception as e:
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
    df_ajustes = get_sheet_data(service, ID_AJUSTES, 'A:Z')
    df_folha = get_sheet_data(service, ID_FOLHA, 'A:Z')
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
        
        # Processar Folha
        col_data_folha = find_date_col(df_folha)
        df_folha['Data'] = df_folha[col_data_folha].apply(robust_date_parse)
        df_folha['Mes_Ano'] = df_folha['Data'].dt.strftime('%m/%Y').fillna('Desconhecido')

        # Processar Prioridades (Aba Central)
        if not df_prioridades.empty:
            col_data_pr = find_date_col(df_prioridades)
            df_prioridades['_Data'] = df_prioridades[col_data_pr].apply(robust_date_parse)
            df_prioridades['_Mes_Ano'] = df_prioridades['_Data'].dt.strftime('%m/%Y').fillna('Desconhecido')

        # 📌 MANTENDO OS DADOS BRUTOS E CRIANDO O ÍNDICE DE PROLIXIDADE
        col_descricao = next((col for col in df_ocorrencias.columns if any(k in col.lower() for k in ['detalhamento', 'descri', 'ocorrencia'])), df_ocorrencias.columns[3] if len(df_ocorrencias.columns) > 3 else df_ocorrencias.columns[-1])
        df_ocorrencias['Texto_Bruto'] = df_ocorrencias[col_descricao].fillna("Sem descrição")
        
        # 📌 NOVA CATEGORIZAÇÃO DE OCORRÊNCIAS
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

    except Exception as e:
        st.warning(f"Aviso no tratamento dos dados: {e}")
        
    return df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_prioridades

# =====================================================================
# INTERFACE DO DASHBOARD
# =====================================================================

st.title("📊 Painel Gerencial - Setor de Edição de Vídeos")

with st.spinner("Conectando via OAuth e Processando Dados..."):
    # Como a requisição para API agora precisa do client_secret, ele abrirá o navegador na 1ª vez
    raw_ajustes, raw_folha, raw_ocorrencias, raw_ocorrencias_fora, df_ranking_editores, df_prioridades = carregar_dados()
    
    if not raw_ocorrencias.empty:
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

        if filtro_label != "Todos":
            filtro_mes = map_filtro[filtro_label]
            df_ocorrencias = df_ocorrencias[df_ocorrencias['Mes_Ano'] == filtro_mes] if not df_ocorrencias.empty else df_ocorrencias
            df_ocorrencias_fora = df_ocorrencias_fora[df_ocorrencias_fora['Mes_Ano'] == filtro_mes]
            df_folha = df_folha[df_folha['Mes_Ano'] == filtro_mes] if not df_folha.empty else df_folha
            df_prioridades = df_prioridades[df_prioridades['_Mes_Ano'] == filtro_mes] if not df_prioridades.empty else df_prioridades

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

        # ---------------- KPIs PRINCIPAIS ----------------
        total_ocorrencias_gerais = len(df_ocorrencias)
        total_fora_controle = len(df_ocorrencias_fora)
        total_videos = len(df_folha) 
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Videos Produzidos", total_videos)
        col2.metric("Ocorrências Totais", total_ocorrencias_gerais)
        col3.metric("Erros Fora do Controle", total_fora_controle, delta_color="inverse")
        
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
                
                # Lógica de cores: Cobrança de prazo é VERMELHO, Todo o resto é AZUL
                contagem_tipos['Cor'] = contagem_tipos['Categoria'].apply(lambda x: '#e74c3c' if x == 'COBRANÇA DE PRAZO' else '#3498db')
                
                # Para Plotly manter a ordem crescente de tamanho (barras horizontais, os maiores ficam em cima)
                contagem_tipos = contagem_tipos.sort_values(by='Quantidade', ascending=True)

                fig_tipos = px.bar(contagem_tipos, x='Quantidade', y='Categoria', orientation='h',
                              text='LabelText')
                
                # Aplicando as cores diretamente nas barras
                fig_tipos.update_traces(marker_color=contagem_tipos['Cor'], textposition='outside')
                
                fig_tipos.update_layout(
                    xaxis_title="Quantidade de Ocorrências",
                    yaxis_title="",
                    showlegend=False,
                    xaxis={"showgrid": True, "gridcolor": "#444"},
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin={"l": 0, "r": 0, "t": 10, "b": 10}
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
                    fig2.update_traces(marker_color='#27ae60', textposition='outside')
                    fig2.update_layout(
                        xaxis_title="Demandas Realizadas",
                        yaxis_title="",
                        showlegend=False,
                        xaxis={"showgrid": True, "gridcolor": "#444"},
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        margin={"l": 0, "r": 0, "t": 10, "b": 10}
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Nenhuma demanda encontrada para este período.")
            else:
                st.info("Dados de editores não encontrados na aba Prioridades.")
                
        st.divider()
        
        # ---------------- SEÇÃO 3: OCORRÊNCIAS FORA DE CONTROLE (CRÍTICAS) ----------------
        st.subheader("🚨 Ocorrências Fora de Controle")
        st.caption("Estatísticas baseadas na planilha do Gerente (Erros fora do setor de Edição)")
        if len(df_ocorrencias_fora) > 0:
            st.dataframe(df_ocorrencias_fora.head(10), use_container_width=True)
        else:
            st.info("Sem ocorrências fora de controle registradas neste período.")
    else:
        st.warning("Aguardando carregamento de dados / Falha na autenticação.")
