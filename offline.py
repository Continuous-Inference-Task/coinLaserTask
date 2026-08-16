"""
offline.py — Offline package preparation for the CoIn Laser Task.

Bundles a fully configured experiment (code, config, sequences, presets,
images) together with all Python dependencies and a portable interpreter
into a self-contained directory that runs on a lab machine without internet.

Called from wizard.py:
    from offline import prepare_offline_package
    prepare_offline_package(cfg)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent

PYTHON_VERSION = "3.10"
PYTHON_VERSION_SHORT = "310"

# python-build-standalone GitHub release API
PBS_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"

# Platform → python-build-standalone arch suffix
PBS_ARCH = {
    "linux":   "x86_64-unknown-linux-gnu",
    "windows": "x86_64-pc-windows-msvc",
}

# pip download --platform values
PIP_PLATFORM = {
    "linux":   "manylinux_2_17_x86_64",
    "windows": "win_amd64",
}

# wxPython pre-built wheel indexes (Linux only; Windows wheels are on PyPI)
WXPYTHON_FIND_LINKS = {
    "ubuntu-22.04": "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04",
    "ubuntu-24.04": "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04",
}

# Project files/directories to copy into the package
PROJECT_DIRS  = ["laserTask", "stimgen", "presets", "sequences", "images"]
PROJECT_FILES = ["main.py", "pyproject.toml", "uv.lock"]

# Patterns to exclude when copying
EXCLUDE = {"__pycache__", ".pyc", "config.json.bak"}

# Machine-local config keys shown during the lab-machine config check
MACHINE_CONFIG_KEYS = [
    ("target_os",          "Target OS"),
    ("window_size_w",      "Window width"),
    ("window_size_h",      "Window height"),
    ("fullscreen",         "Fullscreen"),
    ("screen_index",       "Screen index"),
    ("monitor_name",       "Monitor name"),
    ("target_refresh_rate","Refresh rate (Hz)"),
    ("input_device",       "Input device"),
    ("key_left",           "Left key"),
    ("key_right",          "Right key"),
    ("keyboard_backend",   "Keyboard backend"),
    ("trigger_mode",       "Trigger mode"),
    ("serial_port",        "Serial port"),
    ("serial_baud_rate",   "Serial baud rate"),
    ("parallel_address",   "Parallel port address"),
]


# ── Terminal helpers (mirror wizard.py style, zero deps) ────────────────────

class _C:
    reset   = "\033[0m"
    bold    = "\033[1m"
    dim     = "\033[2m"
    green   = "\033[32m"
    yellow  = "\033[33m"
    red     = "\033[31m"
    cyan    = "\033[36m"
    magenta = "\033[35m"

def _c(code: str, text: str) -> str:
    return f"{code}{text}{_C.reset}"

def _step(msg: str) -> None:
    """Print a step header."""
    print(f"  {_c(_C.cyan, '→')} {msg}...")

def _done(msg: str = "done") -> None:
    print(f"    {_c(_C.green, '✓')} {msg}")

def _fail(msg: str) -> None:
    print(f"    {_c(_C.red, '✗')} {msg}")

def _info(msg: str) -> None:
    print(f"    {_c(_C.dim, msg)}")

def _prompt(text: str, default: str = "") -> str:
    """Prompt with optional default, return stripped input or default."""
    if default:
        raw = input(f"  {text} [{default}]: ").strip()
        return raw if raw else default
    return input(f"  {text}: ").strip()

def _prompt_yn(text: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {text} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


# ── Pre-flight check ────────────────────────────────────────────────────────

def _preflight() -> Tuple[bool, List[str]]:
    """Verify that the experiment is configured and sequences exist."""
    issues: List[str] = []

    config_json = PROJECT_ROOT / "laserTask" / "config.json"
    if not config_json.exists():
        issues.append("laserTask/config.json not found — run the wizard first.")
    else:
        _done(f"Config: {config_json.relative_to(PROJECT_ROOT)}")

    seq_dir = PROJECT_ROOT / "sequences"
    if not seq_dir.exists() or not any(seq_dir.glob("**/*.csv")):
        issues.append("No sequences found — generate sequences first (wizard → generate).")
    else:
        n = len(list(seq_dir.glob("**/*.csv")))
        _done(f"Sequences: {n} CSV files")

    presets_dir = PROJECT_ROOT / "presets"
    if presets_dir.exists():
        n = len(list(presets_dir.glob("*.json")))
        _done(f"Presets: {n} preset(s)")

    images_dir = PROJECT_ROOT / "images"
    if images_dir.exists():
        n = len(list(images_dir.iterdir()))
        _done(f"Images: {n} file(s)")

    return (len(issues) == 0, issues)


# ── Platform selection ────────────────────────────────────────────────────

def _ask_platform() -> Tuple[str, Optional[str]]:
    """Ask the target platform. Returns (platform, ubuntu_version or None)."""
    print()
    print("  Which platform will the lab machine run?")
    print(f"    {_c(_C.green, '1')})  Linux  (Ubuntu)")
    print(f"    {_c(_C.green, '2')})  Windows")
    print()

    while True:
        choice = input(_c(_C.magenta, "  ❯ ")).strip()
        if choice == "1":
            platform = "linux"
            break
        elif choice == "2":
            platform = "windows"
            break
        print(_c(_C.yellow, "  Please enter 1 or 2."))

    ubuntu_ver = None
    if platform == "linux":
        print()
        print("  Which Ubuntu version?")
        print(f"    {_c(_C.green, '1')})  Ubuntu 22.04")
        print(f"    {_c(_C.green, '2')})  Ubuntu 24.04")
        print()

        while True:
            choice = input(_c(_C.magenta, "  ❯ ")).strip()
            if choice == "1":
                ubuntu_ver = "ubuntu-22.04"
                break
            elif choice == "2":
                ubuntu_ver = "ubuntu-24.04"
                break
            print(_c(_C.yellow, "  Please enter 1 or 2."))

    return (platform, ubuntu_ver)


# ── Step 1: Export requirements ─────────────────────────────────────────────

def _export_requirements(pack_dir: Path, target_platform: Optional[str] = None) -> bool:
    """Export locked requirements via uv export, optionally filtered for a
    specific target platform (cross-platform packaging)."""
    _step("Exporting locked requirements")
    try:
        result = subprocess.run(
            ["uv", "export", "--no-dev", "--no-emit-project", "--no-hashes"],
            cwd=PROJECT_ROOT,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            _fail("uv export failed")
            _info(result.stderr[:500])
            return False

        raw_lines = result.stdout.splitlines()

        # Filter for target platform if cross-packaging
        if target_platform:
            current_os = "windows" if sys.platform == "win32" else "linux"
            if target_platform != current_os:
                raw_lines = _filter_requirements_for_platform(raw_lines, target_platform)
                _info(f"Filtered for {target_platform} platform")

        req_file = pack_dir / "requirements.txt"
        req_file.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

        n = len([l for l in raw_lines
                 if l.strip() and not l.startswith("#") and not l.startswith(" ")])
        _done(f"{n} packages exported")
        return True
    except FileNotFoundError:
        _fail("uv not found — run inside the project venv (uv run python wizard.py)")
        return False
    except Exception as e:
        _fail(str(e))
        return False


def _filter_requirements_for_platform(lines: List[str], target_platform: str) -> List[str]:
    """Filter requirements.txt lines, keeping only packages whose markers
    match the target platform.

    Uses packaging.markers if available; falls back to simple heuristics.
    """
    # Build the environment for marker evaluation
    if target_platform == "windows":
        env = {
            "sys_platform": "win32",
            "platform_system": "Windows",
            "os_name": "nt",
        }
    else:
        env = {
            "sys_platform": "linux",
            "platform_system": "Linux",
            "os_name": "posix",
        }
    env.update({
        "python_version": PYTHON_VERSION,
        "python_full_version": f"{PYTHON_VERSION}.0",
        "platform_machine": "x86_64",
        "implementation_name": "cpython",
        "platform_python_implementation": "CPython",
        "extra": "",
    })

    try:
        from packaging.requirements import Requirement
        from packaging.markers import Marker
    except ImportError:
        # Fallback: simple heuristic — keep lines without sys_platform markers
        # or with matching platform
        keep_target = "win32" if target_platform == "windows" else "linux"
        skip_targets = {"win32", "linux", "darwin"} - {keep_target}
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                result.append(line)
                continue
            if not line.startswith(" "):  # package line (not comment continuation)
                skip = False
                for skip_target in skip_targets:
                    if f"sys_platform == '{skip_target}'" in stripped:
                        # Check it's not an OR with our target
                        if f"sys_platform == '{keep_target}'" not in stripped:
                            skip = True
                            break
                if skip:
                    continue
            result.append(line)
        return result

    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or line.startswith(" "):
            # Comment or continuation line — keep it
            result.append(line)
            continue

        # Parse the requirement
        try:
            req = Requirement(stripped)
            if req.marker is None or req.marker.evaluate(env):
                result.append(line)
        except Exception:
            # If we can't parse, keep the line to be safe
            result.append(line)

    return result


# ── Step 2: Download wheels ─────────────────────────────────────────────────

def _download_wheels(pack_dir: Path, target_platform: str,
                     ubuntu_ver: Optional[str]) -> bool:
    """Download all wheels for the target platform."""
    _step(f"Downloading wheels ({target_platform}"
          + (f"/{ubuntu_ver}" if ubuntu_ver else "") + ")")

    wheels_dir = pack_dir / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)
    req_file = pack_dir / "requirements.txt"

    # Build the pip download command.
    # uv-managed venvs don't include pip, so we use `uv run --with pip`
    # to temporarily add pip to the environment (same approach as uv-pack).
    base_cmd = ["uv", "run", "--with", "pip",
                "python", "-m", "pip", "download",
                "--no-deps",
                "--disable-pip-version-check",
                "-r", str(req_file),
                "-d", str(wheels_dir)]

    # Determine if this is cross-platform
    current_platform = "windows" if sys.platform == "win32" else "linux"
    is_cross = (target_platform != current_platform)

    if is_cross:
        # --platform requires --only-binary, but some packages only have
        # sdists (pure Python). We use a two-pass approach:
        #   1. Download with --only-binary :all: (gets all wheels)
        #   2. Retry with --no-binary for packages that only have sdists
        cmd = base_cmd + ["--platform", PIP_PLATFORM[target_platform],
                          "--python-version", PYTHON_VERSION_SHORT,
                          "--only-binary", ":all:"]
    else:
        cmd = base_cmd + ["--prefer-binary"]

    # wxPython find-links for Linux targets
    if target_platform == "linux":
        for uv_ver in ["ubuntu-22.04", "ubuntu-24.04"]:
            url = WXPYTHON_FIND_LINKS.get(uv_ver)
            if url:
                cmd += ["--find-links", url]

    _info("Running: uv run --with pip python -m pip download ... (this may take several minutes)")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                  cwd=PROJECT_ROOT)

        # ── Two-pass: retry with --no-binary for sdist-only packages ──
        if result.returncode != 0 and is_cross:
            failed = _parse_failed_packages(result.stderr)
            if failed:
                _info(f"{len(failed)} package(s) have no wheels — downloading as sdist")
                retry_cmd = cmd + ["--no-binary", ",".join(failed)]
                result = subprocess.run(retry_cmd, capture_output=True, text=True,
                                          cwd=PROJECT_ROOT)

        if result.returncode != 0:
            _fail("pip download had errors")
            for line in result.stderr.strip().splitlines()[-10:]:
                _info(f"  {line}")
            return False

        n_wheels = len(list(wheels_dir.glob("*.whl")))
        n_sdist = len(list(wheels_dir.glob("*.tar.gz"))) + len(list(wheels_dir.glob("*.zip")))
        _done(f"{n_wheels} wheels, {n_sdist} sdist downloaded")
        return True
    except Exception as e:
        _fail(str(e))
        return False


def _parse_failed_packages(stderr: str) -> List[str]:
    """Extract package names that couldn't be found as wheels from pip stderr."""
    import re
    failed = []
    for line in stderr.splitlines():
        match = re.search(r"Could not find a version that satisfies the requirement (\S+)", line)
        if match:
            pkg_spec = match.group(1)
            # Extract package name from "package==version ; markers"
            pkg_name = re.match(r'^([a-zA-Z0-9_.-]+)', pkg_spec)
            if pkg_name:
                failed.append(pkg_name.group(1))
    return failed


# ── Step 3: Download portable Python ────────────────────────────────────────

def _download_python_build(pack_dir: Path, target_platform: str) -> bool:
    """Download a python-build-standalone archive for the target platform."""
    _step(f"Downloading portable Python {PYTHON_VERSION} ({target_platform})")

    py_dir = pack_dir / "python"
    py_dir.mkdir(parents=True, exist_ok=True)

    arch = PBS_ARCH[target_platform]
    # Match: cpython-3.10.X-{arch}-install_only_stripped.tar.gz
    prefix = f"cpython-{PYTHON_VERSION}."
    suffix = f"-{arch}-install_only_stripped.tar.gz"

    try:
        # Query the GitHub API for the latest release that has 3.10 assets
        req = urllib.request.Request(
            f"{PBS_API}?per_page=10",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "coin-laser-task"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            import json as _json
            releases = _json.loads(resp.read())

        asset_url = None
        asset_name = None

        for release in releases:
            for asset in release.get("assets", []):
                name = asset["name"]
                if name.startswith(prefix) and name.endswith(suffix):
                    asset_url = asset["browser_download_url"]
                    asset_name = name
                    break
            if asset_url:
                break

        if not asset_url:
            _fail(f"No Python {PYTHON_VERSION} build found for {target_platform}")
            return False

        dest = py_dir / asset_name

        # Skip if already downloaded
        if dest.exists():
            _done(f"Using cached: {asset_name}")
            return True

        _info(f"Downloading {asset_name}...")
        urllib.request.urlretrieve(asset_url, dest)

        size_mb = dest.stat().st_size / (1024 * 1024)
        _done(f"{asset_name} ({size_mb:.0f} MB)")
        return True

    except urllib.error.HTTPError as e:
        _fail(f"GitHub API error: {e}")
        _info("If rate-limited, set GITHUB_TOKEN env var and retry.")
        return False
    except Exception as e:
        _fail(str(e))
        return False


# ── Step 4: Copy project files ──────────────────────────────────────────────

def _copy_project(pack_dir: Path, include_wizard: bool) -> bool:
    """Copy project code, config, sequences, presets, images into the package."""
    _step("Copying project code and configuration")

    def _ignore(dir_path, names):
        ignored = set()
        for name in names:
            if name in EXCLUDE or name.endswith(".pyc"):
                ignored.add(name)
        return ignored

    # Copy directories
    for dirname in PROJECT_DIRS:
        src = PROJECT_ROOT / dirname
        if src.exists():
            shutil.copytree(src, pack_dir / dirname, ignore=_ignore,
                            dirs_exist_ok=True)

    # Copy files
    for filename in PROJECT_FILES:
        src = PROJECT_ROOT / filename
        if src.exists():
            shutil.copy2(src, pack_dir / filename)

    # Always copy wizard.py (it's needed for the launcher even if we
    # don't include it as a user-facing option — the launcher uses it
    # for the config-check feature)
    if include_wizard:
        src = PROJECT_ROOT / "wizard.py"
        if src.exists():
            shutil.copy2(src, pack_dir / "wizard.py")

    # Ensure data/ exists (for experiment output)
    data_dir = pack_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / ".gitkeep").touch()

    # Copy offline.py (so the launcher can use it if needed)
    src = PROJECT_ROOT / "offline.py"
    if src.exists():
        shutil.copy2(src, pack_dir / "offline.py")

    _done("Project files copied")
    return True


# ── Step 5: Bundle system libraries ─────────────────────────────────────────

def _bundle_system_libs(pack_dir: Path, target_platform: str) -> bool:
    """Bundle platform-specific system libraries not included in wheels."""
    if target_platform != "linux":
        _done("No system libraries needed for Windows")
        return True

    _step("Bundling system library: libportaudio.so.2")
    lib_dir = pack_dir / "lib"
    lib_dir.mkdir(exist_ok=True)

    # Try to find libportaudio on the system
    import ctypes.util
    pa_path = ctypes.util.find_library("portaudio")

    if pa_path and Path(pa_path).exists():
        shutil.copy2(pa_path, lib_dir / "libportaudio.so.2")
        _done(f"Bundled {Path(pa_path).name}")
    else:
        # Try common locations
        for candidate in ["/usr/lib/libportaudio.so.2",
                          "/usr/lib/x86_64-linux-gnu/libportaudio.so.2",
                          "/lib/x86_64-linux-gnu/libportaudio.so.2"]:
            if Path(candidate).exists():
                shutil.copy2(candidate, lib_dir / "libportaudio.so.2")
                _done(f"Bundled from {candidate}")
                return True
        # Not found — warn but continue (psychtoolbox bundles its own)
        _info("libportaudio.so.2 not found on this system.")
        _info("PsychoPy prefers PTB audio (which bundles portaudio), so")
        _info("this is usually fine. If sounddevice is used, install")
        _info("portaudio19-dev on the lab machine.")

    return True


# ── Step 6: Write launcher scripts ──────────────────────────────────────────

def _write_launchers(pack_dir: Path, include_wizard: bool,
                      target_platform: str) -> bool:
    """Write run.sh, run.bat, and _launcher.py into the package."""
    _step("Generating launcher scripts")

    # _launcher.py — the main launcher logic (Python, cross-platform)
    launcher_path = pack_dir / "_launcher.py"
    launcher_path.write_text(_LAUNCHER_PY, encoding="utf-8")

    # run.sh — thin wrapper for Linux/macOS
    run_sh = pack_dir / "run.sh"
    run_sh.write_text(_RUN_SH, encoding="utf-8")
    run_sh.chmod(0o755)

    # run.bat — thin wrapper for Windows
    run_bat = pack_dir / "run.bat"
    run_bat.write_text(_RUN_BAT, encoding="utf-8")

    # README.txt — quick instructions
    readme = pack_dir / "README.txt"
    readme.write_text(
        "CoIn Laser Task — Offline Package\n"
        "===================================\n\n"
        "To run the experiment:\n"
        "  Linux:   ./run.sh\n"
        "  Windows: run.bat\n\n"
        "First run takes a few minutes to set up the Python environment.\n"
        "Subsequent runs start immediately.\n\n"
        "Commands:\n"
        "  ./run.sh              Run the experiment\n"
        + ("  ./run.sh wizard       Open the configuration wizard\n"
           "  ./run.sh --check      Re-check machine settings\n\n"
           if include_wizard else "\n")
        + "If running from a USB stick, you will be offered to copy\n"
        "the experiment to the local disk for better performance.\n",
        encoding="utf-8")

    # .gitignore for the package
    (pack_dir / ".gitignore").write_text(
        ".venv/\n.python/\ndata/\n.machine_verified\n.packages_installed\n",
        encoding="utf-8")

    _done("Launchers generated")
    return True


# ── Removable Drive Detection ──────────────────────────────────────────────

def _discover_removable_drives() -> List[Dict[str, Any]]:
    """Detect mounted USB flash drives and removable media cross-platform."""
    drives: List[Dict[str, Any]] = []

    # 1. Linux: use lsblk JSON + udisks2 auto-mount
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS,MODEL,TRAN,RM"],
                capture_output=True, text=True, check=True
            )
            data = json.loads(res.stdout)

            def scan_devices(dev_list, parent_model=None, parent_tran=None):
                for dev in dev_list:
                    name = dev.get("name", "")
                    model = (dev.get("model") or parent_model or "USB Drive").strip()
                    tran = dev.get("tran") or parent_tran
                    rm = dev.get("rm") or False
                    fstype = dev.get("fstype")
                    label = dev.get("label") or name
                    mountpoints = [m for m in dev.get("mountpoints", []) if m]

                    is_removable = (tran == "usb") or rm or any("/media" in m for m in mountpoints)

                    # If removable partition with filesystem is unmounted, try auto-mount
                    if is_removable and fstype and not mountpoints and name:
                        dev_path = f"/dev/{name}"
                        m_res = subprocess.run(["udisksctl", "mount", "-b", dev_path], capture_output=True, text=True)
                        if m_res.returncode == 0:
                            for line in m_res.stdout.splitlines():
                                if "Mounted" in line and " at " in line:
                                    m_path = line.split(" at ")[-1].strip().rstrip(".")
                                    if m_path:
                                        mountpoints.append(m_path)

                    if mountpoints and is_removable:
                        for m in mountpoints:
                            try:
                                usage = shutil.disk_usage(m)
                                free_gb = usage.free / (1024**3)
                                drives.append({
                                    "path": Path(m),
                                     "label": label or Path(m).name,
                                    "model": model,
                                    "free_gb": free_gb,
                                    "device": f"/dev/{name}"
                                })
                            except Exception:
                                pass

                    if "children" in dev:
                        scan_devices(dev["children"], parent_model=model, parent_tran=tran)

            scan_devices(data.get("blockdevices", []))
        except Exception:
            user = os.environ.get("USER", "")
            search_paths = [Path(f"/run/media/{user}"), Path(f"/media/{user}"), Path("/media"), Path("/mnt")]
            for sp in search_paths:
                if sp.is_dir():
                    for entry in sp.iterdir():
                        if entry.is_dir() and not entry.is_symlink():
                            try:
                                usage = shutil.disk_usage(entry)
                                drives.append({
                                    "path": entry,
                                    "label": entry.name,
                                    "model": "Removable Drive",
                                    "free_gb": usage.free / (1024**3),
                                    "device": str(entry)
                                })
                            except Exception:
                                pass

    # 2. macOS: check /Volumes
    elif sys.platform == "darwin":
        volumes = Path("/Volumes")
        if volumes.is_dir():
            for v in volumes.iterdir():
                if v.is_dir() and not v.is_symlink() and v.name not in ("Macintosh HD", "Macintosh HD - Data"):
                    try:
                        usage = shutil.disk_usage(v)
                        drives.append({
                            "path": v,
                            "label": v.name,
                            "model": "External Drive",
                            "free_gb": usage.free / (1024**3),
                            "device": str(v)
                        })
                    except Exception:
                        pass

    # 3. Windows: iterate drive letters with GetDriveTypeW
    elif sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    dtype = kernel32.GetDriveTypeW(drive)
                    if dtype in (2, 3):
                        try:
                            usage = shutil.disk_usage(drive)
                            vol_name_buf = ctypes.create_unicode_buffer(1024)
                            kernel32.GetVolumeInformationW(
                                drive, vol_name_buf, 1024, None, None, None, None, 0
                            )
                            label = vol_name_buf.value or f"Drive ({letter}:)"
                            drives.append({
                                "path": Path(drive),
                                "label": label,
                                "model": "Removable Disk" if dtype == 2 else "Drive",
                                "free_gb": usage.free / (1024**3),
                                "device": drive
                            })
                        except Exception:
                            pass
        except Exception:
            pass

    return drives


def _ask_destination(default_dir: str = "./offline-package") -> Tuple[Path, bool]:
    """Ask destination directory, presenting auto-detected USB drives if available.

    Returns (resolved_pack_dir, is_usb_destination).
    """
    print()
    drives = _discover_removable_drives()

    if not drives:
        out_dir = _prompt("Output directory", default_dir)
        return Path(out_dir).resolve(), False

    print("  Where would you like to save the offline package?")
    options: List[Tuple[str, str, Path]] = []

    # 1. Local folder option
    options.append(("local", f"Local directory  ({default_dir})", Path(default_dir).resolve()))

    # 2+. Discovered USB drives
    for d in drives:
        label = d["label"]
        model = d["model"]
        free_str = f"{d['free_gb']:.1f} GB free"
        target_path = d["path"] / "coin-laser-task-offline"
        desc = f"{model} ({label})  —  {target_path}  [{free_str}]"
        options.append(("usb", desc, target_path))

    # Last: Custom path
    options.append(("custom", "Custom path …", Path(default_dir).resolve()))

    for idx, (_, desc, _) in enumerate(options, 1):
        print(f"    {_c(_C.green, str(idx))})  {desc}")
    print()

    default_choice = "2" if len(drives) >= 1 else "1"
    while True:
        choice = input(f"  {_c(_C.magenta, '❯ ')}").strip()
        if not choice:
            choice = default_choice

        if choice.isdigit() and 1 <= int(choice) <= len(options):
            idx = int(choice) - 1
            kind, _, target_path = options[idx]
            if kind == "local":
                return target_path, False
            elif kind == "usb":
                return target_path, True
            elif kind == "custom":
                custom_str = _prompt("Output directory", default_dir)
                return Path(custom_str).resolve(), False
        print(_c(_C.yellow, f"  Please enter a number 1–{len(options)}."))


# ── Main entry point ────────────────────────────────────────────────────────

def prepare_offline_package(cfg: Dict[str, Any]) -> None:
    """Prepare a self-contained offline package of the configured experiment.

    Called from wizard.py when the user selects "Prepare offline package".
    """
    print()
    print("  " + _c(_C.bold, "Prepare Offline Package"))
    print("  " + _c(_C.dim, "Bundles your configuration, sequences, and all"))
    print("  " + _c(_C.dim, "dependencies into a self-contained directory for"))
    print("  " + _c(_C.dim, "a lab machine without internet access."))
    print()

    # ── Pre-flight check ──
    print("  Current state:")
    ok, issues = _preflight()
    if not ok:
        print()
        seq_dir = PROJECT_ROOT / "sequences"
        has_seqs = seq_dir.exists() and any(seq_dir.glob("**/*.csv"))
        config_exists = (PROJECT_ROOT / "laserTask" / "config.json").exists()

        # If sequences are missing but config is ready, offer to generate right now
        if not has_seqs and config_exists:
            _warn("No stimulus sequences found in sequences/.")
            print("  The offline package needs generated sequences to run on the lab machine.")
            print()
            if _prompt_yn("Generate sequences now from your current configuration?", default=True):
                try:
                    import wizard
                    cfg_to_use = cfg.copy() if cfg else wizard._read_laser_task_config()
                    if wizard.run_sequence_generation(cfg_to_use):
                        print()
                        _done("Sequences generated successfully.")
                        print()
                        print("  Re-checking state:")
                        ok, issues = _preflight()
                except Exception as exc:
                    _fail(f"Sequence generation failed: {exc}")

        if not ok:
            print()
            for issue in issues:
                _fail(issue)
            print()
            print("  Please resolve the issues above before packaging.")
            return
    # ── Ask target platform ──
    target_platform, ubuntu_ver = _ask_platform()

    # ── Ask if wizard should be included ──
    print()
    include_wizard = _prompt_yn(
        "Include the wizard for machine-local adjustments on the lab machine?",
        default=True)

    # ── Ask output directory with USB auto-detection ──
    pack_dir, is_usb = _ask_destination("./offline-package")

    # Check free space
    try:
        parent_dir = pack_dir if pack_dir.exists() else pack_dir.parent
        usage = shutil.disk_usage(parent_dir)
        free_gb = usage.free / (1024**3)
        if free_gb < 1.5:
            _warn(f"Low disk space on destination: {free_gb:.1f} GB available. Package requires ~1.5 GB.")
            if not _prompt_yn("Proceed anyway?", default=False):
                print("  Cancelled.")
                return
    except Exception:
        pass

    if pack_dir.exists() and pack_dir != PROJECT_ROOT:
        print()
        if not _prompt_yn(f"Directory exists: {pack_dir}\n  Remove and recreate?",
                          default=True):
            print("  Cancelled.")
            return
        shutil.rmtree(pack_dir, ignore_errors=True)

    pack_dir.mkdir(parents=True, exist_ok=True)

    # ── Run packaging pipeline ──
    print()
    steps = [
        ("Export requirements",     lambda: _export_requirements(pack_dir, target_platform)),
        ("Download wheels",          lambda: _download_wheels(
            pack_dir, target_platform, ubuntu_ver)),
        ("Download Python",          lambda: _download_python_build(
            pack_dir, target_platform)),
        ("Copy project",             lambda: _copy_project(
            pack_dir, include_wizard)),
        ("Bundle system libraries",  lambda: _bundle_system_libs(
            pack_dir, target_platform)),
        ("Generate launchers",       lambda: _write_launchers(
            pack_dir, include_wizard, target_platform)),
    ]

    for label, step_fn in steps:
        if not step_fn():
            print()
            _fail(f"Packaging failed at: {label}")
            print(f"  Partial output in: {pack_dir}")
            return

    # ── Done ──
    print()
    # Calculate total size
    total_size = sum(f.stat().st_size for f in pack_dir.rglob("*") if f.is_file())
    size_gb = total_size / (1024 ** 3)
    size_mb = total_size / (1024 ** 2)

    if size_gb >= 1:
        size_str = f"{size_gb:.1f} GB"
    else:
        size_str = f"{size_mb:.0f} MB"

    print(f"  {_c(_C.green, '✓ Package ready')}: {pack_dir}  ({size_str})")
    print()
    print("  Next steps:")
    launcher_cmd = "run.bat" if target_platform == "windows" else "./run.sh"
    if is_usb:
        print(f"    1. Eject USB drive safely.")
        print(f"    2. On lab machine: insert USB and run {_c(_C.cyan, launcher_cmd)}")
    else:
        print(f"    1. Copy to USB:     {_c(_C.cyan, f'cp -r {pack_dir}/ /media/your-usb/')}")
        print(f"    2. On lab machine:  {_c(_C.cyan, launcher_cmd)}")
    print()
    if include_wizard:
        print("  On the lab machine, the wizard is available for")
        print("  machine-local adjustments (serial port, display, etc.):")
        print(f"    {_c(_C.dim, './run.sh wizard')}")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Launcher script template — written into the package as _launcher.py
# Runs on the lab machine with only Python stdlib available.
# ─────────────────────────────────────────────────────────────────────────────

_LAUNCHER_PY = r'''#!/usr/bin/env python3
"""_launcher.py — Offline launcher for the CoIn Laser Task.

Handles first-run setup (extract Python, create venv, install wheels),
machine-config verification, and experiment/wizard launch.

Requires only Python stdlib.  Bootstrapped by run.sh / run.bat.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────

PACK_DIR   = Path(__file__).resolve().parent
PYTHON_DIR = PACK_DIR / ".python"
VENV_DIR   = PACK_DIR / ".venv"
WHEELS_DIR = PACK_DIR / "wheels"
LIB_DIR    = PACK_DIR / "lib"
CONFIG_PATH = PACK_DIR / "laserTask" / "config.json"
MARKER_INSTALLED = PACK_DIR / ".packages_installed"
MARKER_VERIFIED   = PACK_DIR / ".machine_verified"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")

# venv bin directory name differs by platform
_VENV_BIN = "Scripts" if IS_WINDOWS else "bin"
_VENV_PY = VENV_DIR / _VENV_BIN / ("python.exe" if IS_WINDOWS else "python3")
_BUNDLED_PY = PYTHON_DIR / ("python.exe" if IS_WINDOWS else "bin/python3")

# Machine-local config keys to display during the check
_MACHINE_KEYS = [
    ("target_os",          "Target OS"),
    ("window_size_w",      "Window width"),
    ("window_size_h",      "Window height"),
    ("fullscreen",         "Fullscreen"),
    ("screen_index",       "Screen index"),
    ("monitor_name",       "Monitor name"),
    ("target_refresh_rate","Refresh rate (Hz)"),
    ("input_device",       "Input device"),
    ("key_left",           "Left key"),
    ("key_right",          "Right key"),
    ("keyboard_backend",   "Keyboard backend"),
    ("trigger_mode",       "Trigger mode"),
    ("serial_port",        "Serial port"),
    ("serial_baud_rate",   "Serial baud rate"),
    ("parallel_address",   "Parallel port address"),
]


# ── Helpers ──────────────────────────────────────────────────────────────

def _c(code, text):
    return f"{code}{text}\033[0m"

_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"

def _say(msg):     print(f"  {msg}")
def _ok(msg):      print(f"  {_c(_GREEN, '✓')} {msg}")
def _warn(msg):    print(f"  {_c(_YELLOW, '⚠')} {msg}")
def _err(msg):     print(f"  {_c(_RED, '✗')} {msg}")
def _info(msg):    print(f"  {_c(_DIM, msg)}")

def _prompt_yn(text, default=True):
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {text} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")

def _prompt(text, default=""):
    if default:
        raw = input(f"  {text} [{default}]: ").strip()
        return raw if raw else default
    return input(f"  {text}: ").strip()

def _find_bundled_python():
    """Find the bundled Python binary, extracting the archive if needed."""
    if _BUNDLED_PY.exists() and os.access(_BUNDLED_PY, os.X_OK):
        return str(_BUNDLED_PY)

    # On Windows, the python.exe might be at a different path
    if IS_WINDOWS:
        alt = PYTHON_DIR / "python.exe"
        if alt.exists():
            return str(alt)

    # Try finding any python3/python.exe in the extracted dir
    for name in ("python3", "python.exe", "python"):
        for p in PYTHON_DIR.rglob(name):
            if os.access(p, os.X_OK):
                return str(p)

    return None

def _extract_python():
    """Extract the bundled python-build-standalone archive."""
    if PYTHON_DIR.exists() and any(PYTHON_DIR.iterdir()):
        # Already extracted but binary not found at expected path
        py = _find_bundled_python()
        if py:
            return py

    # Find the archive
    archives = list((PACK_DIR / "python").glob("cpython-*.tar.gz")) if (PACK_DIR / "python").exists() else []
    if not archives:
        return None

    archive = archives[0]
    _say(f"Extracting Python from {archive.name}...")
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    import tarfile
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(PYTHON_DIR)
    _ok("Python extracted")

    return _find_bundled_python()

def _is_removable_media(path):
    """Heuristic: detect if the path is on a USB stick / removable drive."""
    p = str(path)
    if IS_LINUX:
        for prefix in ("/media/", "/mnt/", "/run/media/"):
            if p.startswith(prefix):
                return True
    elif IS_WINDOWS:
        # Check drive type (A: and B: are typically floppy/removable)
        drive = os.path.splitdrive(p)[0]
        if drive and drive[0].upper() in ("A", "B"):
            return True
        # Check if the drive is removable via ctypes
        try:
            import ctypes
            drive_letter = drive[0] if drive else "C"
            flags = ctypes.c_uint()
            ctypes.windll.kernel32.GetDriveInformationW(
                ctypes.c_wchar_p(f"{drive_letter}:\\"), None, None,
                ctypes.byref(flags), None, None, None, None, None, None)
            # DRIVE_REMOVABLE = 2
            if flags.value == 2:
                return True
        except Exception:
            pass
    return False

def _copy_to_disk():
    """Offer to copy the package to local disk. Returns new path or None."""
    if not _is_removable_media(PACK_DIR):
        return None

    print()
    _warn("You are running from a USB stick / removable media.")
    print("  For better performance, copy to the local disk?")
    if not _prompt_yn("Copy to local disk?", default=True):
        return None

    default_loc = str(Path.home() / "coin-laser-task")
    loc = _prompt("Install location", default_loc)
    dest = Path(loc).expanduser().resolve()

    if dest.exists():
        if not _prompt_yn(f"{dest} already exists. Overwrite?", default=False):
            return None
        shutil.rmtree(dest, ignore_errors=True)

    print()
    _say(f"Copying to {dest}...")
    shutil.copytree(PACK_DIR, dest, symlinks=True,
                    ignore=shutil.ignore_patterns(".python", ".venv"))
    _ok("Files copied")

    # Copy the Python archive (not the extracted dir)
    py_archives = list((PACK_DIR / "python").glob("cpython-*.tar.gz"))
    if py_archives:
        dest_py = dest / "python"
        dest_py.mkdir(exist_ok=True)
        shutil.copy2(py_archives[0], dest_py / py_archives[0].name)

    return dest

def _setup_venv(bundled_py):
    """Create venv and install wheels. Returns venv python path or None."""
    if _VENV_PY.exists() and MARKER_INSTALLED.exists():
        return str(_VENV_PY)

    # Create venv
    if not _VENV_PY.exists():
        _say("Creating virtual environment...")
        try:
            subprocess.run(
                [bundled_py, "-m", "venv", "--copies", str(VENV_DIR)],
                check=True, capture_output=True, text=True)
            _ok("Virtual environment created")
        except subprocess.CalledProcessError as e:
            _err("Failed to create venv")
            _info(e.stderr[:500] if e.stderr else "")
            return None

    # Install wheels
    if not MARKER_INSTALLED.exists():
        req_file = PACK_DIR / "requirements.txt"
        _say(f"Installing packages offline (~{len(list(WHEELS_DIR.glob('*')))} files)...")
        env = os.environ.copy()
        env["PIP_NO_INDEX"] = "1"
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

        try:
            result = subprocess.run(
                [str(_VENV_PY), "-m", "pip", "install",
                 "--find-links", str(WHEELS_DIR),
                 "-r", str(req_file)],
                env=env, capture_output=True, text=True)
            if result.returncode != 0:
                _err("Package installation failed")
                _info(result.stderr[-500:] if result.stderr else "")
                return None
            _ok("Packages installed")
            MARKER_INSTALLED.write_text("ok", encoding="utf-8")
        except Exception as e:
            _err(f"Installation error: {e}")
            return None

    return str(_VENV_PY)

def _read_config():
    """Read laserTask/config.json directly (no project imports needed)."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _check_config(force=False):
    """Show machine-local settings and ask if they match this machine."""
    if MARKER_VERIFIED.exists() and not force:
        return True

    cfg = _read_config()
    if not cfg:
        _warn("No config.json found — using defaults.")
        return True

    print()
    print("  " + _c(_BOLD, "── Machine configuration check ──"))
    print("  This experiment was configured on another computer.")
    print("  Please verify these settings match THIS machine:\n")

    current_os = "linux" if IS_LINUX else ("windows" if IS_WINDOWS else "macos")

    for key, label in _MACHINE_KEYS:
        val = cfg.get(key, "—")
        # Highlight OS mismatch
        if key == "target_os" and val != "—" and val != current_os:
            print(f"    {_c(_YELLOW, label)}: {val}  {_c(_YELLOW, '(mismatch!)')}")
        else:
            print(f"    {label}: {val}")

    print()
    matches = _prompt_yn("Do these settings match this machine?", default=True)

    if matches:
        MARKER_VERIFIED.write_text(
            f"verified {date.today().isoformat()}", encoding="utf-8")
        return True
    else:
        # Offer to launch wizard for machine-local adjustments
        wizard_path = PACK_DIR / "wizard.py"
        if wizard_path.exists():
            print()
            if _prompt_yn("Launch the wizard to adjust machine settings?",
                          default=True):
                _run_wizard([])
                # After wizard, mark as verified
                MARKER_VERIFIED.write_text(
                    f"verified {date.today().isoformat()}", encoding="utf-8")
                return True
            else:
                return True  # proceed anyway
        else:
            _info("Wizard not included in this package.")
            _info("You can edit laserTask/config.json manually.")
            return True

def _build_env():
    """Build environment with LD_LIBRARY_PATH for bundled libs."""
    env = os.environ.copy()

    if IS_LINUX and LIB_DIR.exists():
        # Bundled portaudio
        lib_paths = [str(LIB_DIR)]

        # wxPython bundled libs (same as bootstrap.py)
        wx_dir = (VENV_DIR / "lib" / "python3.10" / "site-packages" / "wx")
        if wx_dir.is_dir():
            lib_paths.append(str(wx_dir))

        env["LD_LIBRARY_PATH"] = os.pathsep.join(
            lib_paths + [env.get("LD_LIBRARY_PATH", "")])

    return env

def _run_experiment(venv_py):
    """Launch main.py with the venv Python."""
    env = _build_env()
    _info("Launching experiment...")
    print()
    subprocess.run(
        [venv_py, str(PACK_DIR / "main.py")],
        cwd=str(PACK_DIR), env=env)

def _run_wizard(args):
    """Launch wizard.py with the venv Python."""
    wizard_path = PACK_DIR / "wizard.py"
    if not wizard_path.exists():
        _err("Wizard not included in this package.")
        _info("This package was prepared without the wizard option.")
        return

    env = _build_env()
    subprocess.run(
        [str(_VENV_PY), str(wizard_path)] + args,
        cwd=str(PACK_DIR), env=env)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    args = [a for a in sys.argv[1:] if a]

    print()
    print(_c(_BOLD, "  CoIn Laser Task — Offline Launcher"))
    print()

    # ── 1. Copy to disk if on removable media ──
    new_dir = _copy_to_disk()
    if new_dir:
        # Re-launch from the new location
        new_launcher = new_dir / "_launcher.py"
        new_run = new_dir / ("run.bat" if IS_WINDOWS else "run.sh")
        _info(f"Re-launching from {new_dir}...")
        print()
        # Re-run the launcher from the new location
        os.chdir(new_dir)
        global PACK_DIR, PYTHON_DIR, VENV_DIR, WHEELS_DIR, LIB_DIR
        global CONFIG_PATH, MARKER_INSTALLED, MARKER_VERIFIED
        global _VENV_BIN, _VENV_PY, _BUNDLED_PY
        PACK_DIR = new_dir
        PYTHON_DIR = PACK_DIR / ".python"
        VENV_DIR = PACK_DIR / ".venv"
        WHEELS_DIR = PACK_DIR / "wheels"
        LIB_DIR = PACK_DIR / "lib"
        CONFIG_PATH = PACK_DIR / "laserTask" / "config.json"
        MARKER_INSTALLED = PACK_DIR / ".packages_installed"
        MARKER_VERIFIED = PACK_DIR / ".machine_verified"
        _VENV_PY = VENV_DIR / _VENV_BIN / ("python.exe" if IS_WINDOWS else "python3")
        _BUNDLED_PY = PYTHON_DIR / ("python.exe" if IS_WINDOWS else "bin/python3")

    # ── 2. Extract Python (first run) ──
    bundled_py = _find_bundled_python()
    if not bundled_py:
        _say("Setting up Python (first run only)...")
        bundled_py = _extract_python()
        if not bundled_py:
            _err("No Python interpreter found. Check the python/ directory.")
            sys.exit(1)

    # ── 3. Create venv + install wheels ──
    venv_py = _setup_venv(bundled_py)
    if not venv_py:
        _err("Environment setup failed.")
        sys.exit(1)

    # ── 4. Config check ──
    check_mode = "--check" in args
    if check_mode:
        args.remove("--check")
    _check_config(force=check_mode)

    # ── 5. Launch ──
    print()
    if args and args[0] == "wizard":
        _run_wizard(args[1:])
    else:
        _run_experiment(venv_py)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("  Cancelled.")
        sys.exit(1)
    except EOFError:
        print()
        print("  Cancelled.")
        sys.exit(1)
'''

# ── run.sh template ──────────────────────────────────────────────────────────

_RUN_SH = r'''#!/bin/sh
set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Extract Python on first run ──
if [ ! -x "$DIR/.python/bin/python3" ]; then
    PY_TGZ=$(ls "$DIR"/python/cpython-*.tar.gz 2>/dev/null | head -1)
    if [ -n "$PY_TGZ" ]; then
        printf "  Extracting Python 3.10 (first run only)..."
        mkdir -p "$DIR/.python"
        tar -C "$DIR/.python" -xzf "$PY_TGZ"
        printf " done\n"
    fi
fi

# ── Find the Python binary ──
PY="$DIR/.python/bin/python3"
if [ ! -x "$PY" ]; then
    PY=$(find "$DIR/.python" -name python3 -type f -perm -u+x 2>/dev/null | head -1)
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    echo "ERROR: Python not found in $DIR/.python/"
    echo "Expected archive in $DIR/python/cpython-*.tar.gz"
    exit 1
fi

exec "$PY" "$DIR/_launcher.py" "$@"
'''

# ── run.bat template ─────────────────────────────────────────────────────────

_RUN_BAT = r'''@echo off
setlocal
set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"

if not exist "%DIR%\.python\python.exe" (
    for %%f in ("%DIR%\python\cpython-*.tar.gz") do (
        echo   Extracting Python 3.10 (first run only)...
        if not exist "%DIR%\.python" mkdir "%DIR%\.python"
        tar -C "%DIR%\.python" -xzf "%%f"
    )
)

set "PY=%DIR%\.python\python.exe"
if not exist "%PY%" (
    for /r "%DIR%\.python" %%f in (python.exe) do set "PY=%%f"
)

if not exist "%PY%" (
    echo ERROR: Python not found in %DIR%\.python\
    exit /b 1
)

"%PY%" "%DIR%\_launcher.py" %*
'''