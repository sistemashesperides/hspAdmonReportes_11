# core/db_connector.py
import pyodbc
import pandas as pd
import configparser
from tkinter import messagebox
from utils.db_config_ui import open_db_config_window

CONFIG_FILE = 'config.ini'

def get_db_connection():
    """
    Intenta conectarse a la BBDD usando config.ini.
    Si falla, abre una UI para que el usuario configure la conexión.
    """
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_FILE):
        # Si el archivo no existe, abre la UI para crearlo
        open_db_config_window()
        parser.read(CONFIG_FILE)

    conn_str = parser['database']['connection_string']
    
    try:
        cnxn = pyodbc.connect(conn_str)
        print("Conexión a la base de datos exitosa.")
        return cnxn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"Error de conexión: {sqlstate}")
        messagebox.showerror("Error de Conexión", "No se pudo conectar a la base de datos. Por favor, revisa la configuración.")
        # Opcional: podrías volver a abrir la UI aquí
        # open_db_config_window()
        return None

def execute_query(query: str, params=None):
    """
    Ejecuta una consulta y devuelve los resultados en un DataFrame de pandas.
    """
    cnxn = get_db_connection()
    if cnxn:
        try:
            df = pd.read_sql(query, cnxn, params=params)
            return df
        finally:
            cnxn.close()
    return pd.DataFrame() # Devuelve un DataFrame vacío si no hay conexión