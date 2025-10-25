# -*- coding: utf-8 -*-
import sqlite3
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pyodbc

DB_PATH = 'settings.db'

# --- Conexión a la BBDD de Configuración ---
def get_db():
    """Establece conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # Permite acceder a las columnas por nombre
    return conn

# --- Inicialización de la Base de Datos ---
def init_db():
    """Crea/actualiza todas las tablas y datos por defecto si no existen."""
    conn = get_db()
    cursor = conn.cursor()

    # --- Creación de Tablas ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            smtp_server TEXT,
            smtp_port INTEGER,
            smtp_user TEXT,
            smtp_password TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS db_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            server TEXT NOT NULL,
            database TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            driver TEXT DEFAULT '{ODBC Driver 17 for SQL Server}'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            sql_query TEXT NOT NULL,
            connection_id INTEGER NOT NULL,
            FOREIGN KEY (connection_id) REFERENCES db_connections (id) ON DELETE RESTRICT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_designs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            repository_id INTEGER NOT NULL,
            output_format TEXT NOT NULL DEFAULT 'pdf',
            config_json TEXT NOT NULL,
            email_to TEXT,
            email_cc TEXT,
            schedule_days TEXT,
            schedule_time TEXT,
            FOREIGN KEY (repository_id) REFERENCES data_repositories (id) ON DELETE RESTRICT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            report_name TEXT NOT NULL,
            recipients TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Enviado', 'Fallido', 'Omitido')),
            error_message TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_summary_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_enabled BOOLEAN DEFAULT 0,
            connection_id INTEGER,
            subject TEXT,
            recipients TEXT,
            schedule_time TEXT,
            sql_query TEXT,
            FOREIGN KEY (connection_id) REFERENCES db_connections (id) ON DELETE SET NULL
        )
    ''')

    # --- Inicialización de Datos por Defecto ---
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        hashed_password = generate_password_hash('97518741')
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', hashed_password))

    cursor.execute("SELECT * FROM settings WHERE id = 1")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO settings (id, smtp_server, smtp_port, smtp_user, smtp_password) VALUES (1, '', 587, '', '')")

    cursor.execute("SELECT * FROM daily_summary_config WHERE id = 1")
    if cursor.fetchone() is None:
        # ==================== CONSULTA SQL POR DEFECTO ACTUALIZADA ====================
        default_query = """
SET DATEFORMAT YMD;
DECLARE @Hoy DATE = GETDATE();
DECLARE @FechaDesde VARCHAR(19) = CONVERT(CHAR(10), @Hoy, 126) + ' 00:00:00';
DECLARE @FechaHasta VARCHAR(19) = CONVERT(CHAR(10), @Hoy, 126) + ' 23:59:59';
DECLARE @Hace30Dias DATE = DATEADD(day, -30, @Hoy);
DECLARE @Hace12Meses DATE = DATEADD(month, -12, DATEFROMPARTS(YEAR(@Hoy), MONTH(@Hoy), 1));
DECLARE @IVA DECIMAL(28,4) = ISNULL(((SELECT MtoTax FROM SATAXES WHERE CodTaxs = 'IVA') / 100.0) + 1.0, 1.0); -- Maneja NULL por si no existe IVA

-- Los resultados se procesan secuencialmente por la aplicación

SELECT TOP 1 RTRIM(Descrip) AS NombreEmpresa FROM SACONF; -- 1
SELECT TipoFac AS Documento, COUNT(TipoFac) AS Cantidad, SUM(MtoTotal - ISNULL(RetenIVA, 0)) AS MontoBruto FROM SAFACT WHERE ISNULL(CodOper, '') <> 'IN' AND TipoFac IN ('A', 'B', 'C', 'D') AND FechaE BETWEEN @FechaDesde AND @FechaHasta GROUP BY TipoFac ORDER BY TipoFac ASC; -- 2
SELECT SUM(CASE WHEN TipoFac = 'A' THEN MtoTotal - ISNULL(RetenIVA, 0) ELSE 0 END) - SUM(CASE WHEN TipoFac = 'B' THEN MtoTotal - ISNULL(RetenIVA, 0) ELSE 0 END) AS VentasNetas FROM SAFACT WHERE ISNULL(CodOper, '') <> 'IN' AND TipoFac IN ('A', 'B') AND FechaE BETWEEN @FechaDesde AND @FechaHasta; -- 3
SELECT SUM(CASE WHEN TipoFac = 'C' THEN MtoTotal - ISNULL(RetenIVA, 0) ELSE 0 END) - SUM(CASE WHEN TipoFac = 'D' THEN MtoTotal - ISNULL(RetenIVA, 0) ELSE 0 END) AS NotasEntregaNetas FROM SAFACT WHERE ISNULL(CodOper, '') <> 'IN' AND TipoFac IN ('C', 'D') AND FechaE BETWEEN @FechaDesde AND @FechaHasta; -- 4
SELECT SUM(CASE WHEN SF.TipoFac = 'A' THEN ISNULL(SF.ImpuestoD, 0) ELSE 0 END) - SUM(CASE WHEN SF.TipoFac = 'B' THEN ISNULL(SF.ImpuestoD, 0) ELSE 0 END) AS IGTF_Neto FROM SAFACT SF WHERE ISNULL(SF.CodOper, '') <> 'IN' AND SF.TipoFac IN ('A', 'B') AND SF.FechaE BETWEEN @FechaDesde AND @FechaHasta; -- 5 (Asumiendo ImpuestoD está en SAFACT)
SELECT SUM(CASE WHEN SF.TipoFac IN ('A', 'C') THEN ISNULL(SF.Descto1, 0) WHEN SF.TipoFac IN ('B', 'D') THEN -ISNULL(SF.Descto1, 0) ELSE 0 END) * @IVA AS DescuentosNetos FROM SAFACT SF WHERE SF.FechaE BETWEEN @FechaDesde AND @FechaHasta AND SF.TipoFac IN ('A', 'B', 'C', 'D'); -- 6 (Asumiendo Descto1 está en SAFACT y se aplica IVA)
SELECT SUM(ISNULL(Saldo, 0) / CASE WHEN ISNULL(Factor, 1) = 0 THEN 1 ELSE Factor END) AS CuentasPorCobrarHoy FROM SAACXC WHERE FechaE BETWEEN @FechaDesde AND @FechaHasta; -- 7
SELECT ISNULL(SI.tipofac, 'N/A') AS TipoDocumento, SI.CodTarj, ST.Descrip AS Instrumento, SUM(SI.monto) AS MontoTotalPago FROM SAIPAVTA SI INNER JOIN SATARJ ST ON SI.CodTarj = ST.CodTarj WHERE SI.FechaE BETWEEN @FechaDesde AND @FechaHasta GROUP BY ISNULL(SI.tipofac, 'N/A'), SI.CodTarj, ST.Descrip ORDER BY TipoDocumento, MontoTotalPago DESC; -- 8
SELECT TOP 10 CodItem, Descrip1 AS Producto, SUM(CASE WHEN TipoFac IN ('A', 'C') THEN Cantidad ELSE -Cantidad END) AS CantidadNeta FROM SAITEMFAC WHERE FechaE BETWEEN @FechaDesde AND @FechaHasta AND TipoFac IN ('A', 'B', 'C', 'D') GROUP BY CodItem, Descrip1 HAVING SUM(CASE WHEN TipoFac IN ('A', 'C') THEN Cantidad ELSE -Cantidad END) > 0 ORDER BY CantidadNeta DESC; -- 9
SELECT TOP 10 CodItem, Descrip1 AS Producto, SUM(CASE WHEN TipoFac IN ('A', 'C') THEN TotalItem ELSE -TotalItem END) AS MontoNeto FROM SAITEMFAC WHERE FechaE BETWEEN @FechaDesde AND @FechaHasta AND TipoFac IN ('A', 'B', 'C', 'D') GROUP BY CodItem, Descrip1 HAVING SUM(CASE WHEN TipoFac IN ('A', 'C') THEN TotalItem ELSE -TotalItem END) > 0 ORDER BY MontoNeto DESC; -- 10
SELECT CONVERT(DATE, FechaE) AS Dia, SUM(CASE WHEN TipoFac = 'A' THEN MtoTotal - ISNULL(RetenIVA, 0) WHEN TipoFac = 'B' THEN -(MtoTotal - ISNULL(RetenIVA, 0)) ELSE 0 END) AS VentaNetaDiaria, SUM(CASE WHEN TipoFac = 'C' THEN MtoTotal - ISNULL(RetenIVA, 0) WHEN TipoFac = 'D' THEN -(MtoTotal - ISNULL(RetenIVA, 0)) ELSE 0 END) AS NotaNetaDiaria FROM SAFACT WHERE ISNULL(CodOper, '') <> 'IN' AND TipoFac IN ('A', 'B', 'C', 'D') AND FechaE >= @Hace30Dias AND FechaE < DATEADD(day, 1, @Hoy) GROUP BY CONVERT(DATE, FechaE) ORDER BY Dia ASC; -- 11
SELECT FORMAT(FechaE, 'yyyy-MM') AS MesAno, SUM(CASE WHEN TipoFac = 'A' THEN MtoTotal - ISNULL(RetenIVA, 0) WHEN TipoFac = 'B' THEN -(MtoTotal - ISNULL(RetenIVA, 0)) ELSE 0 END) AS VentaNetaMensual FROM SAFACT WHERE ISNULL(CodOper, '') <> 'IN' AND TipoFac IN ('A', 'B') AND FechaE >= @Hace12Meses AND FechaE < DATEFROMPARTS(YEAR(@Hoy), MONTH(@Hoy), 1) GROUP BY FORMAT(FechaE, 'yyyy-MM') ORDER BY MesAno ASC; -- 12
        """
        # ==========================================================================
        # Insertar la fila con la consulta SQL por defecto
        cursor.execute("INSERT INTO daily_summary_config (id, is_enabled, subject, recipients, schedule_time, sql_query) VALUES (1, 0, 'Cierre de Ventas Diario Empresa: %empresa%', '', '08:00', ?)", (default_query,))

    # Commit y Cierre (SOLO AL FINAL de init_db)
    conn.commit()
    conn.close()

# --- Gestión de Configuración Global (SMTP) ---
def get_settings():
    conn = get_db()
    settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return dict(settings) if settings else {}

def update_settings(data):
    """Actualiza la configuración SMTP."""
    conn = get_db()
    conn.execute('''
        UPDATE settings SET smtp_server = ?, smtp_port = ?, smtp_user = ?, smtp_password = ? WHERE id = 1
    ''', (
        data.get('smtp_server'), data.get('smtp_port'),
        data.get('smtp_user'), data.get('smtp_password')
    ))
    conn.commit()
    conn.close()

# --- Gestión de Usuarios ---
def verify_user(username, password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user and check_password_hash(user['password_hash'], password)

def update_password(username, new_password):
    hashed_password = generate_password_hash(new_password)
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed_password, username))
    conn.commit()
    conn.close()

# --- Gestión de Conexiones a BBDD ---
def get_all_connections():
    conn = get_db()
    connections_rows = conn.execute("SELECT * FROM db_connections ORDER BY name").fetchall()
    conn.close()
    return [dict(row) for row in connections_rows]

def save_connection(data):
    conn_id = data.get('id')
    password = data.get('password') # Obtener la contraseña
    conn = get_db()

    # Solo actualizar contraseña si se proporciona una nueva
    if conn_id and conn_id.isdigit():
        if password: # Si se ingresó una contraseña nueva
            conn.execute('UPDATE db_connections SET name=?, server=?, database=?, username=?, password=? WHERE id=?',
                         (data['name'], data['server'], data['database'], data['username'], password, conn_id))
        else: # Si se dejó en blanco, no actualizar la contraseña
            conn.execute('UPDATE db_connections SET name=?, server=?, database=?, username=? WHERE id=?',
                         (data['name'], data['server'], data['database'], data['username'], conn_id))
    else: # Insertar nueva conexión (la contraseña es requerida)
        if not password:
             conn.close() # Cerrar conexión antes de lanzar error
             raise ValueError("La contraseña es requerida para nuevas conexiones.")
        conn.execute('INSERT INTO db_connections (name, server, database, username, password) VALUES (?, ?, ?, ?, ?)',
                     (data['name'], data['server'], data['database'], data['username'], password))
    conn.commit()
    conn.close()

def delete_connection(conn_id):
    conn = get_db()
    cursor = conn.cursor()
    # Verificar dependencias antes de eliminar
    cursor.execute("SELECT COUNT(*) FROM daily_summary_config WHERE connection_id = ?", (conn_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        raise ValueError("No se puede eliminar: conexión usada por el Resumen Diario.")
    cursor.execute("SELECT COUNT(*) FROM data_repositories WHERE connection_id = ?", (conn_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        raise ValueError("No se puede eliminar: conexión usada por uno o más Repositorios.")

    conn.execute("DELETE FROM db_connections WHERE id=?", (conn_id,))
    conn.commit()
    conn.close()

def test_connection(data):
    try:
        password = data.get('password')
        # Si no se proporciona contraseña al probar (ej. editando), intentar obtener la guardada
        if not password and data.get('id'):
             conn_temp = get_db()
             saved_conn = conn_temp.execute("SELECT password FROM db_connections WHERE id=?", (data.get('id'),)).fetchone()
             conn_temp.close()
             if saved_conn: password = saved_conn['password']

        if not password: # Si sigue sin haber contraseña (nueva conexión sin pass o error)
            return False, "Se requiere contraseña para probar la conexión."

        conn_str = f"DRIVER={data.get('driver', '{ODBC Driver 17 for SQL Server}')};SERVER={data['server']};DATABASE={data['database']};UID={data['username']};PWD={password};TrustServerCertificate=yes;"
        cnxn = pyodbc.connect(conn_str, timeout=5)
        cnxn.close()
        return True, "Conexión exitosa"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

# --- Gestión de Repositorios de Datos ---
def get_all_repositories():
    conn = get_db()
    repo_rows = conn.execute('SELECT dr.*, dc.name as connection_name FROM data_repositories dr JOIN db_connections dc ON dr.connection_id = dc.id ORDER BY dr.name').fetchall()
    conn.close()
    return [dict(row) for row in repo_rows]

def get_repository_by_id(repo_id):
    conn = get_db()
    repo_row = conn.execute("SELECT * FROM data_repositories WHERE id = ?", (repo_id,)).fetchone()
    conn.close()
    return dict(repo_row) if repo_row else None

def save_repository(data):
    repo_id = data.get('id')
    conn = get_db()
    if repo_id and repo_id.isdigit():
        conn.execute('UPDATE data_repositories SET name=?, description=?, sql_query=?, connection_id=? WHERE id=?',
                     (data['name'], data['description'], data['sql_query'], data['connection_id'], repo_id))
    else:
        conn.execute('INSERT INTO data_repositories (name, description, sql_query, connection_id) VALUES (?, ?, ?, ?)',
                     (data['name'], data['description'], data['sql_query'], data['connection_id']))
    conn.commit()
    conn.close()

def delete_repository(repo_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM report_designs WHERE repository_id = ?", (repo_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        raise ValueError("No se puede eliminar: repositorio usado por uno o más Diseños.")

    conn.execute("DELETE FROM data_repositories WHERE id=?", (repo_id,))
    conn.commit()
    conn.close()

# --- Gestión de Diseños de Reportes ---
def get_all_designs():
    conn = get_db()
    design_rows = conn.execute('SELECT rd.*, dr.name as repository_name FROM report_designs rd JOIN data_repositories dr ON rd.repository_id = dr.id ORDER BY rd.name').fetchall()
    conn.close()
    designs = []
    for row in design_rows:
        design = dict(row)
        try:
            design['config'] = json.loads(design['config_json'] or '{}') # Carga segura
        except json.JSONDecodeError:
             design['config'] = {}
        designs.append(design)
    return designs

def get_design_by_id(design_id):
    conn = get_db()
    design_row = conn.execute("SELECT * FROM report_designs WHERE id = ?", (design_id,)).fetchone()
    conn.close()
    if not design_row: return None
    design = dict(design_row)
    try:
        design['config'] = json.loads(design['config_json'] or '{}')
    except json.JSONDecodeError:
        design['config'] = {}
    # Convertir schedule_days de JSON string a lista Python para la plantilla
    try:
        design['schedule_days'] = json.loads(design['schedule_days'] or '[]')
    except json.JSONDecodeError:
        design['schedule_days'] = []
    return design

def save_design(form_data, file_data):
    design_id = form_data.get('id')

    # Procesar campos, etiquetas y orden
    field_order = form_data.getlist('field_order')
    fields_config = {'order': field_order, 'details': {}}
    for field_name in field_order:
        fields_config['details'][field_name] = {'label': form_data.get(f'field_label_{field_name}', field_name), 'visible': f'field_visible_{field_name}' in form_data}

    # Procesar filtros
    filters = []
    filter_labels, filter_names, filter_types = form_data.getlist('filter_label'), form_data.getlist('filter_name'), form_data.getlist('filter_type')
    for i in range(len(filter_labels)):
        if filter_labels[i] and filter_names[i]: filters.append({'label': filter_labels[i], 'name': filter_names[i], 'type': filter_types[i]})

    # Procesar branding (logo y texto)
    branding_config = {'header_text': form_data.get('header_text')}
    logo_file = file_data.get('company_logo')
    current_logo = None
    if design_id: # Si editamos, obtener logo actual
        old_design = get_design_by_id(design_id)
        if old_design and old_design.get('config', {}).get('branding'):
            current_logo = old_design['config']['branding'].get('logo_filename')

    if logo_file and logo_file.filename != '':
        filename = secure_filename(logo_file.filename)
        upload_folder = os.path.join(os.path.dirname(DB_PATH), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        logo_path = os.path.join(upload_folder, filename)

        # Eliminar logo anterior si existe y es diferente
        if current_logo and current_logo != filename:
             old_logo_path = os.path.join(upload_folder, current_logo)
             if os.path.exists(old_logo_path):
                 try: os.remove(old_logo_path)
                 except OSError as e: print(f"Error eliminando logo antiguo {old_logo_path}: {e}")

        logo_file.save(logo_path)
        branding_config['logo_filename'] = filename
    elif current_logo: # Mantener logo antiguo si no se subió nuevo
        branding_config['logo_filename'] = current_logo

    # Empaquetar configuración
    config = {'fields': fields_config, 'group_by_field': form_data.get('group_by_field'), 'total_fields': form_data.getlist('total_fields'), 'chart': {'type': form_data.get('chart_type'), 'x_axis': form_data.get('chart_x_axis'), 'y_axis': form_data.get('chart_y_axis')}, 'branding': branding_config, 'filters': filters}
    config_json = json.dumps(config)

    conn = get_db()
    cursor = conn.cursor()
    # Guardar schedule_days como JSON string
    schedule_days_json = json.dumps(form_data.getlist('schedule_days'))
    params = (
        form_data.get('name'), form_data.get('repository_id'), form_data.get('output_format'), config_json,
        form_data.get('email_to'), form_data.get('email_cc'),
        schedule_days_json, form_data.get('schedule_time')
    )

    if design_id and design_id.isdigit():
        cursor.execute('UPDATE report_designs SET name=?, repository_id=?, output_format=?, config_json=?, email_to=?, email_cc=?, schedule_days=?, schedule_time=? WHERE id=?', (*params, design_id))
        saved_design_id = int(design_id)
    else:
        cursor.execute('INSERT INTO report_designs (name, repository_id, output_format, config_json, email_to, email_cc, schedule_days, schedule_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', params)
        saved_design_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return saved_design_id

def delete_design(design_id):
    # Opcional: Eliminar logo asociado si existe
    design_to_delete = get_design_by_id(design_id)
    if design_to_delete and design_to_delete.get('config', {}).get('branding', {}).get('logo_filename'):
        logo_filename = design_to_delete['config']['branding']['logo_filename']
        upload_folder = os.path.join(os.path.dirname(DB_PATH), 'uploads')
        logo_path = os.path.join(upload_folder, logo_filename)
        if os.path.exists(logo_path):
            try: os.remove(logo_path)
            except OSError as e: print(f"Error eliminando logo {logo_path}: {e}")

    conn = get_db()
    conn.execute("DELETE FROM report_designs WHERE id=?", (design_id,))
    conn.commit()
    conn.close()

# --- Funciones de Ejecución de Consultas ---
def get_repository_columns(repository_id):
    """Obtiene nombres de columnas de un query de forma segura."""
    repo = get_repository_by_id(repository_id)
    if not repo: return False, "Repositorio no encontrado.", None
    conn_db = get_db()
    conn_details_row = conn_db.execute("SELECT * FROM db_connections WHERE id = ?", (repo['connection_id'],)).fetchone()
    conn_db.close()
    if not conn_details_row: return False, "Conexión no encontrada.", None
    conn_details = dict(conn_details_row)
    cnxn = None
    try:
        conn_str = f"DRIVER={conn_details['driver']};SERVER={conn_details['server']};DATABASE={conn_details['database']};UID={conn_details['username']};PWD={conn_details['password']};TrustServerCertificate=yes;"
        cnxn = pyodbc.connect(conn_str, timeout=5)
        cursor = cnxn.cursor()

        # Limpiar query para análisis
        original_query = repo['sql_query']
        query_for_analysis = original_query
        where_pos = original_query.lower().find(' where ')
        if where_pos != -1: query_for_analysis = original_query[:where_pos]

        cursor.execute("EXEC sp_describe_first_result_set @tsql = ?", query_for_analysis)
        columns = [row.name for row in cursor.fetchall() if row.name] # Asegurarse de que el nombre no sea None
        cnxn.close()

        if not columns: return False, "La consulta parece válida, pero no produce ninguna columna.", None
        return True, "Columnas obtenidas.", columns
    except pyodbc.Error as e:
        if cnxn: cnxn.close()
        sql_error = str(e)
        if 'syntax error' in sql_error.lower() or 'incorrect syntax' in sql_error.lower():
             return False, f"Error de sintaxis en consulta SQL: {sql_error}", None
        return False, f"Error al analizar consulta: {sql_error}", None
    except Exception as e:
        if cnxn: cnxn.close()
        return False, f"Error inesperado al obtener columnas: {e}", None

def execute_repository_query(repository_id, params=None):
    """Ejecuta consulta con parámetros y devuelve datos."""
    repo = get_repository_by_id(repository_id)
    if not repo: return False, "Repositorio no encontrado.", None
    conn_db = get_db()
    conn_details_row = conn_db.execute("SELECT * FROM db_connections WHERE id = ?", (repo['connection_id'],)).fetchone()
    conn_db.close()
    if not conn_details_row: return False, "Conexión no encontrada.", None
    conn_details = dict(conn_details_row)
    cnxn = None
    try:
        conn_str = f"DRIVER={conn_details['driver']};SERVER={conn_details['server']};DATABASE={conn_details['database']};UID={conn_details['username']};PWD={conn_details['password']};TrustServerCertificate=yes;"
        cnxn = pyodbc.connect(conn_str, timeout=10)
        cursor = cnxn.cursor()

        # Ejecutar con parámetros
        cursor.execute(repo['sql_query'], params if params else [])

        if cursor.description is None:
            columns, all_data = [], []
        else:
            columns = [column[0] for column in cursor.description]
            all_data = [tuple(row) for row in cursor.fetchall()]

        cnxn.close()
        data_dict = {'columns': columns, 'data': all_data}
        return True, "Consulta ejecutada.", data_dict
    except Exception as e:
        if cnxn: cnxn.close()
        print(f"Error detallado en execute_repository_query: {e}")
        return False, f"Error al ejecutar consulta: {e}", None

# --- Gestión del Historial de Envíos ---
def log_email_sent(report_name, recipients, status, error_message=None):
    conn = get_db()
    valid_status = status if status in ('Enviado', 'Fallido', 'Omitido') else 'Fallido'
    conn.execute('INSERT INTO email_logs (report_name, recipients, status, error_message) VALUES (?, ?, ?, ?)',
                 (report_name, recipients, valid_status, error_message))
    conn.commit()
    conn.close()

def get_email_logs(limit=100):
    conn = get_db()
    log_rows = conn.execute("SELECT * FROM email_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in log_rows]

# --- Gestión Configuración Resumen Diario ---
def get_daily_summary_config():
    conn = get_db()
    config = conn.execute("SELECT * FROM daily_summary_config WHERE id = 1").fetchone()
    conn.close()
    return dict(config) if config else {}

def update_daily_summary_config(data):
    conn = get_db()
    conn.execute('''
        UPDATE daily_summary_config SET
        is_enabled = ?, connection_id = ?, subject = ?, recipients = ?, schedule_time = ?, sql_query = ?
        WHERE id = 1
    ''', (
        1 if 'is_enabled' in data else 0,
        data.get('connection_id'),
        data.get('subject'),
        data.get('recipients'),
        data.get('schedule_time'),
        data.get('sql_query')
    ))
    conn.commit()
    conn.close()