; Script NSIS para Admin Reportes v1.000
; Desarrollado por Super System Code

!define PRODUCT_NAME "Admin Reportes"
!define PRODUCT_VERSION "1.000"
!define COMPANY_NAME "Super System Code"
!define INSTALL_SUBDIR "AdminReportes"
!define EXE_NAME "AdminReportes.exe"       ; Nombre del ejecutable de PyInstaller
!define LICENSE_FILE "license.dat"        ; Archivo de licencia requerido
!define OUTPUT_FILENAME "AdminReportes_Setup_v${PRODUCT_VERSION}.exe"
!define SOURCE_APP_DIR "dist\${PRODUCT_NAME}" ; Carpeta de salida de PyInstaller (--onedir)

; -------------------------------- Propiedades del Instalador --------------------------------
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "${OUTPUT_FILENAME}"
InstallDir "$PROGRAMFILES64\${COMPANY_NAME}\${INSTALL_SUBDIR}" ; Directorio por defecto (64 bits)
InstallDirRegKey HKLM "Software\${COMPANY_NAME}\${PRODUCT_NAME}" "Install_Dir"
RequestExecutionLevel admin ; Necesita permisos de administrador

; -------------------------------- Interfaz Gráfica (Modern UI 2) --------------------------------
!include "MUI2.nsh"

; --- Iconos y Logos (Opcional: Crea carpetas 'icons' y 'bitmaps' con tus archivos) ---
; Asegúrate de que estos archivos existan o comenta las líneas
!define MUI_ICON ".\icons\app_icon.ico"
!define MUI_UNICON ".\icons\app_unicon.ico"
;!define MUI_HEADERIMAGE ; Descomenta si usas imagen de cabecera
;!define MUI_HEADERIMAGE_BITMAP ".\bitmaps\header.bmp"
;!define MUI_WELCOMEFINISHPAGE_BITMAP ".\bitmaps\side.bmp" ; Descomenta si usas imagen lateral

; --- Páginas del Asistente ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE ".\license.txt" ; Asegúrate de tener este archivo
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE_NAME}" ; Opción para ejecutar al final
!define MUI_FINISHPAGE_RUN_TEXT "Ejecutar ${PRODUCT_NAME}"
!insertmacro MUI_PAGE_FINISH

; --- Páginas del Desinstalador ---
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; --- Idioma ---
!insertmacro MUI_LANGUAGE "Spanish"

; --- Información de Versión (para propiedades del archivo EXE) ---
VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "CompanyName" "${COMPANY_NAME}"
VIAddVersionKey "LegalCopyright" "© ${COMPANY_NAME}"
VIAddVersionKey "FileDescription" "Instalador de ${PRODUCT_NAME}"
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"

; ================================= Sección de Instalación =================================
Section "Instalar ${PRODUCT_NAME}" SEC_INSTALL
  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer ; No sobrescribir archivos más nuevos (útil para actualizaciones)

  ; --- COPIAR ARCHIVOS DE LA APLICACIÓN ---
  ; Copia todo desde la carpeta de PyInstaller
  ; Asegúrate de que la ruta ${SOURCE_APP_DIR} es correcta relativa a este script .nsi
  File /r "${SOURCE_APP_DIR}\*.*"

  ; --- COPIAR ARCHIVO DE LICENCIA ---
  ; Busca license.dat en la carpeta del instalador
  IfFileExists "$EXEDIR\${LICENSE_FILE}" LicenseFound NoLicense
LicenseFound:
  File "$EXEDIR\${LICENSE_FILE}"
  goto LicenseDone
NoLicense:
  MessageBox MB_ICONEXCLAMATION|MB_OK "¡Atención! No se encontró el archivo de licencia '${LICENSE_FILE}' junto al instalador. La aplicación no funcionará sin él."
LicenseDone:

  ; --- Crear carpetas adicionales ---
  CreateDirectory "$INSTDIR\uploads" ; Para logos de reportes

  ; --- Guardar ruta de instalación en el registro ---
  WriteRegStr HKLM "Software\${COMPANY_NAME}\${PRODUCT_NAME}" "Install_Dir" "$INSTDIR"

  ; --- Crear accesos directos en Menú Inicio ---
  CreateDirectory "$SMPROGRAMS\${COMPANY_NAME}"
  CreateShortCut "$SMPROGRAMS\${COMPANY_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${EXE_NAME}" "" "$INSTDIR\${EXE_NAME}" 0

  ; --- Escribir información del desinstalador ---
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME} (por ${COMPANY_NAME})"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "Publisher" "${COMPANY_NAME}"
  ; Opcional: Estimar tamaño (en KB)
  ; WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "EstimatedSize" 150000 ; Ejemplo: 150MB
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"

  MessageBox MB_ICONINFORMATION|MB_OK "${PRODUCT_NAME} se ha instalado correctamente."

SectionEnd

; ================================= Sección de Desinstalación =================================
Section "Uninstall" SEC_UNINSTALL
  ; --- Preguntar si se quieren mantener datos (opcional, por defecto elimina todo) ---
  ; MessageBox MB_YESNO|MB_ICONQUESTION "¿Desea mantener los archivos de configuración y datos (settings.db, uploads)? $\nSi elige 'No', se eliminarán todos los datos." IDYES KeepData

  ; --- Eliminar archivos y carpetas ---
  Delete "$INSTDIR\${LICENSE_FILE}" ; Eliminar licencia al desinstalar
  Delete "$INSTDIR\uninstall.exe"   ; El propio desinstalador
  Delete "$INSTDIR\settings.db"     ; Eliminar base de datos de configuración
  RMDir /r "$INSTDIR\uploads"       ; Eliminar logos subidos

; KeepData: ; Etiqueta para saltar la eliminación si el usuario elige 'Sí'

  ; Eliminar el resto de archivos y carpetas de la aplicación
  RMDir /r "$INSTDIR"

  ; --- Eliminar accesos directos ---
  Delete "$SMPROGRAMS\${COMPANY_NAME}\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${COMPANY_NAME}" ; Intenta eliminar la carpeta de la empresa si está vacía

  ; --- Eliminar claves del registro ---
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\${COMPANY_NAME}\${PRODUCT_NAME}"

  MessageBox MB_ICONINFORMATION|MB_OK "${PRODUCT_NAME} fue desinstalado correctamente."
SectionEnd
