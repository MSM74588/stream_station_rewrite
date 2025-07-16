import shutil
import os
from ..constants import REQUIRED_EXECUTABLES

def check_dependencies():
    missing = [exe for exe in REQUIRED_EXECUTABLES if shutil.which(exe) is None]
    if missing:
        print(f"❌ Missing required dependencies: {', '.join(missing)}")
        os._exit(1)
    print("✅ All required dependencies are present.")