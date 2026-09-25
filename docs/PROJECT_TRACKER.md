> Current scope (September 25, 2026): voice-only wellbeing check -> broad location confirmation -> device comparison within 10 km -> recent FEMA declaration lookup -> Voice Live situation summary and reviewed non-confidential questions. Location corrections default to three and are configurable. Disabled/unavailable location can be explicitly skipped. The app now uses public Census/OpenFEMA services rather than fictional scenarios. Initial speech still uses Voice Live; local initial speech is not implemented. Live service, OS permission, and audio validation remain pending. See README.md and TEST_REPORT.md for precise behavior and limitations.
>
> Notes below are historical and superseded by this workflow.
> Current scope (September 24, 2026): voice-only crisis interview. The app asks spoken questions selected from supplied crisis data and receives spoken answers. Action plans, messaging, translation, and search are outside the current product. The implementation uses fictional data pending confirmation of the production dataset. Questions are predefined; adaptive follow-ups and real Azure/audio validation remain pending.
>
> The tracker below describes the superseded September 23 scope and is retained as historical context.
# CrisisConnect Desktop — Project Tracker

Project name confirmed: **CrisisConnect**. Standalone desktop first; phone and web applications are planned future extensions.

Updated September 23, 2026 · v0.1.0

## Scope decision

The current deliverable is a **standalone desktop application**. Mobile/phone apps and a web app are future roadmap items for the competition submission. This supersedes the earlier guide's recommendation to build a web frontend first. Azure remains the planned cloud API provider.

## Status

| Work item | Status | Evidence / next step |
|---|---|---|
| Standalone Python/Tkinter source | Implemented | `main.py`, `crisisconnect/gui.py` |
| Offline disaster scenarios | Implemented and logic-tested | Four fictional scenarios |
| Source-grounded deterministic plans | Implemented and tested | General guidance; geography/freshness/approval filters |
| Voice Live protocol adapter | Implemented and tested against a local server | Real Azure and audio devices not tested |
| Azure model need classification | Implemented with strict output validation | Live tenant test pending |
| Translator API | Implemented; request/marker behavior tested | Real translation accuracy pending |
| AI Search API and seeding | Implemented; request/filter behavior tested | Actual index provisioning pending |
| ACS email/SMS | Implemented; SDK-call contract tested | Actual permissions/sender setup/delivery pending |
| Delivery consent/allowlist/duplicate guard | Implemented and tested | In-memory only; not a durable production queue |
| Windows build script | Included | Build and packaged-app test on Windows pending |
| Desktop visual/keyboard/audio QA | Pending | Run on the user's graphical desktop |
| Azure deployment | Not executed | Requires user subscription, supported model, roles, and quota |
| Real disaster declaration feed | Not implemented | Add an authoritative incident/jurisdiction integration |
| Live shelter capacity | Not implemented | Needs a current maintained operational source |
| Human escalation | Referral only | No staffed queue, transfer, or case submission |
| Recipient OTP verification | Not implemented | Current real sends restricted to operator-approved testers |
| Production identity/service gateway | Not implemented | Required before public distribution with paid APIs |
| Full-duplex voice and interruption | Later phase | Current design is push-to-talk and confirmed transcripts |
| Web/mobile/telephone access | Later phase | Reuse core services after production security design |

## Next work session

- [ ] Run offline GUI on Windows and record visual/accessibility findings.
- [ ] Create Foundry/Translator/Search/ACS development resources.
- [ ] Sign in with Azure CLI and validate roles.
- [ ] Seed the dedicated public-guidance index after source review.
- [ ] Pass the synthetic Connections test.
- [ ] Test microphone transcript accuracy with at least two speakers.
- [ ] Validate spoken readback and failure behavior.
- [ ] Test Spanish guidance with a fluent reviewer.
- [ ] Verify one email sender and one consenting email tester.
- [ ] Complete SMS sender verification before live SMS testing.
- [ ] Freeze tested dependency versions.
- [ ] Build and test the Windows executable folder.

## Before use with real disaster survivors

- [ ] Current incident/jurisdiction data and maintained operational source policy.
- [ ] Account/session security architecture for users beyond the developer.
- [ ] Recipient verification, suppression/opt-out handling, and abuse limits.
- [ ] Durable delivery state, retry reconciliation, and delivery receipt processing.
- [ ] Retention/deletion review covering Azure services, operating systems, and queues.
- [ ] Broader language, accent, disability, low-connectivity, and device testing.
- [ ] Staffed escalation agreement and clear service hours.
- [ ] Accessibility and security review; emergency guidance reviewed by responsible partners.

## Session log template

```markdown
### Date — Work session
- Goal:
- Change / commit:
- Test evidence:
- Cloud resources changed:
- Estimated/actual cost:
- Privacy implications:
- Blocker:
- Next action / owner:
```

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-23 | Standalone desktop first | User direction; web/mobile planned for later |
| 2026-09-23 | Offline default, live opt-in | Dummy app usable immediately; prevent accidental API calls |
| 2026-09-23 | Operator credentials and tester allowlist | Bound the initial integration test; no public credential distribution |
| 2026-09-23 | Push-to-talk and transcript confirmation | Make recognition errors visible before recommendations |
| 2026-09-23 | Deterministic source-backed summaries | Avoid invented eligibility facts in final action plans |
| 2026-09-23 | No auto-retry after uncertain send | Reduce accidental duplicate messages |
