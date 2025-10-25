# run_report_task.py
from app.reports.data_repositories import get_ventas_por_cliente
from app.reports.report_generator import generar_reporte_ventas
from app.admin.services import get_settings # ¡Importante!
# from utils.email_sender import enviar_email
from datetime import datetime
import json
import sys

def ejecutar_reporte_diario():
    # 1. Obtener la configuración de la GUI
    config = get_settings()
    
    # 2. Verificar si hoy es un día de envío programado
    hoy_semana = str(datetime.now().weekday()) # Lunes=0, Domingo=6
    dias_programados = json.loads(config.get('schedule_days', '[]'))
    
    if hoy_semana not in dias_programados:
        print(f"Hoy no es un día programado para el envío. Tarea omitida.")
        sys.exit()
    
    # (El resto del script sigue igual: obtiene datos, genera reporte)
    # ...
    
    # Al final, usa los datos de config para enviar el correo
    print(f"Enviando correo a: {config['email_to']} con CC a: {config['email_cc']}")
    # enviar_email(
    #     smtp_config={
    #         'server': config['smtp_server'],
    #         'port': config['smtp_port'],
    #         # ...etc.
    #     },
    #     destinatario=config['email_to'],
    #     cc=config['email_cc'],
    #     # ...
    # )

if __name__ == '__main__':
    ejecutar_reporte_diario()