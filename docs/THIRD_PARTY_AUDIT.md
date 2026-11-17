# DG Radio r50 — third-party resource audit

Status: **partial** — source extracted from supplied r50 IPK; no full runtime test.

| Component | Findings | Status |
| --- | --- | --- |
| Python source | Three .py files present; initial syntax parsing passed | Preliminary |
| Original interface graphics | Author confirms independently created and authorizes GPL-2.0-or-later | Author-attested |
| Bundled font | `DGRadioMonoCondensed.ttf` is **DejaVu Sans Condensed**, identified from embedded name records; Bitstream/Tavmjong Bah/DejaVu notices apply | Third-party license; preserve notices |
| Station logos and fetched artwork | Verify whether any copyrighted logos are bundled or fetched at runtime | Pending |
| JSON station lists | Review data provenance and stream URLs | Pending |
| Secrets and telemetry | Full source audit still required | Pending |
| HD Satelit build | Needs complete committed source tree and updater-disabled package variant | Pending |

The author's GPL grant applies to original DG Radio material, not third-party assets. The font metadata finding supersedes any prior assumption that the renamed font was original.
