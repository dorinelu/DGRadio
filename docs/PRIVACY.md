# DG Radio — Privacy and optional usage statistics

## Current public version: v0.2-r50 RC2
DG Radio contacts GitHub to check for software updates if the user has enabled automatic update checking, or when the user explicitly checks manually. It downloads IPK packages only with confirmation. HTTPS service operators may process standard request metadata such as an IP address as part of delivering the service.

**DG Radio currently does not implement an installation telemetry service or a unique-installation counter.** Do not represent repository traffic or IPK downloads as unique users.

## Rules for future optional statistics
- **Opt-in only**: disabled by default and enabled only after a clear explanation and affirmative user choice.
- Update checks and update installation **must function when analytics are disabled**.
- Collect only data needed for aggregate statistics: app version, optional Enigma2 image family and a randomly generated installation identifier if truly needed.
- Never read or transmit MAC addresses, serial numbers, device identifiers, user names, channel lists, location, IP addresses as analytics fields, or listening history.
- Do not create a fingerprint from device model, software versions or network information.
- Provide an easy Settings switch to stop participation and a way to delete any stored local analytics identifier.
- Describe retention, processor, hosting, deletion and access controls before enabling collection.
- Server-side request logs need short retention and IP minimization; never publish raw identifiers.
- Do not report active installations until the method is operational and validated.

## Release download statistics
GitHub Release asset download counts measure downloads of the hosted asset, not unique installations. Shared/offline IPKs are not included.

Questions and changes can be raised through the repository issue tracker.
