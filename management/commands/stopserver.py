import subprocess
import sys
import os

def run():
    """Stop the FastAPI development server running on port 8000"""
    try:
        # Find processes using port 8000
        result = subprocess.run(
            ["lsof", "-ti:8000"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} process(es) using port 8000")
            
            # Kill each process
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(["kill", "-9", pid.strip()], check=True)
                        print(f"Killed process {pid.strip()}")
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to kill process {pid.strip()}: {e}")
            
            print("Server stopped successfully")
        else:
            print("No processes found running on port 8000")
            
    except FileNotFoundError:
        print("Error: 'lsof' command not found. This script requires lsof to be installed.")
        sys.exit(1)
    except Exception as e:
        print(f"Error stopping server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()