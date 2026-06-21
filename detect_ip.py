"""Auto-detect local network IP address."""
import socket


def get_local_ip() -> str:
    """Detect the LAN IP this machine uses to reach the gateway."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    print(get_local_ip())
