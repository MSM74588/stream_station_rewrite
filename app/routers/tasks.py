from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.taskconfig import load_tasks
import subprocess
from datetime import datetime
from pathlib import Path


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


router = APIRouter()

class TaskRequest(BaseModel):
    task_name: str
    
@router.post("/taskrunner")
async def run_named_task(request: TaskRequest, background_tasks: BackgroundTasks):
    task_name = request.task_name
    tasks = load_tasks()

    if task_name not in tasks:
        raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found.")

    background_tasks.add_task(run_task, task_name, tasks[task_name])
    return {"status": "scheduled", "message": f"Task '{task_name}' has been started."}

@router.get("/taskrunner")
async def list_available_tasks():
    """
    Returns a dictionary of all available tasks and their associated command lists.
    """
    tasks = load_tasks()
    return {"available_tasks": tasks}


def run_task(task_name: str, commands: list[str]):
    log_path = LOG_DIR / f"task_{task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    with open(log_path, "a") as log_file:
        log_file.write(f"[{datetime.now()}] Starting task: {task_name}\n\n")

        for cmd in commands:
            log_file.write(f"Running command: {cmd}\n")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                log_file.write(result.stdout)
                log_file.write("\n")
                
                if result.returncode != 0:
                    log_file.write(f"Command failed with return code {result.returncode}\n")
                    break

            except Exception as e:
                log_file.write(f"Exception occurred: {str(e)}\n")
                break

        log_file.write(f"[{datetime.now()}] Task completed: {task_name}\n")