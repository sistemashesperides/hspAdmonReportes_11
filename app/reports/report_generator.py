import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generar_reporte_ventas(df: pd.DataFrame, formato: str = 'pdf'):
    """
    Genera un reporte avanzado de ventas con totales, subtotales y un gráfico.
    """
    if df.empty:
        print("No hay datos para generar el reporte.")
        return None

    # --- 1. Cálculos de Totales y Subtotales ---
    # Subtotal por cliente
    subtotales = df.groupby('Cliente')['TotalVenta'].sum().reset_index()
    # Total general
    total_general = df['TotalVenta'].sum()

    # --- 2. Generación de Gráfico ---
    plt.style.use('ggplot')
    plt.figure(figsize=(10, 6))
    subtotales.sort_values('TotalVenta', ascending=False).head(10).plot(
        kind='bar', x='Cliente', y='TotalVenta', legend=False
    )
    plt.title('Top 10 Clientes por Venta')
    plt.ylabel('Total Venta (€)')
    plt.xlabel('Cliente')
    plt.tight_layout()
    
    # Guardar gráfico como imagen
    os.makedirs('temp_reports', exist_ok=True)
    grafico_path = os.path.join('temp_reports', 'grafico_ventas.png')
    plt.savefig(grafico_path)
    plt.close()

    # --- 3. Generación de Archivo ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if formato == 'pdf':
        # Renderizar HTML con Jinja2 y luego convertir a PDF
        env = Environment(loader=FileSystemLoader('templates/'))
        template = env.get_template('report_template.html')
        
        html_out = template.render(
            tabla_datos=df.to_html(classes='table table-striped', index=False),
            tabla_subtotales=subtotales.to_html(classes='table', index=False),
            total_general=f"{total_general:,.2f} €",
            grafico_path=f"file:///{os.path.abspath(grafico_path)}",
            fecha_reporte=datetime.now().strftime("%d/%m/%Y")
        )
        
        ruta_salida = f"temp_reports/reporte_ventas_{timestamp}.pdf"
        HTML(string=html_out).write_pdf(ruta_salida)
        return ruta_salida

    elif formato == 'excel':
        # Generar un Excel con varias hojas y el gráfico
        ruta_salida = f"temp_reports/reporte_ventas_{timestamp}.xlsx"
        with pd.ExcelWriter(ruta_salida, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Detalle_Ventas', index=False)
            subtotales.to_excel(writer, sheet_name='Resumen_por_Cliente', index=False)
            
            # Añadir el gráfico a una hoja
            workbook = writer.book
            worksheet = workbook.add_worksheet('Gráfico')
            worksheet.insert_image('B2', grafico_path)
            
        return ruta_salida