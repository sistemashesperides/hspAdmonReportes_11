from flask_apscheduler import APScheduler
from app.admin.services import get_all_designs, get_design_by_id
from app.reports.tasks import execute_scheduled_report
from app.daily_summary.tasks import send_daily_summary_email_task # <-- Importa la nueva tarea
from app.admin.services import get_daily_summary_config          # <-- Importa la config
import json

scheduler = APScheduler()
DAILY_SUMMARY_JOB_ID = 'daily_summary_job'

def update_job_for_design(design):
    """Crea, actualiza o elimina un trabajo para un diseño de reporte específico."""
    job_id = f'report_job_{design["id"]}'
    
    # Extraer horario del diseño
    schedule_time_str = design.get('schedule_time')
    schedule_days_json = design.get('schedule_days', '[]')
    
    # Si no hay horario, eliminar el trabajo si existe
    if not schedule_time_str or not schedule_days_json or schedule_days_json == '[]':
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"Trabajo '{job_id}' eliminado por falta de horario.")
        return

    try:
        hour, minute = map(int, schedule_time_str.split(':'))
        days_of_week = ",".join(json.loads(schedule_days_json))

        job_args = {
            'trigger': 'cron',
            'hour': hour,
            'minute': minute,
            'day_of_week': days_of_week,
            'args': [design['id']]  # Pasamos el design_id a la tarea
        }

        if scheduler.get_job(job_id):
            scheduler.modify_job(id=job_id, **job_args)
            print(f"Trabajo '{job_id}' para '{design['name']}' actualizado.")
        else:
            scheduler.add_job(id=job_id, func=execute_scheduled_report, **job_args)
            print(f"Trabajo '{job_id}' para '{design['name']}' creado.")
            
    except (ValueError, TypeError) as e:
        print(f"Error al procesar horario para trabajo '{job_id}': {e}")


def schedule_all_jobs_on_startup(app):
    """Carga todos los diseños de la BBDD y programa sus trabajos al iniciar."""
    with app.app_context():
        print("Programando todos los trabajos de reportes al iniciar...")
        # Usamos get_all_designs para obtener los IDs, luego get_design_by_id para los detalles
        designs_summary = get_all_designs()
        for design_summary in designs_summary:
            full_design = get_design_by_id(design_summary['id'])
            if full_design:
                update_job_for_design(full_design)

def update_daily_summary_job():
    """Crea, actualiza o elimina el trabajo para el resumen diario."""
    config = get_daily_summary_config()
    
    if config.get('is_enabled') and config.get('schedule_time'):
        try:
            hour, minute = map(int, config['schedule_time'].split(':'))
            job_args = {
                'trigger': 'cron', 'hour': hour, 'minute': minute, 'day_of_week': '*' # Todos los días
            }
            if scheduler.get_job(DAILY_SUMMARY_JOB_ID):
                scheduler.modify_job(id=DAILY_SUMMARY_JOB_ID, **job_args)
                print(f"Trabajo '{DAILY_SUMMARY_JOB_ID}' actualizado.")
            else:
                scheduler.add_job(id=DAILY_SUMMARY_JOB_ID, func=send_daily_summary_email_task, **job_args)
                print(f"Trabajo '{DAILY_SUMMARY_JOB_ID}' creado.")
        except (ValueError, TypeError) as e:
            print(f"Error al procesar horario para '{DAILY_SUMMARY_JOB_ID}': {e}")
    else:
        # Si está deshabilitado o no tiene hora, eliminar el job
        if scheduler.get_job(DAILY_SUMMARY_JOB_ID):
            scheduler.remove_job(DAILY_SUMMARY_JOB_ID)
            print(f"Trabajo '{DAILY_SUMMARY_JOB_ID}' eliminado (deshabilitado o sin hora).")

def schedule_all_jobs_on_startup(app):
    """Carga todos los diseños y el resumen diario al iniciar."""
    with app.app_context():
        print("Programando trabajos de reportes al iniciar...")
        designs_summary = get_all_designs()
        for design_summary in designs_summary:
            full_design = get_design_by_id(design_summary['id'])
            if full_design: update_job_for_design(full_design)
        
        # Añadir la programación del resumen diario
        print("Programando trabajo del resumen diario...")
        update_daily_summary_job()