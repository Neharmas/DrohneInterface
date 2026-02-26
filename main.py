import sys
from pathlib import Path
import os
import json
import time
import socket, struct
import cv2

def establish_connection(HOST, PORT, socket):
    if ":" in HOST:
        IP, PORT = str(HOST.split(":")[0]), int(HOST.split(":")[1])
        print(f"Verbindung wird zu {HOST} aufgebaut...")
        socket.connect((IP, PORT))
    else:
        print(f"Verbindung wird zu {HOST}:{PORT} aufgebaut...")
        socket.connect((HOST, PORT))

    socket.setblocking(True)
    print("Verbindung aufgestellt!")

def get_coordinates():
        data = ""
        i2o_path = os.path.join(os.path.expanduser("~"), "brain", "i2o")

        fov_path = os.path.join(i2o_path, "sichtfeld.json")
        with open(fov_path) as f:
            data = json.load(f)

        marker_path = os.path.join(i2o_path, "marker.json")
        with open(marker_path) as f:
            data.update(json.load(f))

        xyz_path = os.path.join(i2o_path, "xyz.json")
        with open(xyz_path) as f:
            data.update(json.load(f))

        return data

def get_img():
    img_path = os.path.join(os.path.expanduser("~"), "LIVE")

    files = [
        f for f in os.listdir(img_path)
        if f.lower().endswith(".jpg")
    ]

    if len(files) < 2:
        return None

    files = sorted(files)
    second_latest = files[-2]
    data = cv2.imread(os.path.join(img_path, second_latest))
    if data is None:
        return None

    return data

def send_json(socket, data):
    msg = json.dumps(data).encode("utf-8")
    header = struct.pack(">BI", 0x02, len(msg))
    socket.sendall(header + msg)

def send_frame(socket, img):
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        print("Bild konnte nicht enkodiert werden")
        return

    img_bytes = encoded.tobytes()

    header = struct.pack(">BI", 0x01, len(img_bytes))
    socket.sendall(header + img_bytes)

def reset_input():
    input_path = Path.home() / "input" / "input.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)

    default_data = {
        "move_z": 0,
        "move_y": 0,
        "move_x": 0,
        "rotate": 0,
        "look_x": 0,
        "look_y": 0,
        "zoom": 3
    }

    with input_path.open("w", encoding="utf-8") as f:
        json.dump(default_data, f, ensure_ascii=False, indent=4)

tasks = [
    {"func": get_coordinates, "interval": 1/20, "last": 0},
    {"func": get_img, "interval": 1/30, "last": 0}
]

RECONNECT_DELAY = 3.0

def main(HOST, PORT=8080):
    recv_buffer = ""
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
                                elif t["func"] == get_img:
                                    send_frame(s, data)
                            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                                print(f"Verbindung beim Übertragen abgebrochen: {e}")
                                running = False
                                break
                            t["last"] = now

                    # Check for incoming controller messages
                    try:
                        msg = s.recv(1024)
                        if msg:
                            recv_buffer += msg.decode("utf-8")

                            while "\n" in recv_buffer:
                                line, recv_buffer = recv_buffer.split("\n", 1)

                                if not line.strip():
                                    continue

                                try:
                                    data = json.loads(line)
                                except json.JSONDecodeError as e:
                                    print(f"JSON Decode Fehler (unvollständig?): {e}")
                                    continue

                                input_path = Path.home() / "input" / "input.json"
                                input_path.parent.mkdir(parents=True, exist_ok=True)

                                with input_path.open("w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False, indent=4)

                        else:
                            reset_input()
                            raise ConnectionResetError("Host hat die Verbindung aufgelöst")

                    except BlockingIOError:
                        reset_input()
                    except ConnectionResetError as e:
                        print(f"Verbindung verloren: {e}")
                        reset_input()
                        running = False

                    time.sleep(0.01)  # avoid 100% CPU

        except (ConnectionRefusedError, TimeoutError) as e:
            print(f"Verbindung konnte nicht zum Host aufgestellt werden: {e}")
            reset_input()
        except KeyboardInterrupt:
            print("Vom Nutzer unterbrochen — abbrechen")
            reset_input()
            break
        except Exception as e:
            print(f"Unerwartete Fehlmeldung: {e}")
            reset_input()
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
