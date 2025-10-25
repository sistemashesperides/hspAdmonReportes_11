from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from functools import wraps
from app.admin.services import *
from core.scheduler_service import scheduler, update_job_for_design
from app.reports.generator_service import generate_report
from app.utils.email_sender import send_email
from app.admin.services import log_email_sent

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Decorador de Autenticación ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'warning')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Autenticación y Generales ---
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session:
        return redirect(url_for('admin.designs'))
    if request.method == 'POST':
        if verify_user(request.form['username'], request.form['password']):
            session['logged_in'] = True
            session['username'] = request.form['username']
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('admin.designs'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('admin/login.html')

@admin_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if 'update_smtp_settings' in request.form:
            update_settings(request.form)
            flash('Configuración de correo guardada.', 'success')
        elif 'update_password' in request.form:
            if verify_user(session['username'], request.form['current_password']):
                update_password(session['username'], request.form['new_password'])
                flash('Contraseña actualizada correctamente.', 'success')
            else:
                flash('La contraseña actual es incorrecta.', 'danger')
        return redirect(url_for('admin.settings'))
    current_settings = get_settings()
    return render_template('admin/settings.html', settings=current_settings)

# --- Rutas de Gestión de Conexiones ---
@admin_bp.route('/connections', methods=['GET', 'POST'])
@login_required
def connections():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save':
            save_connection(request.form)
            flash('Conexión guardada correctamente.', 'success')
        elif action == 'delete':
            delete_connection(request.form.get('id'))
            flash('Conexión eliminada.', 'info')
        return redirect(url_for('admin.connections'))
    all_connections = get_all_connections()
    return render_template('admin/connections.html', connections=all_connections)

@admin_bp.route('/connections/test', methods=['POST'])
@login_required
def test_db_connection():
    success, message = test_connection(request.json)
    return jsonify({'success': success, 'message': message})

# --- Rutas de Gestión de Repositorios ---
@admin_bp.route('/repositories', methods=['GET', 'POST'])
@login_required
def repositories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save':
            save_repository(request.form)
            flash('Repositorio guardado correctamente.', 'success')
        elif action == 'delete':
            delete_repository(request.form.get('id'))
            flash('Repositorio eliminado.', 'info')
        return redirect(url_for('admin.repositories'))
    all_repos = get_all_repositories()
    all_conns = get_all_connections()
    return render_template('admin/repositories.html', repositories=all_repos, connections=all_conns)

@admin_bp.route('/repositories/test', methods=['POST'])
@login_required
def test_repository():
    data = request.json
    success, message, result_data = test_repository_query(data['connection_id'], data['sql_query'])
    return jsonify({'success': success, 'message': message, 'data': result_data})

# --- Rutas de Gestión de Diseños de Reportes ---
@admin_bp.route('/designs', methods=['GET', 'POST'])
@login_required
def designs():
    if request.method == 'POST':
        if request.form.get('action') == 'delete':
            design_id_to_delete = request.form.get('id')
            job_id = f'report_job_{design_id_to_delete}'
            if scheduler.get_job(job_id):
                scheduler.remove_job(id=job_id)
            delete_design(design_id_to_delete)
            flash('Diseño y su tarea programada han sido eliminados.', 'info')
        return redirect(url_for('admin.designs'))
    all_designs = get_all_designs()
    return render_template('admin/designs.html', designs=all_designs)

@admin_bp.route('/designer', methods=['GET', 'POST'])
@admin_bp.route('/designer/<int:design_id>', methods=['GET', 'POST'])
@login_required
def designer(design_id=None):
    if request.method == 'POST':
        saved_design_id = save_design(request.form, request.files)
        full_design = get_design_by_id(saved_design_id)
        if full_design:
            update_job_for_design(full_design)
        flash('Diseño guardado y tarea programada actualizada.', 'success')
        return redirect(url_for('admin.designs'))
    design_data = get_design_by_id(design_id) if design_id else None
    all_repos = get_all_repositories()
    return render_template('admin/designer.html', design=design_data, repositories=all_repos)

# --- Rutas de API y Ejecución de Reportes ---
@admin_bp.route('/api/repository-columns/<int:repository_id>')
@login_required
def get_repo_columns(repository_id):
    success, message, columns = get_repository_columns(repository_id)
    return jsonify({'success': success, 'message': message, 'columns': columns})

@admin_bp.route('/execute-report/<int:design_id>', methods=['GET', 'POST'])
@login_required
def execute_report(design_id):
    try:
        filter_values = request.form.to_dict()
        output, mimetype, filename = generate_report(design_id, filter_values)
        headers = {'Content-Disposition': f'inline;filename={filename}'}
        return Response(output, mimetype=mimetype, headers=headers)
    except Exception as e:
        flash(f'Error al generar el reporte: {str(e)}', 'danger')
        return redirect(url_for('admin.designs'))
    
    # app/admin/routes.py

# ... (otras rutas)

# --- NUEVO: Ruta para el Historial de Envíos ---
@admin_bp.route('/email-log')
@login_required
def email_log():
    logs = get_email_logs()
    return render_template('admin/email_log.html', logs=logs)

# ... (resto de las rutas)
# --- NUEVO: Ruta para la lista de reportes (Emisión) ---
@admin_bp.route('/report-list')
@login_required
def report_list():
    all_designs = get_all_designs() # Reutilizamos la función existente
    return render_template('admin/report_list.html', designs=all_designs)

# --- NUEVO: Ruta para enviar email manualmente ---
@admin_bp.route('/send-report-email', methods=['POST'])
@login_required
def send_report_email():
    design_id = request.form.get('design_id')
    email_to = request.form.get('email_to')
    email_cc = request.form.get('email_cc')
    subject = request.form.get('subject')
    body_extra = request.form.get('body', '') # Cuerpo adicional opcional

    try:
        design = get_design_by_id(design_id)
        if not design:
            raise ValueError("Diseño no encontrado")
        
        smtp_config = get_settings()
        if not smtp_config.get('smtp_server'):
            raise ValueError("Servidor SMTP no configurado.")

        # Recolectar valores de los filtros del formulario
        filter_values = {}
        if design['config'].get('filters'):
            for f in design['config']['filters']:
                filter_values[f['name']] = request.form.get(f['name'])

        # Generar el reporte
        output, mimetype, filename = generate_report(design_id, filter_values)

        # Preparar datos del email
        recipients = [e.strip() for e in email_to.split(',') if e.strip()]
        cc = [e.strip() for e in email_cc.split(',') if e.strip()]
        
        body = f"{body_extra}\n\n" if body_extra else ""
        if design['output_format'] == 'html_email':
             body += output # El reporte es el cuerpo principal
             is_html_body = True
             attachment = None
        else:
             body += "Adjunto encontrará el reporte solicitado."
             is_html_body = False
             attachment = (filename, mimetype, output)

        # Enviar email (usando la utilidad que ya tenemos)
        send_email(
            smtp_config=smtp_config,
            recipients=recipients,
            cc=cc,
            subject=subject,
            body=body,
            is_html=is_html_body,
            attachment=attachment
        )
        
        # Registrar el envío manual
        log_email_sent(design['name'], f"Manual a: {email_to} | CC: {email_cc}", "Enviado")
        flash(f"Reporte '{design['name']}' enviado correctamente.", 'success')

    except Exception as e:
        log_email_sent(design.get('name', f'ID {design_id}'), f"Manual a: {email_to} | CC: {email_cc}", "Fallido", str(e))
        flash(f"Error al enviar el email: {str(e)}", 'danger')

    return redirect(url_for('admin.report_list'))