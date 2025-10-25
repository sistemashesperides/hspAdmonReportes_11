# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.admin.routes import login_required # Reutilizar decorador de login
from app.admin.services import get_daily_summary_config, update_daily_summary_config, get_all_connections
from core.scheduler_service import update_daily_summary_job # Para actualizar tarea al guardar config
from app.daily_summary.services import get_daily_summary_data # Función para obtener datos
from jinja2 import Environment, FileSystemLoader # Para renderizar preview
import os
from datetime import datetime
from flask import current_app # Para acceder a config['PROJECT_ROOT'] en preview
import traceback # Importar para manejo de errores detallado
import base64 # <-- AÑADIR ESTA IMPORTACIÓN

# Crear Blueprint para este módulo
daily_summary_bp = Blueprint('daily_summary', __name__,
                             url_prefix='/admin/daily-summary',
                             template_folder='../../templates/daily_summary')

# --- Ruta para la página de Configuración del Resumen Diario ---
@daily_summary_bp.route('/', methods=['GET', 'POST'])
@login_required
def config_page():
    if request.method == 'POST':
        try:
            update_daily_summary_config(request.form)
            # Actualizar la tarea programada con la nueva configuración
            update_daily_summary_job()
            flash('Configuración del resumen diario guardada correctamente.', 'success')
        except Exception as e:
             flash(f'Error al guardar la configuración: {str(e)}', 'danger')
        # Siempre redirigir a la misma página después de POST para evitar reenvío de formulario
        return redirect(url_for('daily_summary.config_page'))

    # Para el método GET, cargar la configuración actual y las conexiones disponibles
    config = get_daily_summary_config()
    connections = get_all_connections()
    # Asegurarse que sql_query exista en el diccionario, si no, poner vacío
    if 'sql_query' not in config:
        config['sql_query'] = '' # O cargar el default si prefieres, aunque init_db ya lo hace
    return render_template('config.html', config=config, connections=connections)

# --- Ruta API para Previsualizar el Correo ---
@daily_summary_bp.route('/preview', methods=['POST'])
@login_required
def preview():
    data = request.json
    connection_id = data.get('connection_id')
    sql_query = data.get('sql_query')

    # Validar entrada básica
    if not connection_id or not sql_query:
        return jsonify({"error": "Faltan parámetros: connection_id o sql_query"}), 400

    try:
        # Obtener los datos usando la consulta y conexión proporcionadas
        # Esta función ahora devuelve (True, data_dict) o (False, {'error': msg, 'debug_log': [...]})
        success, result_data = get_daily_summary_data(connection_id, sql_query)

        if not success:
            # Si falló, result_data contiene el error y el log
            # Devolvemos este diccionario como JSON con estado 500 (Error Interno del Servidor)
            return jsonify(result_data), 500

        # Si tuvo éxito, result_data contiene los datos del resumen
        summary_data = result_data
        project_root = current_app.config.get('PROJECT_ROOT', os.path.dirname(current_app.root_path))
        template_loader = FileSystemLoader(searchpath=os.path.join(project_root, 'templates', 'daily_summary'))
        env = Environment(loader=template_loader)

        # Añadir filtro de formato de fecha si no existe globalmente (mejor hacerlo global en create_app)
        if 'date_format' not in env.filters:
             def date_format_filter(value, format='%d/%m/%Y'):
                 if isinstance(value, datetime): return value.strftime(format)
                 # Añadir manejo básico si el valor ya es string (ej. MesAno)
                 if isinstance(value, str): return value # Asumiendo que ya está formateado
                 return value # Devolver otros tipos tal cual
             env.filters['date_format'] = date_format_filter
        
        # Añadir filtro de formato numérico (ej: %.2f) si no existe globalmente
        if 'currency_format' not in env.filters:
             def currency_format_filter(value, format_spec="%.2f"):
                 try:
                     # Intentar convertir a float y formatear
                     num_value = float(value)
                     return format_spec % num_value
                 except (ValueError, TypeError):
                     # Si no es un número válido, devolver 0.00 formateado o el valor original
                     try: return format_spec % 0.0
                     except: return value # Fallback si format_spec es inválido
             env.filters['currency_format'] = currency_format_filter


        template = env.get_template('email_body.html')

        # --- AJUSTE CLAVE: Convertir bytes de imagen a Base64 para preview ---
        chart_30_src = None
        if summary_data.get('chart_30_days_bytes'):
            try:
                # Convertir los bytes crudos a una cadena Base64
                img_base64 = base64.b64encode(summary_data['chart_30_days_bytes']).decode('utf-8')
                # Crear el Data URI que el HTML puede mostrar
                chart_30_src = f"data:image/png;base64,{img_base64}"
            except Exception as e:
                print(f"Error convirtiendo gráfico 30 días a base64 para preview: {e}")

        chart_12_src = None
        if summary_data.get('chart_12_months_bytes'):
             try:
                # Convertir los bytes crudos a una cadena Base64
                img_base64 = base64.b64encode(summary_data['chart_12_months_bytes']).decode('utf-8')
                # Crear el Data URI que el HTML puede mostrar
                chart_12_src = f"data:image/png;base64,{img_base64}"
             except Exception as e:
                print(f"Error convirtiendo gráfico 12 meses a base64 para preview: {e}")
        
        # -------------------------------------------------------------------

        # Renderizar el template pasando las fuentes de imagen Base64
        # Asumimos que tu template email_body.html usa las variables:
        # <img src="{{ chart_30_src or ('cid:' + cid_chart_30) }}">
        # <img src="{{ chart_12_src or ('cid:' + cid_chart_12) }}">
        # De esta forma, usa chart_30_src si existe (preview), o recurre al cid para el email final.
        html_preview = template.render(
            data=summary_data,
            today_date=datetime.now().strftime('%d/%m/%Y'),
            chart_30_src=chart_30_src, # Variable con el Base64 Data URI
            chart_12_src=chart_12_src, # Variable con el Base64 Data URI
            cid_chart_30=None,         # Lo ponemos a None en preview para forzar el uso de chart_30_src
            cid_chart_12=None          # Lo ponemos a None en preview para forzar el uso de chart_12_src
        )

        # Devolver el HTML renderizado directamente con estado 200 OK
        return html_preview

    except Exception as e:
        # Capturar cualquier otro error inesperado (ej: durante el renderizado de Jinja)
        print(f"Error inesperado en ruta preview: {e}")
        traceback.print_exc() # Imprimir traceback completo en consola del servidor
        # Devolver el error como JSON para que el frontend lo muestre
        return jsonify({"error": f"Error inesperado al generar previsualización: {str(e)}"}), 500
