# Future Cleanup Notes

Use this file to track items we intentionally keep active for now and revisit during final cleanup.

## Deferred Items

### M-P2P prototype after stable hosted delivery

Status: Defer until after Railway deployment and short-title validation.

Reason:
- We now have a stable direct-download and VCNR direct-playback baseline.
- Mobile-to-mobile peer transfer is valuable, but it should be added only after the hosted server flow is stable.
- This avoids mixing two large delivery-path changes at once.

Current instruction:
- Finish `VCNR_Web`.
- Deploy the hosted flow to Railway.
- Test a few shorter real titles first.
- Then begin the `M-P2P` prototype.

Reference:
- [m-p2p-design-note.md](D:/Python/VCNR_Web/docs/m-p2p-design-note.md)

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
