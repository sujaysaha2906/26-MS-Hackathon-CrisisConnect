"""Launch the voice-only crisis chatbot with Python 3.11+."""
import argparse
import sys

from crisisconnect.config import Settings, SafeError
from crisisconnect.azure import AzureServices
from crisisconnect.voice import VoiceLive


def main():
    parser = argparse.ArgumentParser(description="CrisisConnect voice-only crisis chatbot")
    parser.add_argument("--live", action="store_true", help="Use Azure voice (the default)")
    args = parser.parse_args()
    try:
        settings = Settings.from_file("live")
    except SafeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not settings.voice_endpoint:
        print("Set AZURE_VOICELIVE_ENDPOINT in config.json before starting the voice chatbot. See README.md.", file=sys.stderr)
        return 1
    try:
        import tkinter as tk
        from crisisconnect.gui import App
        root = tk.Tk()
        App(root, settings, VoiceLive(settings, AzureServices(settings)))
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
