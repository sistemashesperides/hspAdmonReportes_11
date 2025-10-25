# -*- coding: utf-8 -*-
import pyodbc
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Usar backend no interactivo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from app.admin.services import get_db as get_config_db
import traceback # Importar traceback aquí

# --- Funciones de Generación de Gráficos (sin cambios) ---
def generate_30_day_chart(data):
    """Genera el gráfico de tendencia de 30 días como PNG base64."""
    if not data: return None
    try:
        df = pd.DataFrame(data)
        if 'Dia' not in df.columns: # Añadir verificación
             print("WARN: Columna 'Dia' no encontrada para gráfico 30 días.")
             # traceback.print_exc() # Descomentar para ver el traceback si sigue fallando
             return None
        df['Dia'] = pd.to_datetime(df['Dia'])
        df = df.set_index('Dia')
        df['VentaNetaDiaria'] = pd.to_numeric(df['VentaNetaDiaria'], errors='coerce').fillna(0)
        df['NotaNetaDiaria'] = pd.to_numeric(df['NotaNetaDiaria'], errors='coerce').fillna(0)
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df.index, df['VentaNetaDiaria'], label='Ventas Netas', marker='o', linestyle='-')
        ax.plot(df.index, df['NotaNetaDiaria'], label='Notas Entrega Netas', marker='x', linestyle='--')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        fig.autofmt_xdate()
        ax.set_title('Tendencia Neta - Últimos 30 Días')
        ax.set_ylabel('Monto Neto')
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        # Devolver bytes para embeber en correo con CID
        # return f"data:image/png;base64,{image_base64}"
        buf.seek(0) # Rebobinar para leer los bytes
        return buf.getvalue()
    except Exception as e:
        print(f"Error generando gráfico 30 días: {e}")
        traceback.print_exc() # Imprimir traceback completo del error del gráfico
        return None

def generate_12_month_chart(data):
    """Genera el gráfico de tendencia de 12 meses como PNG base64."""
    if not data: return None
    try:
        df = pd.DataFrame(data)
        if 'MesAno' not in df.columns: # Añadir verificación
            print("WARN: Columna 'MesAno' no encontrada para gráfico 12 meses.")
            # traceback.print_exc() # Descomentar para ver el traceback si sigue fallando
            return None
        df['MesAno'] = df['MesAno'].astype(str)
        df = df.set_index('MesAno')
        df['VentaNetaMensual'] = pd.to_numeric(df['VentaNetaMensual'], errors='coerce').fillna(0)
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df.index, df['VentaNetaMensual'], label='Ventas Netas Mensuales', marker='o', linestyle='-')
        ax.set_title('Tendencia Ventas Netas - Últimos 12 Meses')
        ax.set_ylabel('Monto Neto Mensual')
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        # Devolver bytes para embeber en correo con CID
        # return f"data:image/png;base64,{image_base64}"
        buf.seek(0) # Rebobinar para leer los bytes
        return buf.getvalue()
    except Exception as e:
        print(f"Error generando gráfico 12 meses: {e}")
        traceback.print_exc() # Imprimir traceback completo del error del gráfico
        return None

# --- Función Principal de Obtención de Datos (CON LECTURA SECUENCIAL PARA 12 RESULTADOS) ---
def get_daily_summary_data(connection_id, sql_query):
    """Ejecuta la consulta unificada (12 resultados), devuelve datos y logs en caso de error."""
    debug_log = ["--- INICIO OBTENCIÓN DATOS RESUMEN ---"]
    conn_db = get_config_db()
    conn_details_row = conn_db.execute("SELECT * FROM db_connections WHERE id = ?", (connection_id,)).fetchone()
    conn_db.close()
    if not conn_details_row:
        error_msg = f"No se encontró la conexión con ID {connection_id}"
        debug_log.append(f"ERROR: {error_msg}")
        return False, {"error": error_msg, "debug_log": debug_log}
    conn_details = dict(conn_details_row)
    debug_log.append(f"Conexión encontrada: {conn_details.get('name')}")
    sql = sql_query
    results = {}
    cnxn = None
    step_name = "Inicio" # Para saber qué paso falló
    try:
        conn_str = f"DRIVER={conn_details['driver']};SERVER={conn_details['server']};DATABASE={conn_details['database']};UID={conn_details['username']};PWD={conn_details['password']};TrustServerCertificate=yes;"
        debug_log.append(f"Intentando conectar a: {conn_details['server']} / {conn_details['database']}")
        cnxn = pyodbc.connect(conn_str, timeout=20)
        cursor = cnxn.cursor()
        debug_log.append("Conexión BBDD externa exitosa.")
        debug_log.append("Ejecutando consulta SQL...")
        cursor.execute(sql)
        debug_log.append("Consulta SQL ejecutada.")

        # --- Funciones auxiliares robustas ---
        def fetch_dict_list(cursor, step_name):
             nonlocal debug_log
             debug_log.append(f"Leyendo lista para: {step_name}")
             data, cols = [], []
             try:
                 # Es crucial verificar cursor.description ANTES de intentar leer columnas o filas
                 if cursor.description:
                     cols = [c[0] for c in cursor.description]
                     # Solo intentar fetchall si hay descripción
                     data = [dict(zip(cols, row)) for row in cursor.fetchall()]
                 else:
                     debug_log.append(f"Sin descripción/resultados para {step_name}")
                 debug_log.append(f"Leídas {len(data)} filas para {step_name}. Columnas: {cols}")
             except pyodbc.ProgrammingError as pe: # Capturar si fetchall falla porque no hay resultados
                 debug_log.append(f"WARN: ProgrammingError en fetch_dict_list({step_name}): {pe}")
             except Exception as e:
                 debug_log.append(f"ERROR: Excepción inesperada en fetch_dict_list para {step_name}: {e}")
                 raise
             return data

        def fetch_scalar(cursor, step_name):
            nonlocal debug_log
            debug_log.append(f"Leyendo escalar para: {step_name}")
            value = 0.0 # Valor por defecto numérico
            try:
                row = cursor.fetchone()
                if row and row[0] is not None:
                    # Intentar convertir a float, si falla, mantener 0.0
                    try: value = float(row[0])
                    except (ValueError, TypeError):
                         debug_log.append(f"WARN: No se pudo convertir a float el valor para {step_name}: {row[0]}")
                         value = 0.0
                debug_log.append(f"Valor para {step_name}: {value}")
            except pyodbc.ProgrammingError as pe:
                 debug_log.append(f"WARN: ProgrammingError en fetch_scalar({step_name}): {pe}")
            # Devolver siempre 0.0 si hay error o no hay valor
            return value

        # --- Procesar los 12 resultados SECUENCIALMENTE ---
        step_name="1. NombreEmpresa"
        debug_log.append(f"Leyendo string para: {step_name}")
        nombre_empresa_row = cursor.fetchone()
        results['nombre_empresa'] = nombre_empresa_row[0].strip() if nombre_empresa_row and nombre_empresa_row[0] else "Empresa Desconocida"
        debug_log.append(f"Valor para {step_name}: {results['nombre_empresa']}")
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="2. ResumenDocumentos"
        results['resumen_documentos'] = fetch_dict_list(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="3. VentasNetas"
        results['ventas_netas'] = fetch_scalar(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="4. NotasEntregaNetas"
        results['notas_entrega_netas'] = fetch_scalar(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="5. IGTF_Neto"
        results['igtf_neto'] = fetch_scalar(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="6. DescuentosNetos"
        results['descuentos_netos'] = fetch_scalar(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="7. CxcHoy"
        results['cxc_hoy'] = fetch_scalar(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="8. DesglosePagos"
        results['desglose_pagos'] = fetch_dict_list(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="9. TopCantidad"
        results['top_productos_cantidad'] = fetch_dict_list(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="10. TopMonto"
        results['top_productos_monto'] = fetch_dict_list(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="11. Hist30Dias"
        results['historico_30_dias_data'] = fetch_dict_list(cursor, step_name)
        if not cursor.nextset(): raise ValueError(f"Faltan resultados después de {step_name}")

        step_name="12. Hist12Meses"
        results['historico_12_meses_data'] = fetch_dict_list(cursor, step_name)
        # Ya no debería haber más resultados después de este
        # if cursor.nextset(): debug_log.append("WARN: Se encontraron MÁS resultados de los 12 esperados.")

        debug_log.append("Todos los resultados SQL leídos correctamente.")
        cnxn.close()
        debug_log.append("Conexión BBDD externa cerrada.")

        # --- Generar Gráficos (devuelven bytes) ---
        debug_log.append("Generando gráficos...")
        results['chart_30_days_bytes'] = generate_30_day_chart(results['historico_30_dias_data'])
        results['chart_12_months_bytes'] = generate_12_month_chart(results['historico_12_meses_data'])
        debug_log.append("Gráficos generados (o None si fallaron).")

        debug_log.append("--- FIN OBTENCIÓN DATOS RESUMEN (ÉXITO) ---")
        return True, results

    except Exception as e:
        if cnxn:
            try: cnxn.close(); debug_log.append("Conexión BBDD externa cerrada después de error.")
            except Exception as close_e: debug_log.append(f"Error al cerrar conexión BBDD tras error: {close_e}")

        # Incluir el último paso conocido en el mensaje de error
        error_message = f"Error al obtener datos del resumen (en paso '{step_name}'): {e}"
        debug_log.append(f"--- FIN OBTENCIÓN DATOS RESUMEN (ERROR en paso '{step_name}'): {type(e).__name__} - {e} ---")
        debug_log.append(traceback.format_exc()) # Añadir traceback completo al log

        return False, {"error": error_message, "debug_log": debug_log}

