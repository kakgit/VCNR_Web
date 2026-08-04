# Future Cleanup Notes

Use this file to track items we intentionally keep active for now and revisit during final cleanup.

## Deferred Items

### M-P2P prototype cleanup and next-phase hardening

Status: Active follow-up after first working milestone on July 23, 2026.

Reason:
- The first working same-user M-P2P transfer milestone has now been reached.
- The prototype is useful and validated, but it still needs hardening before broader rollout.
- Resume, cleanup, and cross-user entitlement rules still need more work.

Current instruction:
- Keep the current working same-user encrypted transfer path.
- Improve resume and interruption recovery.
- Improve cleanup and completion behavior.
- Add cross-user entitlement-controlled transfer later.
- Evaluate direct LAN or `libp2p` transport after the relay-backed prototype is stable.

Reference:
- [m-p2p-design-note.md](D:/Python/VCNR_Web/docs/m-p2p-design-note.md)
- [m-p2p-phase-1-build-plan.md](D:/Python/VCNR_Web/docs/m-p2p-phase-1-build-plan.md)
- [m-p2p-working-milestone-2026-07-23.md](D:/Python/VCNR_Web/docs/m-p2p-working-milestone-2026-07-23.md)

### Admin frontend cleanup after viewer-first work

Status: Defer until after viewer page work.

Reason:
- We prioritized getting the admin delete flow working before doing a broader frontend cleanup pass.
- The current `app.js` still mixes viewer, admin, creator, and VCNR logic in one large file.
- Recent fixes removed the most problematic duplicate handlers, but the file still needs a structured cleanup pass later.

Final cleanup decision to revisit:
- Split large frontend logic into smaller modules where practical
- Remove remaining legacy event wiring and duplicate state paths
- Review admin panel defaults, panel switching, and modal wiring for simplification
- Re-check page caching/versioning assumptions after the frontend is stable

Current instruction:
- Do not spend time on broad frontend cleanup until the next viewer-page milestone is complete.
- Treat this as an active deferred cleanup item for the final cleanup phase.

### Embedded vs external subtitle/audio support

Status: Keep active for now.

Reason:
- Modern movie files often include embedded subtitle and audio tracks.
- We may still need separate subtitle/audio support later depending on source files, dubbing flow, subtitle fixes, or player behavior.

Final cleanup decision to revisit:
- If the final delivery format consistently uses embedded tracks, we can consider removing or simplifying:
  - language taxonomy cleanup remnants
  - separate subtitle/audio management paths
  - language-linked media support that is no longer needed

Current instruction:
- Do not remove subtitle/audio support related structures yet.
- Treat this as an active deferred cleanup item for the final cleanup phase.
