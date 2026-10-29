# main.py — CityMind 2D Desktop Application Entry Point
# Launch the native Pygame 2D operations center.
#
# Usage:
#   python frontend-2d-pygame/main.py                     # Connects to running backend
#   python frontend-2d-pygame/main.py --auto-backend      # Automatically starts backend if not running
#   python frontend-2d-pygame/main.py --screen route_lab
#   python frontend-2d-pygame/main.py --screen diagnostics

import os
import sys
import time
import argparse
import subprocess
import urllib.request
from urllib.parse import urlparse

# Ensure frontend-2d-pygame and project root are in Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.application import Application
from app.state import ActiveScreen


def is_backend_alive(url: str, timeout: float = 1.0) -> bool:
    """Quick HTTP probe to check if the backend is already running."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="CityMind — 2D Operations Center (Pygame Desktop Application)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Screens available via --screen:
  dashboard     Overview KPIs, active operations, live feed
  city_map      Interactive 2D city grid, node & edge inspector
  route_lab     Interactive pathfinding comparison (A* vs Reference Dijkstra)
  god_mode      Deliberate flood testing and consequence simulation
  ambulance     Ambulance allocation, mission state, reachability
  heatmap       Multi-layer heatmaps (risk, population, police, ambulance)
  police        Police deployment from ML pipeline
  metrics       Full simulation metrics and backend event history
  diagnostics   Graph integrity, routing correctness & backend health audits
        """
    )
    parser.add_argument(
        "--backend-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Base URL of the CityMind FastAPI backend (default: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--auto-backend",
        action="store_true",
        help="Automatically start the backend uvicorn server if not already running"
    )
    parser.add_argument(
        "--screen",
        type=str,
        default="dashboard",
        choices=[
            "dashboard", "city_map", "route_lab", "god_mode",
            "ambulance", "heatmap", "police", "metrics", "diagnostics"
        ],
        help="Initial screen to display (default: dashboard)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    screen_map = {
        "dashboard":   ActiveScreen.DASHBOARD,
        "city_map":    ActiveScreen.CITY_MAP,
        "route_lab":   ActiveScreen.ROUTE_LAB,
        "god_mode":    ActiveScreen.GOD_MODE,
        "ambulance":   ActiveScreen.AMBULANCE,
        "heatmap":     ActiveScreen.RISK_HEATMAP,
        "police":      ActiveScreen.POLICE,
        "metrics":     ActiveScreen.METRICS,
        "diagnostics": ActiveScreen.DIAGNOSTICS,
    }

    initial_screen = screen_map.get(args.screen, ActiveScreen.DASHBOARD)
    backend_proc = None

    # Handle --auto-backend
    if args.auto_backend:
        if not is_backend_alive(args.backend_url):
            print("[AUTO-BACKEND] Backend not detected on " + args.backend_url + ". Launching backend process...")
            target = urlparse(args.backend_url)
            if target.hostname not in ("127.0.0.1", "localhost", "::1") or target.scheme != "http" or target.path not in ("", "/"):
                print("[AUTO-BACKEND] Auto-start requires a local HTTP backend URL.")
                return 1
            backend_cmd = [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", target.hostname, "--port", str(target.port or 80)]
            backend_proc = subprocess.Popen(backend_cmd, cwd=parent_dir, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            
            # Wait for backend to come alive (up to 12s)
            t0 = time.time()
            alive = False
            while time.time() - t0 < 12.0:
                time.sleep(0.5)
                if is_backend_alive(args.backend_url):
                    alive = True
                    break
            if alive:
                print("[AUTO-BACKEND] Backend successfully initialized and responding!")
            else:
                print("[AUTO-BACKEND] Warning: Backend process started but did not respond within 12s.")
        else:
            print("[AUTO-BACKEND] Backend is already running.")

    print("=" * 65)
    print("  CityMind — 2D Operations Center (Pygame Desktop)")
    print(f"  Backend URL:    {args.backend_url}")
    print(f"  Initial Screen: {initial_screen.value}")
    print("=" * 65)
    print("Launching Pygame application...")

    app = None
    try:
        app = Application(backend_url=args.backend_url)
        if initial_screen != ActiveScreen.DASHBOARD:
            app.switch_screen(initial_screen)
        app.run()
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    except Exception as e:
        print(f"\n[ERROR] Application exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if app is not None:
            app.close()
        if backend_proc is not None:
            print("\nShutting down auto-started backend process...")
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                backend_proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
