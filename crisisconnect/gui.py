"""Voice-only, turn-based crisis interview interface."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from .config import SafeError
from .workflow import Workflow
from .device_location import DeviceLocation
from .public_data import CensusPlaces, FEMADeclarations
from .voice import Recorder


class App:
    def __init__(self, root, settings, voice):
        self.root, self.settings, self.voice = root, settings, voice
        self.locations = DeviceLocation()
        self.places = CensusPlaces()
        self.fema = FEMADeclarations(settings.fema_lookback_days)
        self.interview = None
        self.recorder = Recorder()
        self.results = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.recording = False
        self.closed = False
        self.timer = None
        self.generation = 0
        root.title("CrisisConnect - Voice conversation")
        root.geometry("700x440")
        root.minsize(560, 360)
        frame = ttk.Frame(root, padding=28)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="CrisisConnect", font=("Segoe UI", 26, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Talk about how the crisis has affected you.", font=("Segoe UI", 12)).pack(anchor="w", pady=12)
        ttk.Label(frame, text="A wellbeing check, location confirmation, and FEMA declaration lookup.", wraplength=600).pack(anchor="w")
        self.consent = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, variable=self.consent,
                        text="I agree to Azure voice processing and device location access for this conversation.").pack(anchor="w", pady=14)
        ttk.Label(frame, text="Town/state names are checked with Census and FEMA. Device coordinates stay on this device.", wraplength=600).pack(anchor="w")
        ttk.Label(frame, text="Avoid sharing identity numbers, bank details, or exact addresses.", wraplength=570).pack(anchor="w")
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=20)
        self.start_button = ttk.Button(actions, text="Start conversation", command=self.start)
        self.start_button.pack(side="left")
        self.record_button = ttk.Button(actions, text="Record answer", command=self.toggle_record, state="disabled")
        self.record_button.pack(side="left", padx=6)
        self.repeat_button = ttk.Button(actions, text="Repeat question", command=self.repeat, state="disabled")
        self.repeat_button.pack(side="left")
        ttk.Button(frame, text="End conversation", command=self.end).pack(anchor="w")
        self.status = tk.StringVar(value="Ready. Use headphones and allow microphone access.")
        ttk.Label(frame, textvariable=self.status, wraplength=570).pack(anchor="w", pady=16)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)

    def controls(self):
        available = not self.busy and not self.recording
        self.start_button.configure(state="normal" if available and self.interview is None else "disabled")
        active = self.interview is not None and not self.interview.complete
        self.record_button.configure(state="normal" if self.recording or (available and active) else "disabled",
                                     text="Finish answer" if self.recording else "Record answer")
        self.repeat_button.configure(state="normal" if available and self.interview is not None else "disabled")

    def permitted(self):
        if not self.consent.get():
            self.status.set("Agree to voice processing before starting or continuing.")
            return False
        return True

    def run(self, work, done):
        if self.busy or self.recording:
            return
        self.busy = True
        self.cancel = threading.Event()
        cancel, generation = self.cancel, self.generation
        self.controls()

        def worker():
            try:
                result = (True, work(cancel))
            except Exception as exc:
                result = (False, exc)
            self.results.put((generation, cancel, result, done))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                generation, cancel, (ok, value), done = self.results.get_nowait()
                if generation != self.generation:
                    continue
                self.busy = False
                if not cancel.is_set():
                    if ok:
                        done(value)
                    else:
                        self.status.set(str(value) if isinstance(value, (SafeError, ValueError))
                                        else "Voice operation failed. Check your connection and audio devices, then retry.")
                self.controls()
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def start(self):
        if not self.permitted():
            return
        self.interview = Workflow(self.settings, self.locations, self.places, self.fema, self.voice)
        self.repeat()

    def repeat(self):
        if not self.permitted() or self.interview is None:
            return
        prompt = self.interview.prompt
        self.status.set("Speaking...")
        self.run(lambda cancel: self.voice.speak(prompt, cancel=cancel), self.spoken)

    def spoken(self, _):
        if self.interview.complete:
            self.end()
            self.status.set("Conversation complete. You can start a new conversation.")
        else:
            self.status.set("Your turn. Select Record answer, speak, then select Finish answer.")

    def toggle_record(self):
        if self.recording:
            self.finish_record()
            return
        if self.busy or self.interview is None or not self.permitted():
            return
        try:
            self.recorder.start()
        except SafeError as exc:
            self.status.set(str(exc))
            return
        self.recording = True
        self.status.set("Listening... Select Finish answer when done (30-second limit).")
        self.timer = self.root.after(30000, self.finish_record)
        self.controls()

    def finish_record(self):
        if not self.recording:
            return
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        audio = self.recorder.stop()
        self.recording = False
        self.controls()
        if not self.permitted():
            return
        if self.recorder.overflow:
            self.status.set("Audio was interrupted. Please record your answer again.")
            return
        self.status.set("Listening to your answer...")
        self.run(lambda cancel: self.voice.transcribe(audio, cancel=cancel), self.answered)

    def answered(self, transcript):
        if not self.permitted():
            return
        workflow = self.interview
        self.status.set("Checking your answer...")
        self.run(lambda cancel: workflow.advance(transcript, cancel), self.advanced)

    def advanced(self, workflow):
        if not self.permitted():
            return
        self.interview = workflow
        self.repeat()

    def end(self):
        self.cancel.set()
        self.generation += 1
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if self.recording:
            self.recorder.stop()
        self.recording = False
        self.busy = False
        self.interview = None
        self.status.set("Conversation ended. Session answers cleared.")
        self.controls()

    def close(self):
        self.end()
        self.closed = True
        self.root.destroy()
