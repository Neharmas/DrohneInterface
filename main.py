import sys
import os
import json
import time
import socket, struct

def establish_connection(HOST, PORT, socket):
    if ":" in HOST:
        IP, PORT = str(HOST.split(":")[0]), int(HOST.split(":")[1])
        print(f"Verbindung wird zu {HOST} aufgebaut...")
        socket.connect((IP, PORT))
    else:
        print(f"Verbindung wird zu {HOST}:{PORT} aufgebaut...")
        socket.connect((HOST, PORT))

    socket.setblocking(False)
    print("Verbindung aufgestellt!")

def get_coordinates():
        data = ""
        path = os.path.join(os.path.expanduser("~"), "brain", "i2o", "bodenpunkte.json")
        with open(path) as f:
                for x in f:
                        data += str(x)
        return json.loads(data)

tasks = [
    {"func": get_coordinates, "interval": 1/20, "last": 0}
]

def send_json(socket, data):
    msg = json.dumps(data).encode("utf-8")
    header = struct.pack(">BI", 0x02, len(msg))
    socket.sendall(header + msg)

def send_frame(socket, img_bytes):
    header = struct.pack(">BI", 0x01, len(img_bytes))
    socket.sendall(header + img_bytes)

RECONNECT_DELAY = 3.0  # Sekunden warten vor erneutem Versuch

def main(HOST, PORT=8080):
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                establish_connection(HOST, PORT, s)

                running = True
                while running:
                    now = time.perf_counter()
                    for t in tasks:
                        if now - t["last"] >= t["interval"]:
                            try:
                                data = t["func"]()
                                if t["func"] == get_coordinates:
                                    send_json(s, data)
                            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                                print(f"Verbindung beim Übertragen abgebrochen: {e}")
                                running = False
                                break
                            t["last"] = now

                    # --- Check for incoming controller messages ---
                    try:
                        msg = s.recv(1024)
                        if msg:
                            # handle or print controller message if needed
                            pass
                        else:
                            # No data means connection closed by host
                            raise ConnectionResetError("Host hat die Verbindung aufgelöst")
                    except BlockingIOError:
                        # no data available (normal in non-blocking mode)
                        pass
                    except ConnectionResetError as e:
                        print(f"Verbindung verloren: {e}")
                        running = False

                    time.sleep(0.01)  # avoid 100% CPU

        except (ConnectionRefusedError, TimeoutError) as e:
            print(f"Verbindung konnte nicht zum Host aufgestellt werden: {e}")
        except KeyboardInterrupt:
            print("Vom Nutzer unterbrochen — abbrechen")
            break
        except Exception as e:
            print(f"Unerwartete Fehlmeldung: {e}")

        print(f"Verbindung wird wieder aufgestellt in {RECONNECT_DELAY} s...")
        time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(sys.argv[1], int(sys.argv[2]))
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        HOST = input("Geben Sie die IP-Adresse des Controllers ein: ")
        main(HOST)
