import os
import mysql.connector

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SSL_CERT = os.path.join(BASE_DIR, "ca1.pem")



def get_beat_connection():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST_1"),
        port=int(os.getenv("DB_PORT_1")),
        user=os.getenv("DB_USER_1"),
        password=os.getenv("DB_PASSWORD_1"),
        database=os.getenv("DB_NAME_1"),
        ssl_ca=SSL_CERT
    )

    return connection







