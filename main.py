import subprocess
import sys
import time

def run_platform():
    username = "test"
    if not username:
        username = "default_user"

    python_path = sys.executable
    processes = []

    try:
        print("Starting medical platform services...")

        api_proc = subprocess.Popen([python_path, "site_api.py"])
        processes.append(api_proc)
        print("API service started on port 5000")

        server_proc = subprocess.Popen([python_path, "site_server.py"])
        processes.append(server_proc)
        print("Web server started on port 8080")

        esp_proc = subprocess.Popen([python_path, "esp_server.py", username])
        processes.append(esp_proc)
        print(f"ESP data collector started for user: {username}")

        print("System is active. Use Ctrl+C to stop all services.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping all services...")
        for p in processes:
            p.terminate()
        print("System halted.")

if __name__ == "__main__":
    run_platform()