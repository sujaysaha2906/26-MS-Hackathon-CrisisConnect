import copy
from datetime import date
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from .config import SafeError
from .core import Session, EVENTS, LANGUAGES, load_json, plan_hash, redact
from .delivery import Approval
from .voice import Recorder


class App:
    def __init__(self, root, settings, engine, delivery, voice):
        self.root, self.settings, self.engine = root, settings, engine
        self.delivery, self.voice = delivery, voice
        self.session = Session()
        self.plan = ""
        self.results = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.recording = False
        self.recorder = Recorder()
        self.record_timer = None
        self.closed = False
        root.title("CrisisConnect Desktop — disaster assistance prototype")
        root.geometry("1120x820")
        root.minsize(850, 650)
        root.configure(bg="#eff3f5")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#eff3f5")
        style.configure("TLabel", background="#eff3f5", foreground="#163943", font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Primary.TButton", background="#087e80", foreground="white")
        style.configure("TNotebook.Tab", padding=(16, 9), font=("Segoe UI", 11))
        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="CrisisConnect", style="Title.TLabel").pack(side="left")
        banner = "OFFLINE DEMO · fictional scenarios · nothing is sent" if settings.mode == "demo" else "AZURE PILOT · cloud processing · operator/testing use only"
        ttk.Label(top, text=banner).pack(side="left", padx=25)
        ttk.Button(top, text="Clear session", command=self.clear).pack(side="right")
        tk.Label(outer, text="Immediate danger or medical emergency? Call 911. This application cannot dispatch help.",
                 bg="#fff0d9", fg="#703f12", padx=12, pady=10, anchor="w", wraplength=950).pack(fill="x", pady=(14, 10))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        talk, plan, send, connections = [ttk.Frame(self.tabs, padding=15) for _ in range(4)]
        for frame, title in zip((talk, plan, send, connections), ("1  Conversation", "2  Action plan", "3  Send / preview", "4  Connections")):
            self.tabs.add(frame, text=title)
        self.talk_tab, self.plan_tab, self.send_tab = talk, plan, send
        self.build_conversation(talk)
        self.plan_box = self.textbox(plan, height=18)
        self.plan_box.pack(fill="both", expand=True)
        self.plan_box.configure(state="disabled")
        row = ttk.Frame(plan)
        row.pack(fill="x", pady=10)
        ttk.Button(row, text="Save action plan…", command=self.save_plan).pack(side="left")
        ttk.Button(row, text="Read first steps aloud (Azure)", command=self.read_aloud).pack(side="left", padx=8)
        ttk.Button(row, text="Stop audio / cancel", command=self.cancel_operation).pack(side="left")
        ttk.Button(row, text="Prepare delivery", command=self.prepare_delivery).pack(side="right")
        ttk.Label(plan, text="Readback is blocked if its returned transcript differs from the approved text. No live human transfer is connected.", wraplength=900).pack(anchor="w")
        self.build_delivery(send)
        self.connection_box = self.textbox(connections, height=17)
        self.connection_box.pack(fill="both", expand=True)
        self.connection_box.insert("end", self.configuration_text())
        self.connection_box.configure(state="disabled")
        ttk.Button(connections, text="Test Azure with synthetic input (may incur charges)", command=self.test_connections).pack(anchor="w", pady=12)
        self.status = tk.StringVar(value="Ready. Load a fictional scenario or type a request.")
        ttk.Label(outer, textvariable=self.status, wraplength=1000).pack(fill="x", pady=(12, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)

    def textbox(self, parent, **kwargs):
        return ScrolledText(parent, wrap="word", font=("Segoe UI", 11), padx=12, pady=10,
                            bg="white", fg="#143840", relief="flat", **kwargs)

    def build_conversation(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.scenarios = load_json("scenarios.json")
        self.scenario_key = tk.StringVar(value="flood")
        ttk.Combobox(row, textvariable=self.scenario_key, values=list(self.scenarios), state="readonly", width=15).pack(side="left")
        ttk.Button(row, text="Load fictional scenario", command=self.load_scenario).pack(side="left", padx=8)
        self.language = tk.StringVar(value="English")
        ttk.Label(row, text="Language").pack(side="left", padx=(12, 5))
        ttk.Combobox(row, textvariable=self.language, values=list(LANGUAGES), state="readonly", width=25).pack(side="left")
        fields = ttk.Frame(parent)
        fields.pack(fill="x", pady=12)
        self.state, self.county, self.event, self.incident = [tk.StringVar(value=v) for v in ("VA", "Richmond city", "flood", "")]
        for i, (label, var, width) in enumerate((("State code", self.state, 5), ("Affected city / county", self.county, 24), ("Event", self.event, 12), ("Date (YYYY-MM-DD)", self.incident, 15))):
            f = ttk.Frame(fields)
            f.pack(side="left", padx=(0, 14))
            ttk.Label(f, text=label).pack(anchor="w")
            if var is self.event:
                ttk.Combobox(f, values=EVENTS, textvariable=var, state="readonly", width=width).pack()
            else:
                ttk.Entry(f, textvariable=var, width=width).pack()
        self.cloud_consent = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, variable=self.cloud_consent,
            text="Live mode: I agree to Azure processing this test conversation. Avoid IDs, bank details, and exact addresses.").pack(anchor="w")
        self.urgent = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, variable=self.urgent, text="I need urgent help / may be in immediate danger").pack(anchor="w", pady=(5, 8))
        ttk.Label(parent, text="Tell CrisisConnect what you need. Microphone transcripts are shown for correction before you submit.", wraplength=900).pack(anchor="w")
        self.input = self.textbox(parent, height=4)
        self.input.pack(fill="x", pady=8)
        actions = ttk.Frame(parent)
        actions.pack(fill="x")
        self.submit = ttk.Button(actions, text="Find my next steps", style="Primary.TButton", command=self.ask)
        self.submit.pack(side="left")
        self.record_button = ttk.Button(actions, text="Record voice (Azure)", command=self.toggle_record)
        self.record_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Human help", command=self.human_help).pack(side="left")
        ttk.Button(actions, text="Stop / cancel", command=self.cancel_operation).pack(side="right")
        self.chat = self.textbox(parent, height=7)
        self.chat.pack(fill="both", expand=True, pady=(12, 0))
        self.chat.insert("end", "CrisisConnect: We can find a starting point together. Confirm the affected city/county and incident date. No eligibility is determined here.\n")
        self.chat.configure(state="disabled")

    def build_delivery(self, parent):
        ttk.Label(parent, text="Review exactly what will be sent. No conversation transcript is attached.", wraplength=950).pack(anchor="w")
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=10)
        self.channel = tk.StringVar(value="email")
        ttk.Combobox(row, textvariable=self.channel, values=("email", "sms"), state="readonly", width=10).pack(side="left")
        ttk.Label(row, text="Destination").pack(side="left", padx=10)
        self.destination = tk.StringVar()
        ttk.Entry(row, textvariable=self.destination, width=40).pack(side="left")
        ttk.Button(row, text="Make short SMS", command=self.short_sms).pack(side="right")
        self.delivery_box = self.textbox(parent, height=15)
        self.delivery_box.pack(fill="both", expand=True)
        self.send_consent = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, variable=self.send_consent,
            text="I reviewed this message and authorize sending it to this destination. I have the recipient's permission.").pack(anchor="w", pady=10)
        self.destination.trace_add("write", lambda *_: self.send_consent.set(False))
        self.channel.trace_add("write", lambda *_: self.send_consent.set(False))
        self.delivery_box.bind("<KeyPress>", lambda e: self.send_consent.set(False))
        ttk.Button(parent, text="Preview simulated send" if self.settings.mode == "demo" else "Confirm and send to allowed tester",
                   style="Primary.TButton", command=self.send).pack(anchor="w")
        ttk.Label(parent, text="SMS/email are not end-to-end confidential. Real delivery requires an operator allowlist and explicit confirmation. No OTP or public-user delivery is implemented.",
                  wraplength=950).pack(anchor="w", pady=10)

    def log(self, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", text + "\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def show_error(self, exc):
        msg = str(exc) if isinstance(exc, (SafeError, ValueError)) else "Operation failed. Check setup and use the text/demo fallback. No service payload was logged."
        self.status.set(msg)
        messagebox.showerror("CrisisConnect", msg)

    def run(self, work, done):
        if self.busy or self.recording:
            messagebox.showinfo("CrisisConnect", "Finish or stop the current operation first.")
            return
        self.busy = True
        self.cancel = threading.Event()
        self.submit.configure(state="disabled")
        self.status.set("Working… No conversation is written to disk.")
        cancel = self.cancel
        def worker():
            try: result = (True, work(cancel))
            except Exception as exc: result = (False, exc)
            self.results.put((result, done, cancel))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                (ok, value), callback, cancel = self.results.get_nowait()
                self.busy = False
                self.submit.configure(state="normal")
                if cancel.is_set():
                    self.status.set("Cancelled. Already submitted cloud requests cannot be recalled.")
                elif ok:
                    self.status.set("Ready.")
                    callback(value)
                else:
                    self.show_error(value)
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def require_cloud_consent(self):
        if self.settings.mode == "live" and not self.cloud_consent.get():
            raise SafeError("Select the Azure-processing consent checkbox before a live test.")

    def load_scenario(self):
        if self.busy or self.recording:
            return
        key = self.scenario_key.get()
        s = self.scenarios[key]
        self.session = Session(scenario=key)
        for var, name in ((self.state,"state"), (self.county,"county"), (self.event,"event"), (self.incident,"incident_date")):
            var.set(s[name])
        self.input.delete("1.0", "end")
        self.input.insert("1.0", s["text"])
        self.urgent.set(key == "urgent")
        self.plan = ""
        self.replace(self.plan_box, "")
        self.delivery_box.delete("1.0", "end")
        self.send_consent.set(False)
        self.status.set(s["label"] + " — training input, not a live disaster declaration.")

    def ask(self):
        try:
            self.require_cloud_consent()
            text = self.input.get("1.0", "end").strip()
            if not text:
                raise SafeError("Type a request or load a fictional scenario first.")
            s = copy.deepcopy(self.session)
            new_geo = (self.state.get().strip().upper(), self.county.get().strip(), self.event.get(), self.incident.get().strip())
            if new_geo != (s.state, s.county, s.event, s.incident_date):
                s.needs.clear()
            s.state, s.county, s.event, s.incident_date = new_geo
            s.language = LANGUAGES[self.language.get()]
            s.urgent = self.urgent.get()
            s.validate()
            if s.urgent:
                messagebox.showwarning("Urgent help", "If you are in immediate danger or have a medical emergency, call 911 now. CrisisConnect cannot dispatch help.")
            self.log("You: " + redact(text))
            def finished(result):
                self.session = s
                self.plan = result["plan"]
                self.urgent.set(s.urgent)
                if result["intent"]["urgent"]:
                    messagebox.showwarning("Urgent help", "Possible urgent need detected. For immediate danger or a medical emergency, call 911. No dispatch has occurred.")
                self.replace(self.plan_box, self.plan)
                self.delivery_box.delete("1.0", "end")
                self.send_consent.set(False)
                self.log("CrisisConnect: Identified needs: " + ", ".join(result["intent"]["needs"]) + ". Review your action plan and correct anything I misunderstood.")
                self.tabs.select(self.plan_tab)
            self.run(lambda cancel: self.engine.reply(s, text, cancel), finished)
        except Exception as exc:
            self.show_error(exc)

    def replace(self, box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def toggle_record(self):
        if self.recording:
            self.stop_record()
            return
        if self.busy:
            return
        try:
            if self.settings.mode != "live":
                raise SafeError("Offline demo uses typed/sample utterances. Real microphone recognition needs --live, dependencies, and Azure credentials.")
            self.require_cloud_consent()
            self.recorder.start()
            self.recording = True
            self.record_button.configure(text="Stop recording & transcribe")
            self.status.set("RECORDING locally — maximum 30 seconds. Stop to send this audio to Azure for transcription.")
            self.record_timer = self.root.after(30000, self.stop_record)
        except Exception as exc:
            self.show_error(exc)

    def stop_record(self):
        if not self.recording:
            return
        if self.record_timer:
            self.root.after_cancel(self.record_timer)
            self.record_timer = None
        audio = self.recorder.stop()
        self.recording = False
        self.record_button.configure(text="Record voice (Azure)")
        lang = LANGUAGES[self.language.get()]
        def done(text):
            self.input.delete("1.0", "end")
            self.input.insert("1.0", text)
            self.status.set("Review/correct the transcript, then choose Find my next steps.")
        self.run(lambda cancel: self.voice.transcribe(audio, lang, cancel), done)

    def read_aloud(self):
        try:
            if not self.plan:
                raise SafeError("Create an action plan first.")
            if self.settings.mode != "live":
                raise SafeError("Audio readback is an Azure integration. Offline demo provides the written plan.")
            self.require_cloud_consent()
            # Omit URLs and avoid cutting a sentence; read bounded complete lines.
            selected = []
            for line in self.plan.splitlines():
                if "https://" in line or not line.strip():
                    continue
                if len(" ".join(selected + [line])) > 1200:
                    break
                selected.append(line)
            text = " ".join(selected)
            self.run(lambda cancel: self.voice.speak(text, cancel), lambda _: self.status.set("Readback finished."))
        except Exception as exc:
            self.show_error(exc)

    def save_plan(self):
        if not self.plan:
            messagebox.showinfo("CrisisConnect", "Create an action plan first.")
            return
        name = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="crisisconnect-action-plan.txt", filetypes=[("Text", "*.txt")])
        if name:
            try:
                with open(name, "w", encoding="utf-8") as f: f.write(self.plan)
                self.status.set("Plan saved where you chose. This local copy remains until you delete it.")
            except OSError:
                self.show_error(SafeError("Could not save the plan. Choose a writable folder."))

    def prepare_delivery(self):
        if not self.plan:
            return
        self.delivery_box.delete("1.0", "end")
        self.delivery_box.insert("1.0", self.plan)
        self.send_consent.set(False)
        self.tabs.select(self.send_tab)

    def short_sms(self):
        if not self.plan:
            return
        s = self.session
        text = ("CRISISCONNECT SIMULATION. No real incident verified.\n" if self.settings.mode == "demo" else "CRISISCONNECT TEST PROTOTYPE. Verify with the agency.\n")
        if s.urgent:
            text += "Immediate danger or medical emergency: call 911. No dispatch has occurred.\n"
        text += "Possible next step: contact FEMA at 800-621-3362 or visit https://www.disasterassistance.gov/ .\n"
        if "shelter" in s.needs:
            text += "Shelter referrals: 211 where available. Confirm availability before travel.\n"
        text += "Ask about your affected location, incident dates, required documents, and deadlines. No eligibility is confirmed. FEMA applications are free."
        self.channel.set("sms")
        self.delivery_box.delete("1.0", "end")
        self.delivery_box.insert("1.0", text)
        self.send_consent.set(False)
        self.status.set("Short SMS prepared in English. Review or edit before consent. The full translated plan is available by email/download.")

    def send(self):
        if self.busy:
            return
        body = self.delivery_box.get("1.0", "end").strip()
        target = self.destination.get().strip()
        a = Approval(self.channel.get(), target, plan_hash(body), self.send_consent.get())
        if not a.consent:
            self.show_error(SafeError("Review the message and check the delivery consent box first."))
            return
        if self.settings.mode == "live" and not messagebox.askyesno("Confirm real transmission", f"Send this exact reviewed {a.channel} to:\n{target}\n\nIt may be visible on the recipient's shared device. Continue?"):
            return
        self.run(lambda cancel: self.delivery.send(body, a), lambda r: self.status.set(r["status"] + ": " + r["detail"]))
        self.send_consent.set(False)

    def configuration_text(self):
        lines = ["SERVICE CONFIGURATION — values/credentials are intentionally hidden", ""]
        for k, v in self.settings.checks().items():
            lines.append(f"{k}: {v}")
        lines += ["", "Demo mode never calls Azure and does not send messages.",
                  "Live mode uses your local Azure sign-in. This build is for the operator's computer, not public distribution with shared credentials.",
                  "Voice is push-to-talk with transcript confirmation; not full duplex.",
                  "Raw audio/transcripts are not deliberately saved by this app. Azure/OS processing and retention still apply.",
                  "No live declaration feed, shelter capacity, eligibility approval, dispatch, callback queue, or phone transfer is implemented.",
                  "See docs/DEPLOY_AND_TEST.md before enabling live APIs."]
        return "\n".join(lines)

    def test_connections(self):
        if self.settings.mode != "live":
            self.status.set("Demo mode: all cloud calls disabled. Run the included local integration tests instead.")
            return
        if not messagebox.askyesno("Synthetic Azure test", "Send only synthetic test input to Voice Live, Translator, and AI Search? This may incur Azure charges. No email/SMS will be sent."):
            return
        def work(cancel):
            intent = self.voice.classify("I need shelter after a flood.", cancel)
            if cancel.is_set(): raise SafeError("Operation cancelled.")
            translation = self.engine.azure.translate("Find help.", "es")
            if cancel.is_set(): raise SafeError("Operation cancelled.")
            records = self.engine.azure.search(Session(needs={"shelter"}))
            return f"Voice schema: OK; Translator: OK; fresh Search matches: {len(records)}. ACS not contacted."
        self.run(work, lambda r: self.status.set(r))

    def human_help(self):
        messagebox.showinfo("Human assistance — referral only", "FEMA assistance: 800-621-3362\nIn-person recovery centers: https://egateway.fema.gov/ESF6/DRCLocator\nLocal shelter referrals: 211 where available\nImmediate danger / medical emergency: 911\n\nAsk about interpreters/accessibility and current service hours. No call, transfer, or dispatch is made by this app.")

    def cancel_operation(self):
        if self.recording:
            self.recorder.stop()  # Discard locally without submitting audio.
            self.recording = False
            if self.record_timer: self.root.after_cancel(self.record_timer)
            self.record_timer = None
            self.record_button.configure(text="Record voice (Azure)")
        self.cancel.set()
        self.status.set("Stop requested. Already submitted cloud requests or messages cannot be recalled.")

    def clear(self):
        if self.busy:
            messagebox.showinfo("CrisisConnect", "Stop the current operation and wait for it to end before clearing.")
            return
        self.cancel_operation()
        self.session, self.plan = Session(), ""
        self.input.delete("1.0", "end")
        self.replace(self.chat, "Session cleared. No saved download or received message is deleted by this action.")
        self.replace(self.plan_box, "")
        self.delivery_box.delete("1.0", "end")
        self.destination.set("")
        self.cloud_consent.set(False)
        self.send_consent.set(False)
        self.urgent.set(False)
        self.state.set("VA")
        self.county.set("")
        self.incident.set("")
        # Deliberately keep this run's duplicate-send guard until the process exits.
        self.tabs.select(self.talk_tab)
        self.status.set("Session cleared. No application transcript was saved.")

    def close(self):
        self.closed = True
        self.cancel_operation()
        self.root.destroy()
