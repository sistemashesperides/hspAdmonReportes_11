import pandas as pd
import os
import io
import base64
from flask import current_app
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import matplotlib.pyplot as plt

from app.admin.services import get_design_by_id, execute_repository_query

def generate_report(design_id, filter_values=None):
    """Genera un reporte, incluyendo grupos, totales y gráficos."""
    design = get_design_by_id(design_id)
    if not design: raise ValueError("Diseño no encontrado")

    # 1. Obtener y preparar datos
    params = [filter_values.get(f['name']) for f in design['config'].get('filters', [])] if filter_values else []
    success, message, raw_data = execute_repository_query(design['repository_id'], params)
    if not success: raise ConnectionError(f"Error al obtener datos: {message}")
    df = pd.DataFrame(raw_data['data'], columns=raw_data['columns'])
    if df.empty: raise ValueError("La consulta no devolvió datos.")

    # Convertir columnas de total a numérico (si es posible)
    config = design['config']
    total_fields_original = config.get('total_fields', [])
    for col in total_fields_original:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce') # 'coerce' convierte errores en NaN

    # 2. Procesar visibilidad, orden y etiquetas (igual que antes)
    visible_fields_config = config.get('fields', {}).get('details', {})
    visible_fields = [f for f, details in visible_fields_config.items() if details.get('visible', True)]
    existing_visible_fields = [f for f in visible_fields if f in df.columns]
    if not existing_visible_fields: raise ValueError("Ningún campo visible existe.")
    df = df[existing_visible_fields]
    ordered_fields = [f for f in config.get('fields', {}).get('order', []) if f in existing_visible_fields]
    df = df[ordered_fields]
    labels = {f: details.get('label', f) for f, details in visible_fields_config.items()}
    df.rename(columns=labels, inplace=True)

    # Renombrar también los campos de totalizar según las etiquetas
    total_fields_labeled = [labels.get(f, f) for f in total_fields_original if labels.get(f, f) in df.columns]

    # 3. Agrupar y calcular subtotales (si se configuró)
    grouped_data = None
    group_by_field_labeled = labels.get(config.get('group_by_field'))
    
    if group_by_field_labeled and group_by_field_labeled in df.columns:
        grouped = df.groupby(group_by_field_labeled)
        grouped_data = {}
        for name, group in grouped:
            subtotals = group[total_fields_labeled].sum() if total_fields_labeled else None
            grouped_data[name] = {
                'rows': group.to_dict(orient='records'),
                'subtotals': subtotals.to_dict() if subtotals is not None else None
            }
            
    # 4. Calcular totales generales (si se configuró)
    grand_totals = df[total_fields_labeled].sum().to_dict() if total_fields_labeled else None

    # 5. Generar gráfico (si se configuró)
    chart_image_base64 = None
    chart_config = config.get('chart', {})
    chart_type = chart_config.get('type')
    x_axis_original = chart_config.get('x_axis')
    y_axis_original = chart_config.get('y_axis')
    
    # Usar etiquetas si existen
    x_axis_labeled = labels.get(x_axis_original)
    y_axis_labeled = labels.get(y_axis_original)

    if chart_type and x_axis_labeled in df.columns and y_axis_labeled in df.columns:
        chart_image_base64 = generate_chart_base64(df, chart_type, x_axis_labeled, y_axis_labeled)

    # 6. Preparar datos finales para la plantilla
    template_data = {
        'title': design['name'],
        'columns': df.columns.tolist(), # Columnas ya renombradas
        'grouped_data': grouped_data, # Datos agrupados o None
        'data_rows': df.to_dict(orient='records') if not grouped_data else None, # Datos planos si no hay grupos
        'group_by_field': group_by_field_labeled,
        'total_fields': total_fields_labeled,
        'grand_totals': grand_totals,
        'chart_image': chart_image_base64,
        'branding': config.get('branding', {}),
        'logo_path': get_logo_path(config)
    }

    # 7. Generar output
    safe_filename = "".join(c for c in design['name'] if c.isalnum() or c in (' ', '_')).rstrip()
    output_format = design['output_format']
    extension = output_format.split('_')[0]
    filename = f"{safe_filename.replace(' ', '_')}.{extension}"
    
    template_map = {
        'pdf': 'report_template.html',
        'html_email': 'email_template.html'
    }
    template_name = template_map.get(output_format)
    if not template_name: raise NotImplementedError(f"Formato {output_format} no implementado")

    html_string = render_template_from_file(template_name, template_data)

    if output_format == 'pdf':
        pdf_bytes = HTML(string=html_string).write_pdf()
        return pdf_bytes, 'application/pdf', filename
    elif output_format == 'html_email':
        return html_string, 'text/html', filename
    else: # Futuro: Excel
        raise NotImplementedError(f"Formato {output_format} no implementado")

def generate_chart_base64(df, chart_type, x_col, y_col):
    """Genera un gráfico con Matplotlib y lo devuelve como imagen base64."""
    try:
        # Asegurarse de que la columna Y sea numérica
        df[y_col] = pd.to_numeric(df[y_col], errors='coerce').fillna(0)
        
        # Agrupar si hay muchos datos en X (ej. tomar top 10)
        if df[x_col].nunique() > 15:
            plot_data = df.groupby(x_col)[y_col].sum().nlargest(10)
        else:
             plot_data = df.groupby(x_col)[y_col].sum()

        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(8, 4)) # Tamaño ajustado para reportes

        if chart_type == 'bar':
            plot_data.plot(kind='bar', ax=ax)
            plt.ylabel(y_col)
        elif chart_type == 'pie':
             # Los gráficos de torta a veces necesitan ajustes si hay muchos valores pequeños
            plot_data.plot(kind='pie', ax=ax, autopct='%1.1f%%', startangle=90, legend=False)
            plt.ylabel('') # Ocultar etiqueta Y en tortas
        elif chart_type == 'line':
            plot_data.plot(kind='line', ax=ax, marker='o')
            plt.ylabel(y_col)
        
        plt.title(f'{y_col} por {x_col}')
        plt.xlabel(x_col)
        plt.xticks(rotation=45, ha='right') # Rotar etiquetas del eje X si son largas
        plt.tight_layout() # Ajustar márgenes

        # Guardar en memoria como PNG
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig) # Liberar memoria
        buf.seek(0)
        
        # Codificar en base64 para embeber en HTML
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
        
    except Exception as e:
        print(f"Error generando gráfico: {e}")
        return None # Devolver None si falla la generación

# --- Funciones auxiliares (render_template_from_file, get_logo_path) sin cambios ---
def render_template_from_file(template_name, context):
    project_root = current_app.config.get('PROJECT_ROOT', os.path.dirname(current_app.root_path))
    searchpath = os.path.join(project_root, 'templates', 'reports')
    template_loader = FileSystemLoader(searchpath=searchpath)
    env = Environment(loader=template_loader)
    try:
        template = env.get_template(template_name)
    except Exception as e:
        raise FileNotFoundError(f"Plantilla '{template_name}' no encontrada en '{searchpath}'. Error: {e}")
    # Añadir 'zip' al entorno para usarlo en la plantilla
    env.globals['zip'] = zip
    return template.render(context)

def get_logo_path(config):
    logo_filename = config.get('branding', {}).get('logo_filename')
    if not logo_filename: return None
    project_root = current_app.config.get('PROJECT_ROOT', os.path.dirname(current_app.root_path))
    logo_path = os.path.join(project_root, 'uploads', logo_filename)
    return f'file:///{logo_path}' if os.path.exists(logo_path) else None