#!/usr/bin/env python3
import subprocess
import sys
import os
from typing import List
import json

try:
    from ._constants import CONFIG_PATH
except ImportError:
    # Running as a script (not as a package module)
    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    sys.path.insert(0, _parent)
    from pironman5._constants import CONFIG_PATH

URL = "http://localhost:34001"

def check_desktop_environment() -> bool:
    """
    Check if the current environment is a desktop environment (prevent failure in SSH/pure console environments)
    Return: True = desktop environment, False = non-desktop environment
    """
    # Core check 1: DISPLAY or WAYLAND_DISPLAY (X11 or Wayland)
    session_type = os.getenv("XDG_SESSION_TYPE", "")
    if session_type not in ["x11", "wayland"]:
        print(f"Error: Current session type is '{session_type}'. Only x11/wayland desktop sessions are supported.", file=sys.stderr)
        return False
    if session_type == "x11" and not os.getenv("DISPLAY"):
        print("Error: X11 session detected but DISPLAY is not set.", file=sys.stderr)
        return False
    if session_type == "wayland" and not os.getenv("WAYLAND_DISPLAY"):
        print("Error: Wayland session detected but WAYLAND_DISPLAY is not set.", file=sys.stderr)
        return False
    
    return True

def find_available_browsers() -> List[str]:
    """
    Detect installed browsers on the system and return a list of executable commands
    Priority: chromium > google-chrome > firefox
    """
    browsers = [
        "chromium-browser",  # Chromium for Debian/Ubuntu-based systems
        "chromium",          # Generic Chromium
        "google-chrome",     # Google Chrome
        "google-chrome-stable",  # Chrome Stable version
        "firefox"            # Firefox
    ]
    
    available = []
    for browser in browsers:
        # Use 'which' command to check if browser is installed
        try:
            subprocess.run(
                ["which", browser],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            available.append(browser)
        except subprocess.CalledProcessError:
            continue
    
    return available

def get_url() -> str:
    """
    Get the URL to open in the browser. Reads from API (not config file)
    to avoid race conditions with config file writes during startup.
    """
    import urllib.request
    try:
        req = urllib.request.Request(f"{URL}/api/v1.0/get-config", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            config = json.loads(r.read().decode())
        dashboard_page = config.get('data', config).get('system', {}).get('default_dashboard_page', '')
        if dashboard_page:
            return f"{URL}/{dashboard_page}"
    except Exception:
        pass
    return URL

def get_browser_fullscreen_args(browser: str) -> List[str]:
    """
    Return fullscreen arguments corresponding to different browsers
    """
    url = get_url()
    
    # Chrome/Chromium fullscreen arguments
    if "chrome" in browser or "chromium" in browser:
        return [
            browser,
            "--start-fullscreen",                # Launch in fullscreen mode
            "--password-store=basic",            # Use basic password store
            # "--kiosk",                           # Kiosk mode (no address bar/menus)
            "--disable-session-crashed-bubble",  # Disable session crashed bubble
            "--no-session-restore",              # Disable session restore
            "--new-window",                      # Open in a new window
            "--no-first-run",                    # Skip first-run setup
            "--no-default-browser-check",        # Skip default browser check
            url
        ]
    # Firefox fullscreen arguments
    elif "firefox" in browser:
        return [
            browser,
            # "-kiosk",                       # Kiosk fullscreen mode
            "--password-manager=disabled",  # Disable password manager
            "-new-window",                  # Open in a new window
            url
        ]
    else:
        return [browser, url]

def launch_browser() -> bool:
    """
    Launch browser and open the specified URL in fullscreen mode
    Return: Whether launch was successful
    """
    # Find available browsers
    available_browsers = find_available_browsers()
    if not available_browsers:
        print("Error: No supported browsers detected (Chrome/Chromium/Firefox).", file=sys.stderr)
        return False
    
    # Use the first detected browser
    selected_browser = available_browsers[0]
    print(f"Detected available browser: {selected_browser}")
    
    # Build launch command
    cmd = get_browser_fullscreen_args(selected_browser)
    print(f"Executing command: {' '.join(cmd)}")
    
    try:
        # Launch browser in background (non-blocking, runs independently)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"Successfully launched {selected_browser}, opened {cmd[-1]} in fullscreen mode.")
        return True
    except Exception as e:
        print(f"Failed to launch browser: {str(e)}", file=sys.stderr)
        return False

def wait_for_dashboard(timeout=30):
    """Wait for dashboard HTTP server to be ready before launching browser."""
    import urllib.request
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{URL}/api/v1.0/get-device-info", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    print(f"Warning: Dashboard not ready after {timeout}s, launching anyway.", file=sys.stderr)
    return False

def run():
    """Main function"""
    # 1. Check if system is Linux
    if not sys.platform.startswith("linux"):
        print("Error: This script only supports Linux systems.", file=sys.stderr)
        sys.exit(1)

    # 2. New: Check if in desktop environment (core modification)
    if not check_desktop_environment():
        sys.exit(1)

    # 3. Warning: Avoid running with root privileges
    if os.geteuid() == 0:
        print("Warning: Running browsers as root is not recommended, may cause permission/security issues.", file=sys.stderr)

    # 4. Wait for dashboard to be ready
    wait_for_dashboard()

    # 5. Launch browser
    if not launch_browser():
        sys.exit(1)

if __name__ == "__main__":
    run()