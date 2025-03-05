import snap7
import mysql.connector
import xml.etree.ElementTree as ET
import time
import struct
import socket
import logging
import smtplib
from email.mime.text import MIMEText

# Načtení konfigurace z XML
CONFIG_FILE = "config.xml"
def load_config():
    tree = ET.parse(CONFIG_FILE)
    root = tree.getroot()
    return {
        "plc_ip": root.find(".//plc/ip").text,
        "plc_rack": int(root.find(".//plc/rack").text),
        "plc_slot": int(root.find(".//plc/slot").text),
        "db_energy": int(root.find(".//plc/db_energy").text),
        "offset_power": int(root.find(".//plc/offset_power").text),
        "offset_pf": int(root.find(".//plc/offset_pf").text),
        "db_turbine_state": int(root.find(".//plc/db_turbine_state").text),
        "offset_turbine_state": int(root.find(".//plc/offset_turbine_state").text),
        "bit_turbine_state": int(root.find(".//plc/bit_turbine_state").text),
        "db_turbine_power": int(root.find(".//plc/db_turbine_power").text),
        "offset_turbine_power": int(root.find(".//plc/offset_turbine_power").text),
        "power_limit_1": float(root.find(".//limits/power_limit_1").text),
        "power_limit_2": float(root.find(".//limits/power_limit_2").text),
        "limit_1_duration": int(root.find(".//limits/limit_1_duration").text),
        "limit_2_duration": int(root.find(".//limits/limit_2_duration").text),
        "plc_disconnect_time": int(root.find(".//limits/plc_disconnect_time").text),
        "mysql_host": root.find(".//mysql/host").text,
        "mysql_user": root.find(".//mysql/user").text,
        "mysql_password": root.find(".//mysql/password").text,
        "mysql_db": root.find(".//mysql/database").text,
        "raspberry_ip": root.find(".//raspberry/ip").text,
        "raspberry_port": int(root.find(".//raspberry/port").text),
        "log_file": root.find(".//logging/log_file").text,
        "smtp_server": root.find(".//email/smtp_server").text,
        "smtp_port": int(root.find(".//email/smtp_port").text),
        "smtp_user": root.find(".//email/smtp_user").text,
        "smtp_password": root.find(".//email/smtp_password").text,
        "recipient": root.find(".//email/recipient").text,
        "power_limit_warning_subject": root.find(".//email/power_limit_warning_subject").text,
        "power_limit_warning_body": root.find(".//email/power_limit_warning_body").text,
        "power_limit_panic_subject": root.find(".//email/power_limit_panic_subject").text,
        "power_limit_panic_body": root.find(".//email/power_limit_panic_body").text,
        "plc_disconnect_subject": root.find(".//email/plc_disconnect_subject").text,
        "plc_disconnect_body": root.find(".//email/plc_disconnect_body").text
    }

config = load_config()

# Nastavení logování
logging.basicConfig(filename=config["log_file"], level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# Funkce pro odesílání e-mailu
def send_email(subject, message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = config["smtp_user"]
        msg["To"] = config["recipient"]

        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["smtp_user"], config["smtp_password"])
        server.sendmail(config["smtp_user"], config["recipient"], msg.as_string())
        server.quit()
        logging.info(f"Email odeslán: {subject}")
    except Exception as e:
        logging.error(f"Chyba při odesílání emailu: {e}")

# Připojení k MySQL s automatickým opakováním
def connect_mysql():
    while True:
        try:
            conn = mysql.connector.connect(
                host=config["mysql_host"],
                user=config["mysql_user"],
                password=config["mysql_password"],
                database=config["mysql_db"]
            )
            return conn
        except Exception as e:
            logging.error(f"Chyba připojení k MySQL: {e}")
            send_email("Chyba MySQL", f"Nepodařilo se připojit k databázi na {config['mysql_host']}. Chyba: {e}")
            time.sleep(30)  # Opakování pokusu po 30 sekundách

# Připojení k PLC s automatickým opakováním
def connect_plc():
    plc = snap7.client.Client()
    while True:
        try:
            plc.connect(config["plc_ip"], config["plc_rack"], config["plc_slot"])
            logging.info("Připojeno k PLC")
            return plc
        except Exception as e:
            logging.error(f"Chyba připojení k PLC: {e}")
            send_email("Chyba připojení k PLC", f"Nepodařilo se připojit k PLC na {config['plc_ip']}. Chyba: {e}")
            time.sleep(30)

plc = connect_plc()

# Funkce pro čtení dat z PLC
def read_real_from_plc(db, offset):
    try:
        data = plc.db_read(db, offset, 4)
        return struct.unpack('>f', data)[0]
    except Exception as e:
        logging.error(f"Chyba při čtení REAL hodnoty z PLC: {e}")
        return None

def read_bool_from_plc(db, offset, bit):
    try:
        data = plc.db_read(db, offset, 1)
        return bool((data[0] >> bit) & 1)
    except Exception as e:
        logging.error(f"Chyba při čtení BOOL hodnoty: {e}")
        return None

# Hlavní smyčka
try:
    while True:
        power = read_real_from_plc(config["db_energy"], config["offset_power"]) / 1000
        turbine_power = read_real_from_plc(config["db_turbine_power"], config["offset_turbine_power"]) / 1000
        turbine_state = read_bool_from_plc(config["db_turbine_state"], config["offset_turbine_state"], config["bit_turbine_state"])
        
        if None not in (power, turbine_power, turbine_state):
            conn = connect_mysql()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO energie_real_time (kdy, hodnota, turbina, turbina_prikon) VALUES (NOW(), %s, %s, %s)",
                           (power, turbine_state, turbine_power))
            conn.commit()
            conn.close()
            logging.info(f"Data zapsána: {power} kW, Turbína: {turbine_state}, Výkon turbíny: {turbine_power} kW")
        
        time.sleep(60)

except KeyboardInterrupt:
    logging.info("Ukončování programu...")
    plc.disconnect()
