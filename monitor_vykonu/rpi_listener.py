import socket
import RPi.GPIO as GPIO

# Konfigurace Raspberry Pi
HOST = "0.0.0.0"  # Nasloucháme na všech rozhraních
PORT = 5000        # Port pro příjem dat
BUZZER_PIN = 18    # GPIO pin pro akci

# Nastavení GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.LOW)

def handle_client(connection):
    try:
        data = connection.recv(1)
        if not data:
            return
        
        bool_value = bool(int(data.decode()))
        print(f"Přijatá BOOL hodnota: {bool_value}")
        
        # Aktivace GPIO podle hodnoty
        if bool_value:
            GPIO.output(BUZZER_PIN, GPIO.HIGH)
            print("Bzučák zapnut!")
        else:
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            print("Bzučák vypnut!")
    except Exception as e:
        print(f"Chyba při zpracování dat: {e}")
    finally:
        connection.close()

# TCP server pro příjem dat
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"Raspberry naslouchá na portu {PORT}...")
    
    while True:
        conn, addr = server.accept()
        print(f"Připojení z {addr}")
        handle_client(conn)
