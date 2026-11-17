# HD Satelit integration — DG Radio v0.2-r50 RC2

Official public baseline: **v0.2-r50 RC2**. Do not package r63 or experimental builds.

## Source-build prerequisite
The current repository contains a prebuilt IPK but does **not yet contain the complete DGRadio source tree**. This is **not yet source-build ready**. Obtain and review the exact r50 sources (Python, JSON, skins, images and required assets) before producing a feed recipe.

## Package behavior
- Preserve the DG LABS by Dorinelu author attribution and repository URL.
- For HD Satelit feed builds, disable the plugin's own update checker and updater through a packaging-specific configuration or patch, without disabling updates in independent installations.
- Avoid duplicate playback UIs when launching streams already present in the image's radio list.
- Test Now Playing artwork, stream metadata, weather and playback controls on a receiver.
- Ensure that the package does not overwrite personal Enigma2 configuration or station favorites.

## Release gate
Do not distribute a source-built package until the source tree, asset provenance, dependency list and licensing are reviewed and a reproducible build is verified. Pin the feed recipe to a reviewed commit or immutable tag.
