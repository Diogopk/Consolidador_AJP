import os
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'supersecretkey'  # Necessário para flash()

# Cria pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def consolidar_dados(lista_csv, lista_excel):
    # Concatena todos os CSVs
    df_csv = pd.concat([
        pd.read_csv(file, sep=';', encoding='utf-8')
        for file in lista_csv
    ], ignore_index=True)

    # Concatena todos os Excels
    df_excel = pd.concat([
        pd.read_excel(file, sheet_name='Historico_adiantamento', engine='openpyxl')
        for file in lista_excel
    ], ignore_index=True)

    # Concatena todos os Excels
    df_excel = pd.concat([
        pd.read_excel(file, sheet_name='Historico_adiantamento', engine='openpyxl')
        for file in lista_excel
    ], ignore_index=True)

    # Processamento dos dados
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        csv_files = request.files.getlist('csv_file')
        excel_files = request.files.getlist('excel_file')

        if csv_files and excel_files:
            resultado = consolidar_dados(csv_files, excel_files)
            resultado_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultado_consolidado.xlsx')
            resultado.to_excel(resultado_path, index=False)

            flash('✅ Arquivo gerado com sucesso!')
            return redirect(url_for('index'))

        else:
            flash('⚠️ Por favor, envie todos os arquivos necessários.')

    return render_template('index.html')

@app.route('/download')
def download_resultado():
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultado_consolidado.xlsx')
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
