import os
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for, flash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecretkey'  # Necessário para flash()

# Cria pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def consolidar_dados(lista_csv, lista_excel):
    df_csv = pd.concat([
        pd.read_csv(file, sep=';', encoding='utf-8')
        for file in lista_csv
    ], ignore_index=True)

    df_excel = pd.concat([
        pd.read_excel(file, sheet_name='Historico_adiantamento', engine='openpyxl')
        for file in lista_excel
    ], ignore_index=True)

    df_csv['valor'] = df_csv['valor'].str.replace(',', '.').astype(float)
    consolidado_ifood = df_csv.groupby('id_da_pessoa_entregadora').agg({
        'recebedor': 'first',
        'praca': 'first',
        'subpraca': 'first',
        'valor': 'sum'
    }).reset_index().rename(columns={
        'id_da_pessoa_entregadora': 'uuid',
        'recebedor': 'nome',
        'valor': 'valor_ifood'
    })

    df_excel['valores'] = pd.to_numeric(df_excel['valores'], errors='coerce')
    consolidado_adiantamento = df_excel.groupby('idEntregador')['valores'].sum().reset_index()
    consolidado_adiantamento = consolidado_adiantamento.rename(columns={
        'idEntregador': 'uuid',
        'valores': 'adiantamentos_trampay'
    })

    resultado = pd.merge(consolidado_ifood, consolidado_adiantamento, on='uuid', how='left')
    resultado['adiantamentos_trampay'] = resultado['adiantamentos_trampay'].fillna(0)
    resultado['total'] = (resultado['valor_ifood'] - resultado['adiantamentos_trampay']).round(2)
    return resultado

def consolidar_performance(lista_csv):
    import numpy as np
    import openpyxl

    df = pd.concat([
        pd.read_csv(file, sep=';', encoding='utf-8')
        for file in lista_csv
    ], ignore_index=True)

    # Valida colunas necessárias
    obrigatorias = ['id_da_pessoa_entregadora', 'pessoa_entregadora', 'data_do_periodo']
    for col in obrigatorias:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    # Converte e prepara
    df['data_do_periodo'] = pd.to_datetime(df['data_do_periodo']).dt.date
    df['id_da_pessoa_entregadora'] = df['id_da_pessoa_entregadora'].astype(str)
    df['pessoa_entregadora'] = df['pessoa_entregadora'].astype(str)

    # Remove colunas desnecessárias
    colunas_remover = [
        'tag', 'duracao_do_periodo', 'tempo_disponivel_absoluto',
        'origem', 'tempo_disponivel_escalado', 'numero_minimo_de_entregadores_regulares_na_escala','numero_de_pedidos_aceitos_e_concluidos'
    ]
    df = df.drop(columns=[col for col in colunas_remover if col in df.columns], errors='ignore')

    # Colunas numéricas
    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()

    # --- ABA 1: Consolidado geral por entregador ---
    geral = df.groupby(['id_da_pessoa_entregadora', 'pessoa_entregadora'], as_index=False)[numeric_cols].sum()

    # Caminho de saída
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultado_consolidado.xlsx')

    # --- Criação do Excel com múltiplas abas ---
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        # Aba principal
        geral.to_excel(writer, sheet_name='Consolidado Geral', index=False)

        # Abas por dia: 1 linha por entregador consolidado no dia
        for data in sorted(df['data_do_periodo'].unique()):
            df_dia = df[df['data_do_periodo'] == data]
            dia_agrupado = df_dia.groupby(['id_da_pessoa_entregadora', 'pessoa_entregadora'], as_index=False)[numeric_cols].sum()
            dia_agrupado.insert(0, 'data_do_periodo', data)
            dia_agrupado.to_excel(writer, sheet_name=str(data)[:31], index=False)

    return path




@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        tipo_relatorio = request.form.get('tipo_relatorio')

        if tipo_relatorio == 'financeiro':
            csv_files = request.files.getlist('csv_file')
            excel_files = request.files.getlist('excel_file')
            if not csv_files:
                flash("⚠️ Envie pelo menos 1 arquivo CSV do iFood.")
                return redirect(url_for('index'))
            resultado = consolidar_dados(csv_files, excel_files)

        elif tipo_relatorio == 'performance':
            csv_files = request.files.getlist('csv_file_perf')
            if not csv_files:
                flash("⚠️ Envie pelo menos 1 arquivo CSV de performance.")
                return redirect(url_for('index'))

            resultado_path = consolidar_performance(csv_files)
            flash('✅ Arquivo de performance gerado com abas por dia!')
            return redirect(url_for('index'))


        else:
            flash("⚠️ Selecione um tipo de relatório.")
            return redirect(url_for('index'))

        resultado_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultado_consolidado.xlsx')
        resultado.to_excel(resultado_path, index=False)
        flash('✅ Arquivo gerado com sucesso!')
        return redirect(url_for('index'))

    return render_template('index.html')

@app.route('/download')
def download_resultado():
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultado_consolidado.xlsx')
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
