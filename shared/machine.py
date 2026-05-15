import os, platform
from wakeonlan import send_magic_packet

def get_status(ip):
    param = "-n 1" if platform.system().lower()=="windows" else "-c 1"
    return os.system(f"ping {param} {ip} > /dev/null 2>&1")==0

def wake_machine(mac):
    send_magic_packet(mac)
