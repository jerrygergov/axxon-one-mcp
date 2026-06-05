# Evidence: phase-13-notifier-reconcile

Docs/corpus-only reconcile (no production code changed). Restamps the notifier RPCs
that the already-shipped `domain_event_subscribe` / `node_event_subscribe` tools
exercise, so the corpus stops underreporting them.

## What was verified live
Via `tools/axxon_mcp_admin.py` (`AxxonApiClient.pull_notifier_events_bounded`), four
bounded subscribe calls ran against the stand (raw/live-verify.txt). Each established a
subscription, held the bounded server-stream open, closed with a clean
`DEADLINE_EXCEEDED` (healthy idle = no events in-window), and ran
`DisconnectEventChannel` cleanly (`disconnect_clean=true`).

## Restamped `pending -> tested-pass` (6 methods)
- DomainNotifier: PullEvents, PullDetailedEvents, DisconnectEventChannel
- NodeNotifier:   PullEvents, PullDetailedEvents, DisconnectEventChannel

## Left pending (not exercised by the shipped tools)
- DomainNotifier/NodeNotifier: UpdateSubscription, PushDiagnosticEvents
- NodeNotifier: Ping

## Consistency note
The "idle stream + clean disconnect = PASS-class" bar is the project's own existing
standard for these tools (STATUS.md records the same idle-stream result as healthy).
This reconcile only makes the corpus reflect that standard. DomainNotifier 0/5 -> 3/5,
NodeNotifier 0/6 -> 3/6. Coverage 172 -> 178 tested-pass. Suite: 705/705.
