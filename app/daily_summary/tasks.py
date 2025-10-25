# -*- coding: utf-8 -*-
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import os

# Importar scheduler dentro de la función para evitar importación circular
# from core.scheduler_service import scheduler 
from app.admin.services import get_settings as get_smtp_config, log_email_sent, get_daily_summary_config
from app.utils.email_sender import send_email
from app.daily_summary.services import get_daily_summary_data

def send_daily_summary_email_task():
    """Tarea que se ejecuta diariamente para enviar el resumen."""
    # Importar scheduler aquí para tener acceso a app.app_context()
    from core.scheduler_service import scheduler 
    
    with scheduler.app.app_context(): # Usar el contexto de la app del scheduler
        config = get_daily_summary_config()
        smtp_config = get_smtp_config()
        
        # Nombre por defecto para logs si falla antes de obtener el nombre de la empresa
        report_name = "Resumen Diario Ventas" 
        recipients_str = config.get('recipients', '') # Obtener destinatarios para logs

        try:
            # --- Validaciones de Configuración Esenciales ---
            if not config.get('is_enabled'):
                print(f"[{datetime.now()}] Resumen diario de ventas OMITIDO (deshabilitado).")
                return # Salir si no está habilitado
                
            if not config.get('connection_id'):
                raise ValueError("No hay conexión BBDD configurada para el resumen.")
            
            if not recipients_str:
                raise ValueError("No hay destinatarios configurados para el resumen.")
                
            if not smtp_config or not smtp_config.get('smtp_server') or not smtp_config.get('smtp_user'):
                raise ValueError("Servidor SMTP no configurado correctamente (servidor/usuario).")

            sql_query = config.get('sql_query')
            if not sql_query:
                raise ValueError("La consulta SQL para el resumen diario no está configurada.")

            print(f"[{datetime.now()}] Iniciando generación del resumen diario de ventas...")
            
            # --- Obtener Datos ---
            success, data = get_daily_summary_data(config['connection_id'], sql_query) 
            if not success:
                # 'data' contiene el mensaje de error de get_daily_summary_data
                raise ValueError(f"Fallo al obtener datos: {data}") 

            # --- Renderizar Plantilla HTML ---
            project_root = scheduler.app.config.get('PROJECT_ROOT', os.path.dirname(scheduler.app.root_path))
            template_loader = FileSystemLoader(searchpath=os.path.join(project_root, 'templates', 'daily_summary'))
            env = Environment(loader=template_loader)
            
            # Añadir filtro de formato si no existe globalmente
            if 'date_format' not in env.filters:
                 def date_format_filter(value, format='%d/%m/%Y'):
                     # Implementación simple del filtro
                     if isinstance(value, datetime): return value.strftime(format)
                     return value
                 env.filters['date_format'] = date_format_filter
                 
            template = env.get_template('email_body.html')
            html_body = template.render(data=data, today_date=datetime.now().strftime('%d/%m/%Y'))

            # --- Construir Asunto ---
            subject = config.get('subject', 'Cierre de Ventas Diario Empresa: %empresa%')
            nombre_empresa = data.get('nombre_empresa', '')
            if '%empresa%' in subject and nombre_empresa:
                subject = subject.replace('%empresa%', nombre_empresa)
                report_name = f"Resumen Diario {nombre_empresa}" # Actualizar nombre para log

            # --- Enviar Correo ---
            send_email(
                smtp_config=smtp_config,
                recipients=[e.strip() for e in recipients_str.split(',') if e.strip()], # Limpiar espacios y omitir vacíos
                cc=[], # Podrías añadir CC a la configuración si es necesario
                subject=subject,
                body=html_body,
                is_html=True
            )
            
            # --- Registrar Éxito ---
            log_email_sent(report_name, recipients_str, "Enviado")
            print(f"[{datetime.now()}] Resumen diario '{report_name}' ENVIADO exitosamente.")

        except Exception as e:
            # --- Registrar Fallo ---
            error_message = str(e)
            # Asegurar que recipients_str tenga un valor para el log
            log_recipients = recipients_str if recipients_str else "N/A"
            log_email_sent(report_name, log_recipients, "Fallido", error_message)
            print(f"[{datetime.now()}] ERROR al generar/enviar resumen diario '{report_name}': {error_message}")