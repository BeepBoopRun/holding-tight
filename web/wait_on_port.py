import socket
import time
import sys


def wait_on_port(host, port, timeout=60, interval=1):
    end_time = time.time() + timeout

    while time.time() < end_time:
        try:
            with socket.create_connection((host, port), timeout=3):
                print(f"Socket {host}:{port} is ready!")
                return True
        except OSError:
            print(f"Waiting for {host}:{port}...")
            time.sleep(interval)

    raise TimeoutError(f"Socket {host}:{port} did not become ready in time")


if len(sys.argv) != 2:
    raise ValueError("Please supply only host:port as input!")

host, port = sys.argv[1].split(":")
wait_on_port(host, port)
