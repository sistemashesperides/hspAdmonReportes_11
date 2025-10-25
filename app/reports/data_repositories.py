# app/reports/data_repositories.py
from core.db_connector import execute_query
import pandas as pd

def get_ventas_por_cliente(fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """
    Obtiene un resumen de ventas por cliente en un rango de fechas.
    """
    query = """
        SELECT 
            c.Nombre AS Cliente,
            p.Producto,
            SUM(v.Cantidad) AS Unidades,
            SUM(v.PrecioTotal) AS TotalVenta
        FROM Ventas v
        JOIN Clientes c ON v.ClienteID = c.ID
        JOIN Productos p ON v.ProductoID = p.ID
        WHERE v.Fecha BETWEEN ? AND ?
        GROUP BY c.Nombre, p.Producto
        ORDER BY TotalVenta DESC;
    """
    # Los parámetros se pasan así para evitar inyección SQL
    df = execute_query(query, params=(fecha_inicio, fecha_fin))
    return df