# Hack Day submission summary

**Project:** CanopyOS

**Category:** Best Open-Source AI Project

**Public repository:** https://github.com/joeylukoji/CanopyOS

**Product screenshots:** [Desktop and mobile gallery](demo-gallery.md)

**Repeatable demo photos:** [Lubumbashi museum](demo-photos/lubumbashi-museum.jpg)
and [Cupertino park](demo-photos/cupertino-park.jpg), with licenses and credits in
the gallery.

**Short description:** CanopyOS turns an outdoor photograph into an exploratory
urban-greening field note. An open-weight SegFormer model segments vegetation,
paving, buildings and open ground; the app reports pixel-based indicators and a
cautious intervention to investigate on site.

**Technologies:** Python, FastAPI, SegFormer B0 (ADE20K), PyTorch, HTMX,
Tailwind CSS, SQLite and Docker. The Jev decision service and Gemma explanation
are optional; the default demo labels its deterministic rule and template
fallbacks explicitly.

**What to show:** Capture or upload a permitted outdoor photograph, wait for the
real segmentation overlay, explain the classified-pixel denominator and Green
Score, then show the intervention's provenance, private history and deletion.
The first scan may download and load model weights; warm the model before the live
presentation. The homepage illustration is concept art, not model output.

**Demo URL:** Add a public HTTPS address only after deployment and a real scan
have been checked on that host. A localhost address is not a public demo.

**Evidence and limits:** The [validation record](validation.md) distinguishes
software checks from field acceptance. The score is exploratory and does not
measure actual land area, temperature, emissions or intervention feasibility.
Live Jev/Gemma calls and a physical phone field trial have not yet been verified.
