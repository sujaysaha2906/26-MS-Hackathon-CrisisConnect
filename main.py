"""Launch the voice-only crisis chatbot with Python 3.11+."""
import argparse
import sys

from crisisconnect.config import Settings, SafeError
from crisisconnect.azure import AzureServices
from crisisconnect.voice import VoiceLive


def main():
    parser = argparse.ArgumentParser(description="CrisisConnect voice-only crisis chatbot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="Use Azure voice (the default)")
    mode.add_argument("--demo", action="store_true", help="Basic local voice chat; no Azure, FEMA, or location checks")
    args = parser.parse_args()
    try:
        settings = Settings(mode="demo") if args.demo else Settings.from_file("live")
    except SafeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not args.demo and not settings.voice_endpoint:
        print("Set AZURE_VOICELIVE_ENDPOINT in config.json before starting the voice chatbot. See README.md.", file=sys.stderr)
        return 1
    try:
        import tkinter as tk
        from crisisconnect.gui import App
        root = tk.Tk()
        if args.demo:
            from crisisconnect.demo import LocalVoice
            voice = LocalVoice()
        else:
            voice = VoiceLive(settings, AzureServices(settings))
        App(root, settings, voice)
        root.mainloop()
    except ImportError:
        print("Install Python with Tkinter support to open the voice interface.", file=sys.stderr)
        return 1
    except Exception:
        print("The voice interface could not open. Check the graphical desktop environment.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
