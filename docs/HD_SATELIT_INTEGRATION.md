# HD Satelit integration — DG Radio v0.2-r50 RC2

Official public baseline: **v0.2-r50 RC2**. Do not package r63 or experimental builds.

## Published r50 source
The exact r50 source tree was extracted from the official r50 IPK and committed under `source/DGRadio/` in commit `942364b2cb7de7bfc7452a608687adda99ef612b`. It contains the Python code, JSON lists, images, and bundled font. HD Satelit must still validate its downstream package build on supported hardware.

## Package behavior
- Preserve the DG LABS by Dorinelu author attribution and repository URL.
- For HD Satelit feed builds, disable the plugin's own update checker and updater through a packaging-specific configuration or patch, without disabling updates in independent installations.
- Avoid duplicate playback UIs when launching streams already present in the image's radio list.
- Test Now Playing artwork, stream metadata, weather and playback controls on a receiver.
- Ensure that the package does not overwrite personal Enigma2 configuration or station favorites.

## Release gate
The source tree is published; HD Satelit should still review dependencies, third-party asset notices, and verify its feed package build before distributing. Pin the feed recipe to a reviewed commit or immutable tag.
