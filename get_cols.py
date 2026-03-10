from dashboard import carregar_dados
import pandas as pd

# carregar_dados returns: df_ajustes, df_folha, df_ocorrencias, df_ocorrencias_fora, df_ranking_editores, df_prioridades
res = carregar_dados()
print(f"Unpacked {len(res)} dataframes")

df_ajustes = res[0]

print("--- AJUSTES ---")
print("Colunas:", df_ajustes.columns.tolist())
print(df_ajustes.head(5).to_dict('records'))
