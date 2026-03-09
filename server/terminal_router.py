from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess
import os
import platform

router = APIRouter()

# Strict allowlist of commands
ALLOWED_TASKS = {
    "START_MONITOR": ["airmon-ng", "start", "wlan0"],
    "STOP_MONITOR": ["airmon-ng", "stop", "wlan0mon"],
    "RESTART_BACKEND": ["systemctl", "restart", "phantomscan"],
    "VIEW_LOGS": ["tail", "-n", "50", "/var/log/phantomscan.log"],
    "CHECK_WIFI": ["iwconfig"],
}

class TaskRequest(BaseModel):
    task: str

@router.post("/execute-task")
async def execute_task(req: TaskRequest):
    if req.task not in ALLOWED_TASKS:
        raise HTTPException(status_code=400, detail=f"Task '{req.task}' is not allowed.")
    
    cmd_args = ALLOWED_TASKS[req.task]
    
    try:
        # shell=False is critical to prevent injection vulnerabilities
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            shell=False,
            # timeout=10 # Optional safety timeout
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
            
        return {
            "status": "success",
            "task": req.task,
            "os": platform.system(),
            "output": output or "Command executed with no output."
        }
    except FileNotFoundError:
        # Expected if the executable is not in PATH (e.g., custom Linux distros missing airmon-ng)
        raise HTTPException(status_code=500, detail=f"Executable '{cmd_args[0]}' not found on host.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")

# To mount this in your main.py:
# from terminal_router import router as terminal_router
# app.include_router(terminal_router, prefix="/api/v1/system")
