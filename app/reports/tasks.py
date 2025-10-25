# -*- coding: utf-8 -*-
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import os

from app.admin.services import get_settings as get_smtp_config, log_email_sent, get_daily_summary_config
from app.utils.email_sender import send_email
from app.daily_summary.services import get_daily_summary_data

def execute_scheduled_report(design_id):
    """Tarea programada para reportes genéricos (no el resumen diario)."""
    # Importar scheduler aquí para tener acceso a app.app_context()
    from core.scheduler_service import scheduler
    from app.admin.services import get_design_by_id # Importar get_design_by_id aquí
    from app.reports.generator_service import generate_report # Importar generate_report aquí

    with scheduler.app.app_context():
        report_name = f"Reporte ID {design_id}"
        recipients_str = "N/A"
        
        try:
            print(f"[{datetime.now()}] Iniciando trabajo programado para el reporte ID: {design_id}")
            
            design = get_design_by_id(design_id)
            smtp_config = get_smtp_config()

            if not design:
                print(f"  -> OMITIDO: El diseño de reporte con ID {design_id} ya no existe.")
                # No registramos esto como error necesariamente
                return

            report_name = design['name']
            recipients_str = f"A: {design.get('email_to', '')} | CC: {design.get('email_cc', '')}"

            # Validaciones
            if not smtp_config.get('smtp_server'):
                raise ValueError("El servidor SMTP no está configurado.")
            if not design.get('email_to'):
                print(f"  -> OMITIDO: El reporte '{report_name}' no tiene destinatarios.")
                log_email_sent(report_name, recipients_str, "Omitido", "Sin destinatarios")
                return

            # 1. Generar el reporte (puede ser PDF, HTML, etc.)
            # Nota: generate_report ahora podría necesitar manejar CIDs si genera HTML con gráficos
            # Por ahora, asumimos que devuelve bytes para adjunto o HTML simple
            output, mimetype, filename = generate_report(design_id, filter_values=None) # Asume sin filtros para tareas programadas por ahora

            # 2. Preparar datos del correo
            subject = f"Reporte Programado: {report_name} - {datetime.now().strftime('%Y-%m-%d')}"
            body = "Hola,\n\nSe adjunta el reporte generado automáticamente.\n\nSaludos."
            attachment = None
            is_html_body = False
            images_to_embed = [] # Lista para imágenes CID

            if design['output_format'] == 'html_email':
                body = output
                is_html_body = True
                # Si este HTML incluye gráficos, necesitaríamos extraerlos aquí
                # y añadirlos a images_to_embed. Simplificando por ahora.
            else: # PDF, XLSX, etc. se adjuntan
                attachment = (filename, mimetype, output)

            # 3. Enviar correo
            send_email(
                smtp_config=smtp_config,
                recipients=[email.strip() for email in design.get('email_to', '').split(',') if email.strip()],
                cc=[email.strip() for email in design.get('email_cc', '').split(',') if email.strip()],
                subject=subject,
                body=body,
                is_html=is_html_body,
                attachment=attachment,
                images=images_to_embed # Pasar lista de imágenes (vacía por ahora para reportes genéricos)
            )

            log_email_sent(report_name, recipients_str, "Enviado")
            print(f"  -> ÉXITO: Reporte '{report_name}' enviado y registrado.")

        except Exception as e:
            error_message = str(e)
            log_email_sent(report_name, recipients_str, "Fallido", error_message)
            print(f"  -> ERROR al procesar el reporte '{report_name}': {error_message}")


# --- Tarea específica para el Resumen Diario (Usa Imágenes CID) ---
def send_daily_summary_email_task():
    """Tarea que se ejecuta diariamente para enviar el resumen con gráficos embebidos."""
    # Importar scheduler aquí
    from core.scheduler_service import scheduler

    with scheduler.app.app_context():
        config = get_daily_summary_config()
        smtp_config = get_smtp_config()

        report_name = "Resumen Diario Ventas" # Nombre por defecto para logging
        recipients_str = config.get('recipients', '')

        try:
            # --- Validaciones ---
            if not config.get('is_enabled'):
                print(f"[{datetime.now()}] Resumen diario OMITIDO (deshabilitado).")
                return
            if not config.get('connection_id'): raise ValueError("Conexión BBDD no configurada.")
            if not recipients_str: raise ValueError("Destinatarios no configurados.")
            if not smtp_config or not smtp_config.get('smtp_server') or not smtp_config.get('smtp_user'):
                raise ValueError("Servidor SMTP no configurado.")
            sql_query = config.get('sql_query')
            if not sql_query: raise ValueError("Consulta SQL no configurada.")

            print(f"[{datetime.now()}] Iniciando Resumen Diario...")

            # --- Obtener Datos (incluye bytes de gráficos) ---
            success, data = get_daily_summary_data(config['connection_id'], sql_query)
            if not success: raise ValueError(f"Fallo al obtener datos: {data.get('error', 'Error desconocido')}")

            # --- Preparar Imágenes para Embeber ---
            images_to_embed = []
            chart_30_bytes = data.get('chart_30_days_bytes')
            chart_12_bytes = data.get('chart_12_months_bytes')
            if chart_30_bytes:
                images_to_embed.append(('chart_30_days_id', chart_30_bytes)) # (cid, bytes)
            if chart_12_bytes:
                images_to_embed.append(('chart_12_months_id', chart_12_bytes))

            # --- Renderizar Plantilla HTML ---
            project_root = scheduler.app.config.get('PROJECT_ROOT', os.path.dirname(scheduler.app.root_path))
            template_loader = FileSystemLoader(searchpath=os.path.join(project_root, 'templates', 'daily_summary'))
            env = Environment(loader=template_loader)
            # (Añadir filtro date_format si es necesario)
            template = env.get_template('email_body.html')
            # Pasar los CIDs a la plantilla para que los use en las etiquetas <img>
            html_body = template.render(
                data=data,
                today_date=datetime.now().strftime('%d/%m/%Y'),
                cid_chart_30='chart_30_days_id', # Pasar los CIDs
                cid_chart_12='chart_12_months_id'
            )

            # --- Construir Asunto ---
            subject = config.get('subject', 'Cierre de Ventas Diario Empresa: %empresa%')
            nombre_empresa = data.get('nombre_empresa', '')
            if '%empresa%' in subject and nombre_empresa:
                subject = subject.replace('%empresa%', nombre_empresa)
                report_name = f"Resumen Diario {nombre_empresa}"

            # --- Enviar Correo con Imágenes Embebidas ---
            send_email(
                smtp_config=smtp_config,
                recipients=[e.strip() for e in recipients_str.split(',') if e.strip()],
                cc=[],
                subject=subject,
                body=html_body,
                is_html=True,
                images=images_to_embed # Pasar la lista de imágenes [(cid, bytes), ...]
            )

            log_email_sent(report_name, recipients_str, "Enviado")
            print(f"[{datetime.now()}] Resumen diario '{report_name}' ENVIADO.")

        except Exception as e:
            error_message = str(e)
            log_recipients = recipients_str if recipients_str else "N/A"
            log_email_sent(report_name, log_recipients, "Fallido", error_message)
            print(f"[{datetime.now()}] ERROR Resumen Diario '{report_name}': {error_message}")
            traceback.print_exc() # Imprimir traceback completo en consola
