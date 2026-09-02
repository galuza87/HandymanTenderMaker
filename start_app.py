import urllib.request
import urllib.error
import json
import sys
import subprocess
import os
import time

def check_lm_studio():
    """Checks if LM Studio is running and has a model loaded on port 1234."""
    url = "http://localhost:1234/api/v1/models"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                # Check if any model has loaded_instances
                is_loaded = False
                for model in data.get("models", []):
                    if model.get("loaded_instances") and len(model["loaded_instances"]) > 0:
                        is_loaded = True
                        break
                
                if is_loaded:
                    return True, "LM Studio is running and a model is loaded."
                else:
                    return False, "LM Studio is running, but NO MODEL IS LOADED. Please load a model in LM Studio."
            else:
                return False, f"Unexpected response status: {response.status}"
    except urllib.error.URLError:
        return False, "LM Studio not running. Please start the local server in LM Studio on port 1234."
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
    
    # Initialize processes as None
    backend_process = None
    frontend_process = None
    
    # Smartly resolve the correct python executable
    venv_python = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python) and sys.prefix == sys.base_prefix:
        python_exe = venv_python
        print(f"-> Auto-detected .venv. Using: {python_exe}")
    else:
        python_exe = sys.executable
        print(f"-> Using Python executable: {python_exe}")
    
    try:
        # Start the Python backend using the resolved executable from project root
        # This allows imports like "from backend.bootstrap" to work correctly
        print("Starting backend...")
        backend_process = subprocess.Popen(
            [python_exe, "-m", "backend.main"],
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("-> Backend started (backend.main)")
        time.sleep(2)  # Give backend time to start
        
        # Start the React frontend
        print("Starting frontend...")
        frontend_process = subprocess.Popen(
            "npm run dev",
            cwd=frontend_dir,
            shell=True
        )
        print("-> Frontend started (npm run dev)")
        time.sleep(3)  # Give frontend time to start
        
        print("\n✅ Both servers are running:")
        print("   - Frontend App: http://localhost:5173")
        print("   - API Docs: http://localhost:8000/docs (test endpoints here)")
        print("\nPress Ctrl+C to stop both.")
        
        # Keep the main script alive to monitor the sub-processes
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping servers...")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
