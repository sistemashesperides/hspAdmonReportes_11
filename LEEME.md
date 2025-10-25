python run_app.py


complementos ---------------------------------------------------------
La Solución: Instalar el "Motor" (GTK+ para Windows)
Sigue estos pasos para instalar las librerías que faltan.

Paso 1: Descargar el instalador de GTK+
Ve a la página oficial de descargas de GTK para Windows. La forma más fácil es a través de los builds de msys2.

Abre este enlace: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

Busca la versión más reciente (la que está arriba del todo).

Descarga el instalador para la arquitectura de tu sistema, que casi seguro será de 64 bits. El archivo se llamará algo como gtk3-runtime-x.x.x-x-ts-win64.exe.

Paso 2: Ejecutar el instalador
Ejecuta el archivo que acabas de descargar. Durante la instalación, llegará un momento clave.

¡MUY IMPORTANTE! Asegúrate de marcar la casilla que dice "Set PATH to include GTK+" o "Add GTK+ to the system PATH".

Esta opción es fundamental porque le dice a Windows dónde encontrar los archivos .dll que WeasyPrint necesita.


-------------Instalador .exe

pyinstaller --name AdminReportes `
--onedir `
--windowed `
--icon="static/favicon.ico" `
--add-data "templates;templates" `
--add-data "static;static" `
--hidden-import="pyodbc" `
--hidden-import="pandas._libs.tslibs.timedeltas" `
--hidden-import="babel.numbers" `
--hidden-import="tkinter" `
--noconfirm `
run_app.py