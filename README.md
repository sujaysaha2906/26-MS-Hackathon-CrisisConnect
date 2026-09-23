# CrisisConnect Desktop — Disaster Assistance Navigator

**Standalone desktop prototype · v0.1.0 · September 23, 2026**

Start here. This release follows the decision to build a desktop application first. Phone/mobile and web applications are future work. The earlier web-first architecture guide is a future architecture reference, not the deployment path for this package.

CrisisConnect is a Python/Tkinter desktop app with an offline disaster simulation and optional Azure adapters. No web browser, Docker, hosted website, or mobile app is required to run it. Internet and your Azure account are required for live cloud APIs.

## 1. Run the dummy app now

### Windows

Install Python 3.11 or later with the Tcl/Tk component. Extract this entire ZIP to a folder. Open a terminal in the extracted `crisisconnect_desktop` folder, then run:

```powershell
py -3 main.py --demo
```

Alternatively double-click `start_demo.cmd`. No pip packages or Azure credentials are needed for the offline GUI.

### Linux

Install Python 3.11+ and Tkinter through your operating system. On Debian/Ubuntu, the Tkinter package is `python3-tk`.

```bash
python3 main.py --demo
```

### macOS

Use Python 3.11+ with a working Tkinter installation, then run `python3 main.py --demo`. Native macOS packaging and microphone permissions have not been tested for this release.

## 2. Try the fictional flood

1. In **Conversation**, choose `flood` and click **Load fictional scenario**.
2. The app fills Richmond city, VA, a fictional flood date, and a displaced renter's request.
3. Click **Find my next steps**.
4. Review the **Action plan** with shelter, food, recovery, missing-document guidance, and official links.
5. Click **Prepare delivery**.
6. Use a dummy address such as `tester@example.com`, review the text, and tick consent.
7. Click **Preview simulated send**. The result must say `simulated`; no message is transmitted.
8. Try the same send again: duplicate protection should block it.
9. Try `urgent`, `wildfire`, and `appeal` scenarios. All incidents are fictional.

The demo uses a frozen September 23, 2026 content snapshot. It does not represent current declarations, live shelter availability, or current deadlines.

## 3. What is implemented

| Capability | Offline demo | Azure live mode |
|---|---|---|
| Desktop GUI and text input | Working | Working |
| Scenario-based needs matching | Local rules | Voice Live model returns validated need categories |
| Microphone transcription | Not simulated as real recognition | Implemented Voice Live WebSocket adapter; requires audio hardware and Azure |
| Spoken response | Written plan only | Buffered Voice Live readback, released only if returned transcript matches approved text |
| Government guidance | Bundled reviewed general guidance | Azure AI Search with geography, approval, and freshness filters |
| Spanish plan | Bundled Spanish text | Azure Translator |
| Bengali plan | Disabled | Translator integration; language/voice quality needs live evaluation |
| Email and SMS | No-network simulation | ACS adapters with consent, tester allowlist, and send flag |
| Human help | Official referrals | Same; no live queue or transfer |
| Disaster detection / eligibility | Not implemented | Not implemented; incident/location are user supplied |

**Live adapters are implemented, but no real Azure tenant, microphone, speaker, or recipient was available for validation here.** Local protocol/adapter tests are not a claim of a completed Azure end-to-end test.

## 4. Enable Azure and package for deployment

Follow **[docs/DEPLOY_AND_TEST.md](docs/DEPLOY_AND_TEST.md)**. It includes:

- Azure resource setup and permissions;
- environment variables, sign-in, and optional dependency installation;
- a public-guidance search-index setup command;
- staged voice, translation, search, email, and SMS tests;
- Windows executable packaging;
- a realistic disaster exercise and a real-event operating checklist;
- troubleshooting and limitations.

## 5. Run tests without a GUI

```bash
python -m unittest discover -s tests -v
python main.py --demo --headless --scenario flood
python main.py --demo --headless --scenario urgent
python main.py --demo --headless --scenario flood --language es
```

The optional `websockets` package is needed for the local voice protocol tests. If it is missing, those tests report `skipped`. All other tests use the standard library; no Azure account or real message delivery is used.

The included [test report](docs/TEST_REPORT.md) records what was actually executed.

## 6. Privacy and operational scope

- The application does not deliberately save recordings, transcripts, API response bodies, or contact details to disk.
- Downloaded plans are saved only where the user explicitly chooses.
- Azure processes live audio/text; redaction cannot remove audio already processed.
- Common identifiers are redacted from typed/transcribed requests. This is a basic safeguard, not complete PII detection.
- Live messaging is **operator/tester-only**. There is no public-user authentication, recipient OTP flow, durable message queue, or staffed case management.
- A send guard lasts only for the running process. After an unknown outcome, inspect ACS before restarting and resending.
- Closing/clearing this app cannot erase received SMS/email or all provider/OS copies.
- Keep credentials on the operator's machine; never bundle a service key, credential cache, environment file, or Azure login with an executable.

This is a competition prototype for supervised testing. It must not be presented as an official agency, eligibility authority, emergency dispatch service, or production disaster-response system.

## 7. Project files

| File | Purpose |
|---|---|
| `main.py` | Desktop launch, headless scenarios, explicit Search setup command |
| `crisisconnect/gui.py` | Conversation, plan, delivery, and connection screens |
| `crisisconnect/core.py` | Session validation, privacy filtering, source validation, deterministic summaries |
| `crisisconnect/engine.py` | Demo/live workflow orchestration |
| `crisisconnect/voice.py` | Capture, Voice Live protocol, transcript confirmation, readback validation |
| `crisisconnect/azure.py` | Translator, AI Search, ACS email/SMS adapters |
| `crisisconnect/delivery.py` | Exact-summary approval, tester allowlist, duplicate-attempt guard |
| `data/resources.json` | Reviewed public general guidance; not a disaster availability feed |
| `data/scenarios.json` | Fictional drill inputs; never uploaded to the live index |
| `tests/` | Offline policy, local HTTP/WebSocket, and adapter-contract tests |
| `docs/PROJECT_TRACKER.md` | Milestones, decisions, and next work |
| `build_windows.cmd` | Builds a Windows executable on Windows |

No Windows executable is prebuilt in this archive. Build on your Windows computer using the included script and test the complete output folder.
