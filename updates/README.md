# Update channel

This directory will contain the public update manifest `stable.json` once the first verified GitHub Release IPK asset has been published.

The manifest must include an exact version, release notes, a HTTPS download URL to an existing official release asset, and the SHA-256 digest of that exact IPK.

Do not place internal testing builds on the public update channel. The plugin must not prompt an update until a valid manifest exists.
