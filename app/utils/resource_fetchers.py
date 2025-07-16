import yaml
import socket
import os

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
    
def save_auth(data, auth_path):
    with open(auth_path, "w") as f:
        yaml.safe_dump(data, f)

def load_auth(auth_path):
    if not os.path.exists(auth_path):
        return None
    with open(auth_path, "r") as f:
        return yaml.safe_load(f)
    
def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Doesn't send data, just opens socket
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"