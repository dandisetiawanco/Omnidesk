# Release Signing, Packaging & Notarization Guide

OmniDesk ships packaging configuration in `apps/desktop/src-tauri/tauri.conf.json` for:

- **macOS**: `.app` bundle and `.dmg` disk image
- **Windows**: `.msi` and NSIS `.exe` installers
- **Linux**: `.deb`, `.rpm`, and `.AppImage` bundles

This repository intentionally contains **zero certificates, private keys, or credentials**. Maintainers provide signing secrets only in protected release CI environments.

## macOS Code Signing & Notarization

Required GitHub Actions Secrets (release tags only):

- `APPLE_CERTIFICATE`: Base64-encoded Developer ID Application `.p12` certificate
- `APPLE_CERTIFICATE_PASSWORD`: Password for the `.p12` file
- `APPLE_SIGNING_IDENTITY`: Full identity string (e.g. `Developer ID Application: ...`)
- `APPLE_ID`: Apple Developer account email
- `APPLE_PASSWORD`: App-specific password for `notarytool`
- `APPLE_TEAM_ID`: 10-character Apple Developer Team ID

Hardened Runtime entitlements live in `apps/desktop/src-tauri/entitlements.plist`. OmniDesk does not disable library validation or enable JIT exceptions.

## Windows Authenticode Signing

Required Secrets:

- `WINDOWS_CERTIFICATE`: Base64-encoded EV or Organization Code Signing certificate (or Azure Trusted Signing / SignPath token)
- `WINDOWS_CERTIFICATE_PASSWORD`: Certificate password
- Timestamp server: RFC 3161 SHA-256 server configured via `tauri.conf.json` (`digestAlgorithm: "sha256"`)

## Linux Packaging & Verification

- Publish SHA-256 checksum manifests (`SHA256SUMS.txt`) alongside `.deb`, `.rpm`, and `.AppImage` artifacts.
- Optionally sign checksums with a maintainer GPG key (`LINUX_GPG_PRIVATE_KEY`) in release workflows.
