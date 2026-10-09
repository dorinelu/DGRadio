# DG Radio — Update security policy

## Public release procedure
1. Build a release from a reviewed source version.
2. Test the IPK on supported Enigma2 images.
3. Publish the **exact final IPK** as a versioned GitHub Release asset, then verify its availability.
4. Compute SHA-256 from that exact asset; record its exact URL, size and hash in `updates/stable.json`.
5. Only after verification, advertise the new version in the public manifest.
6. Keep internal development builds off `updates/stable.json`. Use a separate private or explicitly enabled test channel.
7. If an update breaks, roll back the public manifest to the last known-good released version; do not silently downgrade installed receivers.

## Update client requirements
- Only accept HTTPS update manifests and downloads from trusted origins.
- Validate manifest schema, version, package size, hash, expected file name and allowed download host.
- Hash the **complete downloaded IPK** before running any package manager command.
- Never build a shell command by concatenating untrusted manifest values; use argument lists.
- Require explicit confirmation before installation and GUI restart.
- Reject unsupported archives, redirects to untrusted origins, manifest downgrades and malformed versions.
- Run download and update checks without blocking the GUI; handle network errors and timeouts.
- Avoid reporting a successful installation before the package manager confirms success.

**Note:** SHA-256 checks accidental corruption, but a hash in a mutable manifest alone does not authenticate the publisher against a compromised repository. Future hardening should use a separately trusted signed manifest and verification key, with key rotation and rollback protections.

## Analytics isolation
Any optional statistics service must be separate from update distribution. Failure or rejection of analytics must never affect update checks or playback.
