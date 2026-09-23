"""Run with Python 3.11+; offline desktop demo needs only the standard library."""
import argparse
import sys

from crisisconnect.config import Settings, SafeError
from crisisconnect.core import Session, load_json
from crisisconnect.azure import AzureServices
from crisisconnect.voice import VoiceLive
from crisisconnect.engine import Engine
from crisisconnect.delivery import Delivery


def main():
    parser = argparse.ArgumentParser(description="CrisisConnect standalone disaster navigator prototype")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="Offline simulation (default)")
    mode.add_argument("--live", action="store_true", help="Use Azure services with operator credentials")
    parser.add_argument("--headless", action="store_true", help="Run a fictional demo scenario without a desktop display")
    parser.add_argument("--scenario", choices=("flood", "wildfire", "urgent", "appeal"), default="flood")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--seed-search", action="store_true", help="Explicitly create/update the configured Azure index with reviewed public guidance")
    args = parser.parse_args()
    if args.headless and args.live:
        parser.error("Headless scenarios are offline only; use the GUI to consent to live data processing.")
    settings = Settings.from_env("live" if args.live else "demo")
    services = AzureServices(settings)
    voice = VoiceLive(settings, services)
    engine = Engine(settings, services, voice)
    if args.seed_search:
        if not args.live:
            parser.error("--seed-search requires --live and will write to the configured Azure Search index.")
        try:
            records = load_json("resources.json")
            from crisisconnect.core import usable_record
            if any(not usable_record(r, "VA", "Richmond city") for r in records):
                raise SafeError("Bundled guidance is stale or invalid. Re-review sources and update review/expiry dates before indexing.")
            print("Indexed", services.index_documents(records), "public guidance records. No disaster declarations or user data uploaded.")
            return 0
        except SafeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.headless:
        scenario = load_json("scenarios.json")[args.scenario]
        session = Session(state=scenario["state"], county=scenario["county"], event=scenario["event"],
                          incident_date=scenario["incident_date"], language=args.language, scenario=args.scenario)
        print(engine.reply(session, scenario["text"])["plan"])
        return 0
    try:
        import tkinter as tk
        from crisisconnect.gui import App
        root = tk.Tk()
        App(root, settings, engine, Delivery(settings, services), voice)
        root.mainloop()
    except ImportError:
        print("Tkinter is required. On Ubuntu/Debian install python3-tk; on Windows use a Python installation with Tcl/Tk.", file=sys.stderr)
        return 1
    except Exception as exc:
        # Avoid raw exception details that may contain OS paths or provider data.
        print("Desktop could not open. Run on a graphical desktop, or use --demo --headless --scenario flood.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
