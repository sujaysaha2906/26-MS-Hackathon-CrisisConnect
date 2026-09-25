# Deploy and test the voice chatbot

See [README.md](../README.md) for the wellbeing, location, FEMA, and voice-conversation workflow and its matching rules.

For basic local voice chat, run `scripts\win\setup_demo.cmd` once followed by `scripts\win\start_demo.cmd`, or the Linux `setup_demo.sh` and `start_demo.sh` scripts. Demo mode does not need Azure configuration and bypasses all location/FEMA checks. Verify the local-demo banner, microphone capture, spoken replies, repeat, stop, and restart with networking disconnected. The steps below apply to live mode.

## Setup

1. Create `venv` with the platform script and install `requirements-live.txt`.
2. Set the Voice Live endpoint and optional voice settings in `config.json`. Configure `LOCATION_MAX_RETRIES` and `FEMA_LOOKBACK_DAYS` as appropriate.
3. Sign in with Azure CLI using an account with access to the Voice Live resource.
4. Enable device location and the app's permission. Linux additionally needs GeoClue, a desktop permission agent, and `bash scripts/linux/setup_location.sh`.
5. Start with `scripts\win\start_chat.cmd` or `bash scripts/linux/start_chat.sh`.

## Manual checks

- Answer yes to **Are you okay?** Verify the closing phrase, with no location or FEMA lookup.
- Answer no. Provide and confirm a town/state without sharing an address.
- With location disabled, decline enabling it and say **continue**. Verify FEMA lookup uses the supplied location as unverified.
- Enable location and say **check again**. Verify a fresh fix is requested.
- Check an in-range location and a mismatching location. Verify the configured correction budget ends the conversation on persistent mismatches.
- Use synthetic service responses to check a matching declaration, an empty successful response, an outage, and malformed data. An outage must not produce a no-disaster claim.
- Verify the first AI question occurs only after a matching declaration. Fixed speech/transcription calls occur earlier in the current implementation.
- Confirm no model output outside the reviewed question set is spoken.
- Stop during capture, lookup, transcription, and playback. Late results must not restart the conversation.
- Repeat a question and verify the state and retry counter do not advance.
- Start again and verify answers from the old session are absent.

Actual microphone/speaker, OS location permission, Census/FEMA networking, and Azure end-to-end checks must be completed on the deployment machine. Review the README's town-reference-point and FEMA incident-date limitations before deployment.

## Windows build

Run `scripts\win\build_windows.cmd` on Windows after the source-mode checks pass. Test the complete `dist\CrisisConnectDesktop` folder. Edit `config.json` beside the executable. Never bundle credentials or conversation data.
