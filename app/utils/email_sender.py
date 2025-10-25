import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import uuid # Para CIDs únicos si no se proporcionan

def send_email(smtp_config, recipients, cc, subject, body, is_html=False, attachment=None, images=None):
    """
    Envía un correo electrónico, soportando adjuntos normales y/o imágenes embebidas (CID).

    Args:
        smtp_config (dict): Configuración SMTP {'smtp_server', 'smtp_port', 'smtp_user', 'smtp_password'}.
        recipients (list): Lista de destinatarios principales ['email1', 'email2'].
        cc (list): Lista de destinatarios en copia ['cc1', 'cc2'].
        subject (str): Asunto.
        body (str): Cuerpo del mensaje (texto plano o HTML).
        is_html (bool): True si el cuerpo es HTML.
        attachment (tuple, optional): (filename, mimetype, content_bytes) para adjunto normal.
        images (list, optional): Lista de tuplas [(cid, image_bytes), ...] para imágenes embebidas.
                                 'cid' debe ser único (ej: 'chart_30_days_id').
    """
    valid_recipients = [r for r in recipients if r and '@' in r] # Simple validación
    valid_cc = [c for c in cc if c and '@' in c]
    if not valid_recipients:
        print("  -> Correo no enviado: No hay destinatarios válidos.")
        return

    # Estructura principal: 'mixed' si hay adjuntos, 'related' si solo hay imágenes embebidas, 'alternative' si solo HTML/texto
    if attachment:
        msg_root = MIMEMultipart('mixed')
    elif images:
        msg_root = MIMEMultipart('related')
        # Si hay imágenes, necesitamos una parte 'alternative' DENTRO de 'related' para el cuerpo HTML
        msg_body_container = MIMEMultipart('alternative')
        msg_root.attach(msg_body_container)
    else: # Solo texto o HTML simple
        msg_root = MIMEMultipart('alternative')
        msg_body_container = msg_root # El cuerpo va directamente aquí

    # Configurar cabeceras
    msg_root['From'] = smtp_config.get('smtp_user', '')
    msg_root['To'] = ", ".join(valid_recipients)
    if valid_cc:
        msg_root['Cc'] = ", ".join(valid_cc)
    msg_root['Subject'] = subject
    # Es buena práctica añadir Message-ID
    msg_root['Message-ID'] = smtplib.email.utils.make_msgid()

    # Preparar el cuerpo del mensaje
    body_type = 'html' if is_html else 'plain'
    body_part = MIMEText(body, body_type, 'utf-8')

    # Adjuntar el cuerpo
    if images or not attachment: # Si hay imágenes o solo cuerpo, va en 'alternative' o raíz si es 'alternative'
        msg_body_container.attach(body_part)
    else: # Si hay adjunto normal pero no imágenes, va directamente en 'mixed'
        msg_root.attach(body_part)


    # Adjuntar imágenes embebidas (si existen) a la parte 'related' (msg_root si images=True)
    if images:
        for cid, img_bytes in images:
            if img_bytes:
                try:
                    img = MIMEImage(img_bytes)
                    img.add_header('Content-ID', f'<{cid}>')
                    img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
                    msg_root.attach(img) # Adjuntar al nivel 'related'
                except Exception as img_e:
                     print(f"WARN: No se pudo adjuntar imagen embebida con CID '{cid}': {img_e}")


    # Adjuntar archivo normal (si existe) al nivel principal ('mixed' o 'related')
    if attachment:
        filename, mimetype, content_bytes = attachment
        if content_bytes:
            main_type, sub_type = mimetype.split('/', 1) if mimetype and '/' in mimetype else ('application', 'octet-stream')
            part = MIMEBase(main_type, sub_type)
            part.set_payload(content_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
            msg_root.attach(part) # Adjuntar al nivel raíz

    all_recipients = valid_recipients + valid_cc

    # Conectar y enviar
    server = None
    try:
        smtp_server = smtp_config.get('smtp_server')
        smtp_port = smtp_config.get('smtp_port')
        smtp_user = smtp_config.get('smtp_user')
        smtp_password = smtp_config.get('smtp_password')

        if not smtp_server or not smtp_port or not smtp_user:
             raise ValueError("Configuración SMTP incompleta (servidor, puerto o usuario faltante)")

        print(f"  -> Conectando a SMTP: {smtp_server}:{smtp_port}")
        # Decidir si usar SMTP_SSL (puerto 465) o SMTP con STARTTLS (normalmente 587 o 25)
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
            print("  -> Usando SMTP_SSL.")
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
            server.ehlo()
            server.starttls()
            server.ehlo()
            print("  -> Usando STARTTLS.")

        # Autenticación (si se proporcionó contraseña)
        if smtp_password:
             print(f"  -> Autenticando como {smtp_user}...")
             server.login(smtp_user, smtp_password)
             print("  -> Autenticación exitosa.")
        else:
             print("  -> Intentando enviar sin autenticación explícita (contraseña no proporcionada).")

        print(f"  -> Enviando correo a: {', '.join(all_recipients)}")
        server.sendmail(smtp_user, all_recipients, msg_root.as_string())
        print(f"  -> Correo enviado.")
    except smtplib.SMTPAuthenticationError as auth_e:
         print(f"  -> ERROR de autenticación SMTP: {auth_e}")
         raise ConnectionRefusedError(f"Autenticación fallida para {smtp_user}. Verifica usuario/contraseña.") from auth_e
    except Exception as e:
        print(f"  -> ERROR al enviar correo: {type(e).__name__} - {e}")
        # Imprimir traceback para más detalles en el log del servidor
        import traceback
        traceback.print_exc()
        raise e # Relanzar para que la tarea lo capture
    finally:
        if server:
            try:
                server.quit()
                print("  -> Conexión SMTP cerrada.")
            except Exception as quit_e:
                print(f"  -> Error al cerrar conexión SMTP: {quit_e}")

