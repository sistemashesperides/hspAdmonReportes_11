# utils/db_config_ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import configparser

def save_connection_string(server, database, user, password):
    """Guarda la cadena de conexión en config.ini."""
    conn_str = (
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={user};'
        f'PWD={password};'
    )
    
    config = configparser.ConfigParser()
    config['database'] = {'connection_string': conn_str}
    
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    
    messagebox.showinfo("Guardado", "Configuración de conexión guardada exitosamente.")

def open_db_config_window():
    # ... (El código completo de la ventana Tkinter iría aquí)
    # Este código crea una ventana simple con campos de texto y un botón para guardar.
    # Por brevedad, se omite aquí pero es un formulario estándar de Tkinter.
    # El objetivo final es llamar a save_connection_string() con los datos del usuario.
    print("UI de configuración de BBDD abierta (simulación).")