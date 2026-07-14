import urllib.request
import urllib.error
import json
import sys
import subprocess
import os
import time

def check_lm_studio():
    """Checks if LM Studio is running and has a model loaded on port 1234."""
    url = "http://localhost:1234/v1/models"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                # If the 'data' array has elements, a model is loaded.
                if data.get("data") and len(data["data"]) > 0:
                    return True, "LM Studio is running and model is loaded."
                else:
                    return False, "LM studio not running / model is not loaded"
            else:
                return False, f"Unexpected response status: {response.status}"
    except urllib.error.URLError:
        return False, "LM studio not running / model is not loaded"
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print("Checking LM Studio status...")
    is_ready, message = check_lm_studio()
    
    if not is_ready:
        print(f"Error: {message}")
        sys.exit(1)
        
    print(f"Success: {message}")
    print("Starting backend and frontend...\n")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    
    # Smartly resolve the correct python executable
    venv_python = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python) and sys.prefix == sys.base_prefix:
        python_exe = venv_python
        print(f"-> Auto-detected .venv. Using: {python_exe}")
    else:
        python_exe = sys.executable
        print(f"-> Using Python executable: {python_exe}")
    
    try:
        # Start the Python backend using the resolved executable
        backend_process = subprocess.Popen(
            [python_exe, "main.py"],
            cwd=backend_dir
        )
        print("-> Backend started (main.py)")
        
        # Start the React frontend
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            shell=True
        )
        print("-> Frontend started (npm run dev)")
        
        print("\nBoth servers are running. Press Ctrl+C to stop both.")
        
        # Keep the main script alive to monitor the sub-processes
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping servers...")
        backend_process.terminate()
        frontend_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
