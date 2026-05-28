#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py — Cross-platform bootstrap script for the CoIn Laser Task.

Automatically locates Python 3.10, creates a virtual environment,
installs dependencies via **uv** (fast Rust-based package manager,
with pip fallback), and runs setup.py.

On Linux, wxPython has no pre-built PyPI wheels, so a source build
would take 30-60 minutes.  This script tries pre-built wheels from
the wxPython extras server first, falling back to source only when
necessary.

Requires Python 3.10 exactly — PsychoPy and psychtoolbox have
known issues with 3.11+.
"""
from __future__ import annotations

import hashlib
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
VENV_DIR = PROJECT_ROOT / "stw"


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

    if CURRENT_OS == "linux":
        common_paths = [
            # pyenv
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
        ]
    elif CURRENT_OS == "macos":
        common_paths = [
            # pyenv
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
        ]
    elif CURRENT_OS == "windows":
        common_paths = [
            # Windows Store / user install
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python310" / "python.exe",
            Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "python3.10.exe",
            # System-wide install
            Path("C:/Program Files/Python310/python.exe"),
            Path("C:/Python310/python.exe"),
            # conda / mamba (Windows)
            Path.home() / "miniconda3" / "envs" / "coinlaser" / "python.exe",
            Path.home() / "anaconda3" / "envs" / "coinlaser" / "python.exe",
        ]

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
    _safe_print("  python run.py")
    return None


# ------------------------------------------------------------------ #
#  VENV HELPERS                                                       #
# ------------------------------------------------------------------ #

def _resolve_venv_paths(venv_dir: Path) -> tuple[Path, Path]:
    """Return ``(python_exe, pip_exe)`` for the given venv directory."""
    if CURRENT_OS == "windows":
        return (
            venv_dir / "Scripts" / "python.exe",
            venv_dir / "Scripts" / "pip.exe",
        )
    return (
        venv_dir / "bin" / "python",
        venv_dir / "bin" / "pip",
    )


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file, or '' if it doesn't exist."""
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _needs_reinstall(marker_file: Path, requirements_txt: Path) -> bool:
    """True if dependencies need (re)installing.

    Conditions:
    - ``.setup_done`` marker is missing.
    - ``requirements.txt`` was modified since last install.
    - The marker file's version tag doesn't match REQUIRED_MINOR.
    """
    if not marker_file.exists():
        return True

    try:
        content = marker_file.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return True

    # Line 0: requirements hash, Line 1: python version tag
    req_hash = content[0] if len(content) > 0 else ""
    py_tag = content[1] if len(content) > 1 else ""
    current_hash = _hash_file(requirements_txt)

    if current_hash and current_hash != req_hash:
        return True
    if py_tag != f"{REQUIRED_MAJOR}.{REQUIRED_MINOR}":
        return True
    return False


# ------------------------------------------------------------------ #
#  UV PACKAGE MANAGER                                                 #
# ------------------------------------------------------------------ #

def _ensure_uv(python_exe: Path) -> bool:
    """Install uv into the virtual environment.  Returns True on success."""
    _safe_print("Installing uv (fast package manager) ...")
    try:
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "--upgrade", "uv"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        _safe_print("  (uv install failed — falling back to pip)")
        return False


# ------------------------------------------------------------------ #
#  wxPython LINUX EXTRAS                                              #
# ------------------------------------------------------------------ #

# Pre-built wxPython wheels for Linux are NOT on PyPI.
# The wxPython project publishes Ubuntu-tagged wheels at:
#   https://extras.wxpython.org/wxPython4/extras/linux/gtk3/<ubuntu-ver>/
# These use the ``linux_x86_64`` platform tag and work on any Linux
# distro with a glibc version >= the one the wheel was built against.
# We try the newest Ubuntu version first (higher glibc), then older.
_WXPYTHON_EXTRAS_URLS_LINUX = [
    "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04",
    "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04",
]


def _install_dependencies(
    python_exe: Path,
    requirements_txt: Path,
    use_uv: bool,
) -> None:
    """Install dependencies, with special handling for wxPython on Linux.

    On Linux, wxPython has no pre-built wheels on PyPI.  We first try
    the wxPython extras server (Ubuntu-tagged wheels that work on any
    distro with new-enough glibc).  If no compatible wheel is found, we
    fall back to a source build with a clear warning about the wait.

    On macOS / Windows, wxPython wheels are on PyPI, so no special
    handling is needed.
    """
    pkg_runner = (
        [str(python_exe), "-m", "uv", "pip"]
        if use_uv
        else [str(python_exe), "-m", "pip"]
    )

    # ── Linux: try pre-built wxPython wheels first ──
    if CURRENT_OS == "linux":
        for url in _WXPYTHON_EXTRAS_URLS_LINUX:
            _safe_print(f"  Trying pre-built wxPython wheel: {url}")
            cmd = pkg_runner + [
                "install",
                "--find-links", url,
                "--only-binary", "wxPython",
                "-r", str(requirements_txt),
            ]
            result = subprocess.run(cmd)
            if result.returncode == 0:
                return  # installed from pre-built wheel
            _safe_print(f"  No compatible wheel found at {url}")

        # No pre-built wheel available — fall back to source build
        _safe_print()
        _safe_print("  ────────────────────────────────────────────────────")
        _safe_print("  WARNING: No pre-built wxPython wheel found for Linux.")
        _safe_print("  Falling back to SOURCE BUILD — this takes 30-60 min.")
        _safe_print("  To avoid this in future, see:")
        _safe_print("    https://wxpython.org/pages/downloads/")
        _safe_print("  ────────────────────────────────────────────────────")
        _safe_print()

    # ── Standard install ──
    # macOS / Windows: PyPI wheels for wxPython exist → fast.
    # Linux fallback: removes --only-binary so source build is allowed.
    cmd = pkg_runner + ["install", "-r", str(requirements_txt)]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        _safe_print()
        _safe_print(f"ERROR: Dependency installation failed: {e}")
        _safe_print()
        _safe_print("Common fixes:")
        _safe_print("  - Check internet connection")
        if CURRENT_OS == "macos":
            _safe_print("  - On macOS: brew install portaudio  (required by sounddevice)")
        elif CURRENT_OS == "linux":
            _safe_print("  - On Ubuntu/Debian: sudo apt install portaudio19-dev python3.10-dev")
            _safe_print("  - On Arch/Manjaro:  sudo pacman -S portaudio")
        pkg_mgr = "uv pip" if use_uv else "pip"
        _safe_print(
            f"  - Try manually: {python_exe} -m {pkg_mgr} install"
            f" -r requirements.txt"
        )
        sys.exit(1)


# ------------------------------------------------------------------ #
#  MAIN BOOTSTRAP                                                     #
# ------------------------------------------------------------------ #

def bootstrap():
    # ── Step 0: Locate Python 3.10 ──
    python310 = _find_python310()
    if python310 is None:
        sys.exit(1)

    py_ver = _version_tuple(python310)
    py_ver_str = ".".join(str(v) for v in py_ver) if py_ver else "unknown"
    _safe_print(f"Using Python {py_ver_str} at: {python310}")
    _safe_print()

    # ── Step 1: Resolve venv paths ──
    python_exe, pip_exe = _resolve_venv_paths(VENV_DIR)

    # ── Step 2: Handle existing venv ──
    if VENV_DIR.is_dir():
        venv_ver = _version_tuple(str(python_exe))
        if venv_ver is None:
            _safe_print(f"ERROR: Virtual environment at {VENV_DIR} appears broken.")
            _safe_print(f"  Delete it and re-run:  rm -rf {VENV_DIR.name}/")
            if CURRENT_OS == "windows":
                _safe_print(f"  On Windows:            rmdir /s {VENV_DIR.name}")
            sys.exit(1)

        if venv_ver[0] != REQUIRED_MAJOR or venv_ver[1] != REQUIRED_MINOR:
            _safe_print(
                f"  The existing '{VENV_DIR.name}/' virtual environment "
                f"was created with Python {venv_ver[0]}.{venv_ver[1]}, "
                f"but this project requires {REQUIRED_MAJOR}.{REQUIRED_MINOR}."
            )
            _safe_print()
            # Try to auto-remove and recreate
            if sys.stdin.isatty():
                try:
                    answer = input(
                        f"  Delete '{VENV_DIR.name}/' and recreate? [Y/n] "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = "y"
            else:
                answer = "y"  # non-interactive: auto-recreate
            if answer in ("", "y", "yes"):
                _safe_print(f"  Removing old '{VENV_DIR.name}/' ...")
                try:
                    if CURRENT_OS == "windows":
                        subprocess.run(
                            ["cmd", "/c", "rmdir", "/s", "/q", str(VENV_DIR)],
                            check=False,
                        )
                    else:
                        shutil.rmtree(VENV_DIR)
                    _safe_print("  Old virtual environment removed.")
                except Exception as e:
                    _safe_print(f"ERROR: Could not remove old venv: {e}")
                    _safe_print(f"  Please delete '{VENV_DIR.name}/' manually and re-run.")
                    sys.exit(1)
            else:
                _safe_print("  Aborted.  Delete the old venv manually and re-run:")
                if CURRENT_OS == "windows":
                    _safe_print(f"    rmdir /s {VENV_DIR.name}")
                else:
                    _safe_print(f"    rm -rf {VENV_DIR.name}")
                sys.exit(1)

    # ── Step 3: Create virtualenv if needed ──
    if not VENV_DIR.is_dir():
        _safe_print(
            f"Creating Python {py_ver_str} virtual environment "
            f"in '{VENV_DIR.name}/' ..."
        )
        try:
            subprocess.run(
                [python310, "-m", "venv", str(VENV_DIR)],
                check=True,
            )
            _safe_print("Virtual environment created.")
        except subprocess.CalledProcessError as e:
            _safe_print(f"ERROR: Could not create virtual environment: {e}")
            if CURRENT_OS == "linux":
                _safe_print("  On Ubuntu/Debian, ensure python3.10-venv is installed:")
                _safe_print("    sudo apt install python3.10-venv")
            elif CURRENT_OS == "windows":
                _safe_print("  Make sure Python 3.10 was installed with 'Add to PATH' checked.")
                _safe_print("  Or try running as Administrator.")
            sys.exit(1)

        # Verify it worked
        venv_ver = _version_tuple(str(python_exe))
        if venv_ver is None or venv_ver[0] != REQUIRED_MAJOR or venv_ver[1] != REQUIRED_MINOR:
            _safe_print(
                "ERROR: Created virtual environment, but the interpreter is "
                "not Python 3.10. This can happen if pyenv shims are stale. "
                "Try: pyenv rehash"
            )
            sys.exit(1)

    # ── Step 4: Install/upgrade dependencies ──
    marker_file = VENV_DIR / ".setup_done"
    requirements_txt = PROJECT_ROOT / "requirements.txt"

    if not requirements_txt.is_file():
        _safe_print(f"ERROR: requirements.txt not found at {requirements_txt}")
        sys.exit(1)

    if _needs_reinstall(marker_file, requirements_txt):
        _safe_print("Installing dependencies from requirements.txt ...")
        if CURRENT_OS == "linux":
            _safe_print(
                "(wxPython source build on Linux can take 30-60 min;"
                " pre-built wheels will be tried first)"
            )
        else:
            _safe_print("(this may take a few minutes on first run)")
        _safe_print()

        # Install uv for faster dependency resolution (falls back to pip)
        use_uv = _ensure_uv(python_exe)

        # Install all dependencies (handles wxPython Linux extras internally)
        _install_dependencies(python_exe, requirements_txt, use_uv=use_uv)

        # Write marker with hash and version tag
        try:
            marker_lines = [
                _hash_file(requirements_txt),
                f"{REQUIRED_MAJOR}.{REQUIRED_MINOR}",
            ]
            marker_file.write_text("\n".join(marker_lines) + "\n", encoding="utf-8")
        except OSError:
            pass  # non-fatal

        _safe_print()
        _safe_print("Dependencies installed successfully.")
    else:
        _safe_print("Dependencies already up-to-date (use --reinstall to force).")

    # ── Step 5: Delegate to setup.py ──
    setup_py = PROJECT_ROOT / "setup.py"
    if not setup_py.exists():
        _safe_print(f"ERROR: Could not find setup.py at {setup_py}")
        sys.exit(1)

    cmd = [str(python_exe), str(setup_py)] + sys.argv[1:]
    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        _safe_print()
        _safe_print("Setup cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    bootstrap()
