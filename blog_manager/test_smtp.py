import os
import smtplib
from email.mime.text import MIMEText

# Carica variabili d'ambiente dal file .env se necessario
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 465))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")
TO_EMAIL = EMAIL_HOST_USER  # o altro destinatario

msg = MIMEText("Test SMTP da script Python")
msg["Subject"] = "Test SMTP"
msg["From"] = DEFAULT_FROM_EMAIL
msg["To"] = TO_EMAIL

try:
    with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.sendmail(DEFAULT_FROM_EMAIL, [TO_EMAIL], msg.as_string())
    print("Email inviata con successo!")
except Exception as e:
    print(f"Errore invio email: {e}")
