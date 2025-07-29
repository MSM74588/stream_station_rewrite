# app/task_config.py
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "task.yaml"

def load_tasks():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

TASKS = load_tasks()