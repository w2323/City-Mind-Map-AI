# main.py — CityMind CLI Entry Point
# Runs the full backend simulation from terminal.
# No GUI dependencies. Pure backend execution.
#
# Usage:
#   python main.py                     # Default 20-step simulation
#   python main.py --steps 10          # Custom step count
#   python main.py --seed 42           # Deterministic seed
#   python main.py --verbose           # Detailed logging
#   python main.py --seed 42 --steps 20 --verbose

import sys
import os
import argparse

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from config.simulation_config import SimConfig
from core.simulation_engine import Simulation


def main():
    parser = argparse.ArgumentParser(
        description="CityMind — AI-Based Smart City Simulation (Backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                        Run default 20-step simulation
  python main.py --steps 10             Run 10 steps only
  python main.py --seed 42              Reproducible simulation
  python main.py --seed 42 --verbose    Detailed output with fixed seed
        """
    )
    parser.add_argument("--steps", type=int, default=SimConfig.MAX_STEPS,
                        help=f"Number of simulation steps (default: {SimConfig.MAX_STEPS})")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility (default: non-deterministic)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose/debug logging")
    parser.add_argument("--json", action="store_true",
                        help="Output final state as JSON (for API integration)")

    args = parser.parse_args()

    # Apply CLI overrides to config
    SimConfig.MAX_STEPS = args.steps
    if args.seed is not None:
        SimConfig.SEED = args.seed

    # Banner
    print("=" * 60)
    print("  CityMind — AI-Based Smart City Simulation")
    print("  Backend-Only Mode (No GUI)")
    print(f"  Steps: {args.steps} | Seed: {args.seed or 'random'}")
    print("=" * 60)
    print()

    # Run simulation
    sim = Simulation(seed=args.seed, verbose=args.verbose)

    try:
        state = sim.run_full()
    except RuntimeError as e:
        print(f"\n[FATAL] Simulation failed: {e}")
        sys.exit(1)

    # Print metrics summary
    print()
    print(sim.events.metrics.summary())

    # Print log file location
    print(f"\n  Log file: {sim.events.log_file_path}")

    # Optional JSON output
    if args.json:
        import json
        json_path = os.path.join("logs", "final_state.json")
        with open(json_path, "w") as f:
            json.dump(state.to_dict(), f, indent=2, default=str)
        print(f"  JSON state: {json_path}")

    print()

    # Return exit code based on success
    return 0 if state.is_complete else 1


if __name__ == "__main__":
    sys.exit(main())