import os
import mysql.connector
from mysql.connector import Error

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


def test_existing_connection():
    connection = None
    try:
        print("Attempting to connect using get_beat_connection()...")

        connection = get_beat_connection()

        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"✅ Success! Connected to MySQL Server version: {db_info}")
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            db_name = cursor.fetchone()[0]
            print(f"   Active database: {db_name}")
            cursor.close()

    except Error as e:
        print(f"❌ Connection failed: {e}")

    finally:
        if connection and connection.is_connected():
            connection.close()
            print("🔌 Connection safely closed.")


test_existing_connection()






