#!/usr/bin/env python3
"""
run.py — Cross-platform bootstrap script for the CoIn Laser Task.
Automatically creates a virtual environment, installs dependencies, and runs setup.py.
"""
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def bootstrap():
    venv_dir = PROJECT_ROOT / "stw"
    
    # 1. Resolve paths based on platform
    if os.name == "nt":  # Windows
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:  # macOS / Linux
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"

    # 2. Create virtual environment if it doesn't exist
    if not venv_dir.is_dir():
        print(f"Creating virtual environment in '{venv_dir.name}'...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            print("✓ Virtual environment created.")
        except subprocess.CalledProcessError as e:
            print(f"Error creating virtual environment: {e}")
            sys.exit(1)

    # 3. Install/upgrade dependencies if not done yet
    marker_file = venv_dir / ".setup_done"
    if not marker_file.exists():
        print("Installing dependencies from requirements.txt (this may take a minute)...")
        try:
            # Upgrade pip first
            subprocess.run([str(pip_exe), "install", "--upgrade", "pip"], check=True)
            # Install requirements
            subprocess.run([str(pip_exe), "install", "-r", str(PROJECT_ROOT / "requirements.txt")], check=True)
            marker_file.touch()
            print("✓ Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            sys.exit(1)

    # 4. Delegate to setup.py using the venv interpreter
    setup_py = PROJECT_ROOT / "setup.py"
    if not setup_py.exists():
        print(f"Error: Could not find setup.py at {setup_py}")
        sys.exit(1)

    cmd = [str(python_exe), str(setup_py)] + sys.argv[1:]
    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(1)

if __name__ == "__main__":
    bootstrap()
