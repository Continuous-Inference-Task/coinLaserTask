#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bootstrap.py — Cross-platform bootstrap script for the CoIn Laser Task.

Automatically locates Python 3.10, installs uv (if missing), syncs dependencies
from uv.lock (deterministic), and runs wizard.py.

Requires Python 3.10 exactly — PsychoPy and psychtoolbox have
known issues with 3.11+.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------------------------ #
#  REQUIRED PYTHON VERSION                                           #
# ------------------------------------------------------------------ #
REQUIRED_MAJOR = 3
REQUIRED_MINOR = 10

PROJECT_ROOT = Path(__file__).resolve().parent


# ------------------------------------------------------------------ #
#  TERMINAL HELPERS (Unicode-safe on all platforms)                   #
# ------------------------------------------------------------------ #

def _safe_print(*args, **kwargs):
    """Print that won't crash on terminals with broken Unicode support (e.g. cmd.exe)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Replace fancy chars with ASCII fallbacks
        safe = []
        for a in args:
            if isinstance(a, str):
                a = a.replace("\u2713", "[OK]").replace("\u2717", "[FAIL]").replace("\u2192", "->")
            safe.append(a)
        print(*safe, **kwargs)


# ------------------------------------------------------------------ #
#  OS DETECTION                                                        #
# ------------------------------------------------------------------ #

def _detect_os() -> str:
    """Return 'linux', 'macos', or 'windows'."""
    if sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "macos"
    elif sys.platform in ("win32", "cygwin"):
        return "windows"
    return sys.platform


CURRENT_OS = _detect_os()


# ------------------------------------------------------------------ #
#  PYTHON-VERSION DISCOVERY                                           #
# ------------------------------------------------------------------ #

def _version_tuple(python_binary: str) -> tuple | None:
    """Return ``(major, minor)`` for a Python binary, or None on failure."""
    try:
        out = subprocess.run(
            [python_binary, "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return None
        parts = out.stdout.strip().split()
        if len(parts) >= 2:
            return (int(parts[0]), int(parts[1]))
        return None
    except Exception:
        return None


def _is_python_310(binary: str) -> bool:
    """True if *binary* is a Python 3.10.x interpreter."""
    v = _version_tuple(binary)
    return v is not None and v[0] == REQUIRED_MAJOR and v[1] == REQUIRED_MINOR


def _find_python310() -> str | None:
    """Search for a Python 3.10 binary on the system.

    Checks (in order):
    1. The currently running interpreter (if it happens to be 3.10).
    2. ``python3.10`` on PATH.
    3. ``python3`` on PATH.
    4. ``python`` on PATH.
    5. OS-specific common install locations (pyenv, Homebrew, framework,
       system, Windows installer, conda).

    Returns the path to a Python 3.10 binary, or None.
    """
    candidates: list[tuple[str, str, tuple | None]] = []

    # 1. Current interpreter
    if _is_python_310(sys.executable):
        return sys.executable

    # 2. Explicit python3.10 (works on all OSes if it's on PATH)
    python310 = shutil.which("python3.10")
    if python310 and _is_python_310(python310):
        return python310

    # 3-4. Generic names — record version for diagnostics
    for name in ("python3", "python"):
        path = shutil.which(name)
        if not path:
            continue
        if _is_python_310(path):
            return path
        candidates.append((name, path, _version_tuple(path)))

    # 5. OS-specific common install locations
    common_paths: list[Path] = []

    # Dynamic pyenv versions check (handles any 3.10.x folder, e.g. 3.10.20)
    pyenv_versions_dir = Path.home() / ".pyenv" / "versions"
    if pyenv_versions_dir.is_dir():
        for item in pyenv_versions_dir.iterdir():
            if item.is_dir() and item.name.startswith("3.10"):
                common_paths.append(item / "bin" / "python3.10")
                common_paths.append(item / "bin" / "python3")
                common_paths.append(item / "bin" / "python")

    if CURRENT_OS == "linux":
        common_paths.extend([
            # pyenv fallback
            Path.home() / ".pyenv" / "versions" / "3.10" / "bin" / "python3.10",
            Path.home() / ".pyenv" / "versions" / "3.10" / "bin" / "python3",
            Path.home() / ".pyenv" / "shims" / "python3.10",
            # deadsnakes PPA (Ubuntu)
            Path("/usr/bin/python3.10"),
            Path("/usr/local/bin/python3.10"),
            # conda / mamba
            Path.home() / "miniconda3" / "envs" / "coinlaser" / "bin" / "python",
            Path.home() / "anaconda3" / "envs" / "coinlaser" / "bin" / "python",
            Path.home() / "micromamba" / "envs" / "coinlaser" / "bin" / "python",
        ])
    elif CURRENT_OS == "macos":
        common_paths.extend([
            # pyenv fallback
            Path.home() / ".pyenv" / "versions" / "3.10" / "bin" / "python3.10",
            Path.home() / ".pyenv" / "versions" / "3.10" / "bin" / "python3",
            Path.home() / ".pyenv" / "shims" / "python3.10",
            # Homebrew (Apple Silicon)
            Path("/opt/homebrew/opt/python@3.10/bin/python3.10"),
            Path("/opt/homebrew/bin/python3.10"),
            # Homebrew (Intel)
            Path("/usr/local/opt/python@3.10/bin/python3.10"),
            Path("/usr/local/bin/python3.10"),
            # python.org framework install
            Path("/Library/Frameworks/Python.framework/Versions/3.10/bin/python3.10"),
            Path("/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"),
            # MacPorts
            Path("/opt/local/bin/python3.10"),
            # conda / mamba
            Path.home() / "miniconda3" / "envs" / "coinlaser" / "bin" / "python",
            Path.home() / "anaconda3" / "envs" / "coinlaser" / "bin" / "python",
        ])
    elif CURRENT_OS == "windows":
        common_paths.extend([
            # Windows Store / user install
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python310" / "python.exe",
            Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "python3.10.exe",
            # System-wide install
            Path("C:/Program Files/Python310/python.exe"),
            Path("C:/Python310/python.exe"),
            # conda / mamba (Windows)
            Path.home() / "miniconda3" / "envs" / "coinlaser" / "python.exe",
            Path.home() / "anaconda3" / "envs" / "coinlaser" / "python.exe",
        ])

    for p in common_paths:
        try:
            if p.exists() and _is_python_310(str(p)):
                return str(p)
        except OSError:
            continue  # permission error on some system paths

    # ── diagnostic message ──
    _safe_print("Could not find a Python 3.10 installation.")
    _safe_print()
    if candidates:
        _safe_print("Found the following, but they are not Python 3.10:")
        for name, path, ver in candidates:
            ver_str = ".".join(str(v) for v in ver) if ver else "unknown"
            _safe_print(f"  {name} ({path}) -> Python {ver_str}")
        _safe_print()

    if CURRENT_OS == "linux":
        _safe_print("To install Python 3.10:")
        _safe_print("  - Ubuntu/Debian:  sudo apt install python3.10 python3.10-venv")
        _safe_print("  - Fedora:         sudo dnf install python3.10")
        _safe_print("  - Arch:           yay -S python310")
        _safe_print("  - pyenv:          pyenv install 3.10 && pyenv local 3.10")
        _safe_print("  - conda:          conda create -n coinlaser python=3.10")
    elif CURRENT_OS == "macos":
        _safe_print("To install Python 3.10:")
        _safe_print("  - Homebrew:       brew install python@3.10")
        _safe_print("  - pyenv:          pyenv install 3.10 && pyenv local 3.10")
        _safe_print("  - conda:          conda create -n coinlaser python=3.10")
        _safe_print("  - python.org:    https://www.python.org/downloads/release/python-31011/")
    elif CURRENT_OS == "windows":
        _safe_print("To install Python 3.10:")
        _safe_print("  - winget:         winget install Python.Python.3.10")
        _safe_print("  - Direct:         https://www.python.org/downloads/release/python-31011/")
        _safe_print("  - conda:          conda create -n coinlaser python=3.10")
        _safe_print("                     (use the 64-bit Windows installer)")
    else:
        _safe_print("To install Python 3.10:")
        _safe_print("  - pyenv:          pyenv install 3.10 && pyenv local 3.10")
        _safe_print("  - conda:          conda create -n coinlaser python=3.10")
        _safe_print("  - Direct:         https://www.python.org/downloads/release/python-31011/")

    _safe_print()
    _safe_print("After installing, re-run:")
    _safe_print("  python bootstrap.py")
    return None


# ------------------------------------------------------------------ #
#  UV INSTALLATION                                                    #
# ------------------------------------------------------------------ #

def _which(cmd: str) -> str | None:
    """Return path to cmd if it exists on PATH, else None."""
    return shutil.which(cmd)


def _ensure_uv() -> None:
    """Ensure uv is installed. If not, install it via pipx, pip, or curl."""
    if _which("uv"):
        return  # uv already available

    _safe_print("uv not found. Installing uv (fast Python package manager)...")
    _safe_print()

    # Try pipx first (cleanest, isolated)
    if _which("pipx"):
        _safe_print("Installing via pipx...")
        try:
            subprocess.run(["pipx", "install", "uv"], check=True, capture_output=True)
            if _which("uv"):
                _safe_print("uv installed successfully via pipx.")
                return
        except subprocess.CalledProcessError:
            pass  # fall through to next method

    # Try pip install --user (works everywhere with Python)
    pip = _which("pip3") or _which("pip")
    if pip:
        _safe_print("Installing via pip ( --user )...")
        try:
            subprocess.run(
                [pip, "install", "--user", "uv"],
                check=True,
                capture_output=True,
            )
            # Check if ~/.local/bin is on PATH
            user_bin = Path.home() / ".local" / "bin"
            if user_bin.exists() and str(user_bin) not in os.environ.get("PATH", ""):
                _safe_print(f"WARNING: {user_bin} is not on your PATH.")
                _safe_print(f"  Add this to your shell profile: export PATH=\"{user_bin}:$PATH\"")
                _safe_print(f"  Or run: export PATH=\"{user_bin}:$PATH\" and try again.")
                sys.exit(1)
            if _which("uv"):
                _safe_print("uv installed successfully via pip.")
                return
        except subprocess.CalledProcessError:
            pass  # fall through to next method

    # Try curl (Unix-like systems)
    if CURRENT_OS in ("linux", "macos") and _which("curl"):
        _safe_print("Installing via curl...")
        try:
            subprocess.run(
                ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                check=True,
                shell=False,
            )
            # uv installs to ~/.cargo/bin or ~/.local/bin via the install script
            # The install script adds to PATH in shell profile, but not current session
            cargo_bin = Path.home() / ".cargo" / "bin"
            local_bin = Path.home() / ".local" / "bin"
            new_path = os.environ.get("PATH", "")
            if cargo_bin.exists():
                new_path = f"{cargo_bin}:{new_path}"
            if local_bin.exists():
                new_path = f"{local_bin}:{new_path}"
            os.environ["PATH"] = new_path
            if _which("uv"):
                _safe_print("uv installed successfully via curl.")
                return
        except subprocess.CalledProcessError:
            pass  # fall through to error

    # Try PowerShell (Windows)
    if CURRENT_OS == "windows" and _which("powershell"):
        _safe_print("Installing via PowerShell...")
        try:
            subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "ByPass",
                    "-c",
                    "irm https://astral.sh/uv/install.ps1 | iex",
                ],
                check=True,
                capture_output=True,
            )
            # uv installs to %USERPROFILE%\.cargo\bin
            cargo_bin = Path.home() / ".cargo" / "bin"
            if cargo_bin.exists():
                os.environ["PATH"] = f"{cargo_bin};{os.environ.get('PATH', '')}"
            if _which("uv"):
                _safe_print("uv installed successfully via PowerShell.")
                return
        except subprocess.CalledProcessError:
            pass  # fall through to error

    _safe_print("ERROR: Could not install uv automatically.")
    _safe_print()
    _safe_print("Please install uv manually:")
    _safe_print("  - curl:     curl -LsSf https://astral.sh/uv/install.sh | sh")
    _safe_print("  - pipx:     pipx install uv")
    _safe_print("  - pip:      pip install --user uv")
    _safe_print("  - Windows:  irm https://astral.sh/uv/install.ps1 | iex")
    _safe_print("  - More:     https://docs.astral.sh/uv/getting-started/installation/")
    sys.exit(1)


# ------------------------------------------------------------------ #
#  MAIN BOOTSTRAP                                                     #
# ------------------------------------------------------------------ #

def bootstrap():
    # ── Step 1: Locate Python 3.10 ──
    python310 = _find_python310()
    if python310 is None:
        sys.exit(1)

    py_ver = _version_tuple(python310)
    py_ver_str = ".".join(str(v) for v in py_ver) if py_ver else "unknown"
    _safe_print(f"Using Python {py_ver_str} at: {python310}")
    _safe_print()

    # ── Step 2: Ensure uv is installed ──
    _ensure_uv()
    _safe_print()

    # ── Step 3: Sync dependencies from lockfile ──
    _safe_print("Syncing dependencies from uv.lock (this may take a few minutes on first run)...")
    _safe_print()

    env = os.environ.copy()
    env["UV_PYTHON"] = python310

    try:
        result = subprocess.run(
            ["uv", "sync"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=False,
        )
        if result.returncode != 0:
            _safe_print()
            _safe_print("ERROR: Dependency sync failed.")
            _safe_print()
            _safe_print("Common fixes:")
            _safe_print("  - Check internet connection")
            if CURRENT_OS == "macos":
                _safe_print("  - On macOS: brew install portaudio  (required by sounddevice)")
            elif CURRENT_OS == "linux":
                _safe_print("  - On Ubuntu/Debian: sudo apt install portaudio19-dev python3.10-dev")
                _safe_print("  - On Arch/Manjaro:  sudo pacman -S portaudio")
            _safe_print("  - Try manually: uv sync")
            sys.exit(1)
    except FileNotFoundError:
        _safe_print("ERROR: uv command not found after installation.")
        _safe_print("  Try closing and reopening your terminal, or run: export PATH=\"$HOME/.local/bin:$HOME/.cargo/bin:$PATH\"")
        sys.exit(1)

    _safe_print()
    _safe_print("Dependencies synced successfully.")
    _safe_print()

    # ── Step 4: Delegate to wizard.py ──
    wizard_py = PROJECT_ROOT / "wizard.py"
    if not wizard_py.exists():
        _safe_print(f"ERROR: Could not find wizard.py at {wizard_py}")
        sys.exit(1)

    _safe_print("Launching wizard...")
    _safe_print()

    # ------------------------------------------------------------------ #
    #  LINUX: wxPython's bundled libwx_*.so is not on the loader's        #
    #  default search path. If a system-installed wxWidgets is also       #
    #  present, the loader will prefer the (often older/mismatched) one  #
    #  in /usr/lib, causing undefined-symbol errors when importing wx.   #
    #  Pointing LD_LIBRARY_PATH at the venv's bundled libs fixes it.      #
    #  This is a no-op on macOS and Windows.                              #
    # ------------------------------------------------------------------ #
    if CURRENT_OS == "linux":
        venv_wx_dir = PROJECT_ROOT / ".venv" / "lib" / f"python{REQUIRED_MAJOR}.{REQUIRED_MINOR}" / "site-packages" / "wx"
        if venv_wx_dir.is_dir():
            env["LD_LIBRARY_PATH"] = f"{venv_wx_dir}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"

    try:
        result = subprocess.run(
            ["uv", "run", "python", str(wizard_py)] + sys.argv[1:],
            cwd=PROJECT_ROOT,
            env=env,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        _safe_print()
        _safe_print("Setup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    bootstrap()
