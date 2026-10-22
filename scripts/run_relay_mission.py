"""Plan or replay a finite-energy relay mission without a server or database."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from robotics.relay.examples import SCENARIO_DIR
from robotics.services.relay_service import continue_mission, plan_mission, replay_mission


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--resume", type=Path, help="continue a checked saved report from its current state")
    parser.add_argument("--planner", choices=("auto", "exact", "dispatch"), default="auto")
    parser.add_argument("--actions", type=Path, help="replay a JSON list of joint ticks")
    parser.add_argument("--output", type=Path, help="write a new report, never overwrite")
    parser.add_argument("--max-timesteps", type=int, default=1000)
    parser.add_argument("--max-states", type=int, default=150000)
    parser.add_argument("--time-limit", type=float, default=10)
    args = parser.parse_args(argv)
    try:
        if args.output is not None and args.output.exists():
            raise ValueError(f"report already exists: {args.output}")
        limits = dict(max_timesteps=args.max_timesteps, max_states=args.max_states,
                      time_limit=args.time_limit, strategy=args.planner)
        if args.resume:
            if args.scenario or args.actions:
                raise ValueError("--resume uses the saved scenario and executed actions")
            report = continue_mission(json.loads(args.resume.read_text(encoding="utf-8-sig")), **limits)
        else:
            scenario = json.loads((args.scenario or SCENARIO_DIR / "energy_relay.json").read_text(encoding="utf-8-sig"))
            if args.actions:
                actions = json.loads(args.actions.read_text(encoding="utf-8-sig"))
                report = replay_mission(scenario, actions)
            else:
                report = plan_mission(scenario, **limits)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({"success": report["success"], "status": report["status"],
                          **report["metrics"]}, ensure_ascii=False))
        return 0 if report["success"] else 2
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
