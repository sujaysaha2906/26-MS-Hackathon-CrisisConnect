# Wellbeing, location, and FEMA workflow validation - September 25, 2026

Windows, Python 3.14.3, PyCharm-configured test environment.

- Full suite: 78 tests, 71 passed, 7 skipped, no failures.
- New tests cover okay/unclear/not-okay answers; spoken location confirmation; available/disabled/denied/unavailable device readings; enable-and-recheck; the 10 km boundary; configurable correction limits; successful empty FEMA responses versus service failures; declaration county/state/date filtering; safe AI question selection; summary content; session clearing; and cancellation.
- Census and FEMA adapter contracts use synthetic responses. The new Voice Live question-selection request is tested using an in-memory connector, without external packages or Azure credentials.
- Seven pre-existing loopback WebSocket integration tests remain skipped because websockets is unavailable in the test interpreter.
- A read-only public Census smoke test for Richmond, Virginia failed to connect, including outside the sandbox. The live Census-to-FEMA flow therefore remains unverified from this environment.
- Real Windows/Linux location permissions and device fixes, GeoClue deployment, microphone/speaker operation, Azure voice calls, and packaged execution were not tested.
- Geographic matching currently compares a device fix to a public town reference point, with the reference point's county used for FEMA matching. See README.md for large-town and multi-county limitations.

Earlier reports below describe superseded versions.

---
# Voice-only update validation - September 24, 2026

Windows, Python 3.14.3, PyCharm-configured test environment.

- `unittest discover -s tests -v`: 46 tests, 39 passed, 7 skipped, no failures.
- New checks cover crisis-driven question selection, answer progression, blank-answer rejection, redaction, completion, session isolation, ending capture, ignoring late transcription results, and repeating a question.
- Seven local WebSocket tests were skipped because `websockets` is unavailable. Installing the dependency failed with no matching distribution available from the configured package source.
- Actual microphone/speaker operation and Azure end-to-end voice calls were not tested.
- The report below describes the earlier application and does not validate the current voice-only UI.

---
# CrisisConnect Desktop — Test Report

Date: September 23, 2026  
Release: 0.1.0  
Environment: Linux, Python 3.12.14, websockets 16.0; no desktop display or audio devices available to the builder.

## Executed checks

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -v` | 38 tests passed; 0 failures; 0 skips in the builder environment |
| Flood CLI scenario | Passed |
| Wildfire CLI scenario | Passed |
| Urgent-danger CLI scenario | Passed |
| Missing-document/appeal CLI scenario | Passed |
| Spanish flood CLI scenario | Passed |
| Python source parsing | All application and test modules parsed |
| JSON fixtures | Both fixtures parsed |

The test suite verifies offline operation with network access forbidden; redaction of common identifier patterns; geography, approval, and freshness rejection; strict model-result validation; exact-summary consent; allowed-recipient gating; duplicate/uncertain-send protection; Translator request construction and protected fields; AI Search filters and partial index failures; ACS SDK call shapes and honest provider status; local HTTP transport and blocked redirects; and real loopback WebSocket exchanges for Voice Live-shaped events.

## What “API tested” means here

- HTTP and WebSocket transport tests use local synthetic servers.
- Translator/Search tests also capture and inspect the adapter request shapes.
- ACS tests inject simulated SDK clients and inspect calls/results.
- No Azure endpoints were contacted by these tests.
- No SMS or email was sent.
- No simulated result is evidence of Azure tenant permissions, model availability, sender approval, or live service compatibility.

## Not executed

- Real Foundry/Voice Live, Translator, AI Search, or ACS end-to-end calls.
- Real microphone recording or speaker playback.
- Graphical desktop rendering, keyboard/screen-reader accessibility QA.
- Windows executable build, startup, dependency bundling, signing, or installer tests.
- Spanish/Bengali human language review.
- Real disaster declaration lookup, shelter capacity, emergency dispatch, or staffed handoff.
- Load/soak testing, OS privacy review, or public deployment security testing.

These remain explicit release gates in `PROJECT_TRACKER.md`. Use synthetic input and consenting test recipients when completing them.

## Reproduce

```bash
python -m unittest discover -s tests -v
python main.py --demo --headless --scenario flood
python main.py --demo --headless --scenario wildfire
python main.py --demo --headless --scenario urgent
python main.py --demo --headless --scenario appeal
python main.py --demo --headless --scenario flood --language es
```

Install `websockets` (included in `requirements-live.txt`) to run the local voice protocol tests; otherwise those tests skip explicitly. Tests use no real secrets or recipient addresses.

## Project naming update

Renamed the application, Python package, deployment examples, environment variables, and Windows build output to CrisisConnect. Re-ran all 38 automated tests and the headless flood simulation successfully after the rename. Live Azure and hardware validation remain pending.
