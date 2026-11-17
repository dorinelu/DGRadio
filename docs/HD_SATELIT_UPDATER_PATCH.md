# HD Satelit r50 updater patch

Apply this to the extracted **r50** `DGRadio/plugin.py` source before building the HD Satelit feed package. The standalone release must remain unchanged.

The existing r50 updater uses `DGUpdateMixin`, initializes on both the main screen and settings, checks a signed public manifest and can invoke `opkg install` after user approval. A feed-managed package should not run this separate update path.

## Minimal patch requirements

1. Add `HD_SATELIT_FEED_BUILD = True` near `PLUGIN_RELEASE = "r50"` **only in the HD Satelit build**.
2. In `DGUpdateMixin._initUpdater`, return immediately when the feed flag is true, after initializing any fields required by `_closeUpdater`. Do not append update timers or layout callbacks.
3. In `DGUpdateMixin._runUpdateCheck`, return immediately for the feed build, so manual invocation cannot start an update.
4. In `DGSettings.__init__`, omit the `Check for public updates on startup` configuration entry and hide the yellow-key `Check for Updates` label for feed builds. The yellow action may remain mapped if the method safely returns.
5. In `DGSettings.checkForUpdates`, return immediately for feed builds.
6. Verify closing both screens, changing settings, opening the main screen and checking the feed updater do not raise errors.

**Do not** globally remove the updater from the standalone r50 source. **Do not** package a modified plugin under the original upstream r50 IPK checksum.

This file is an integration specification, **not a tested patch**. Actual source changes and receiver validation remain necessary.
