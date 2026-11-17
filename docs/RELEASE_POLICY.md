# DG Radio release policy

- Public integration baseline: **v0.2-r50 RC2**.
- Other package versions were removed from the default branch. A historical snapshot remains at `archive/pre-r50-cleanup-2026-11`; Git history is public.
- The independent r50 update mechanism remains documented in the README. Image-integrated builds may disable it at packaging time.
- Do not mark this repository as source-build ready until the complete r50 source tree is published and audited.
- Do not create an official source tag before the reviewed source tree is present.
