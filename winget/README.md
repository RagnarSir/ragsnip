# RagSnip — winget submission

These manifests are the source of truth for the `RagnarSir.RagSnip`
package on the [Windows Package Manager Community Repository](https://github.com/microsoft/winget-pkgs).
End-users will be able to install RagSnip with:

```powershell
winget install RagnarSir.RagSnip
```

…once these manifests are merged.

## When to update

Every time you cut a new release (`v1.0.1`, `v1.0.2`, …):

1. Bump `PackageVersion` in all three YAMLs to the new version.
2. Update `InstallerUrl` in `*.installer.yaml` to the new release tag.
3. Update `InstallerSha256` (instructions below).
4. Update `ReleaseDate` to today's date.
5. Submit a fresh PR to `microsoft/winget-pkgs`.

## Filling in the SHA256

After CI publishes `RagSnip-Setup-<version>.exe` to the GitHub Releases
page, compute its SHA256:

```bash
# from the repo root, using gh + sha256sum (Linux/macOS):
gh release download v1.0.1 -p "RagSnip-Setup-*.exe" -O /tmp/RagSnip-Setup.exe
sha256sum /tmp/RagSnip-Setup.exe
```

```powershell
# Windows equivalent:
Invoke-WebRequest https://github.com/RagnarSir/ragsnip/releases/download/v1.0.1/RagSnip-Setup-1.0.1.exe -OutFile RagSnip-Setup.exe
certutil -hashfile RagSnip-Setup.exe SHA256
```

Paste the lower-case hex digest into the `InstallerSha256` field.

## Submitting the PR

The official tool `wingetcreate` automates almost all of this — including
the SHA256 step:

```powershell
winget install Microsoft.WingetCreate
wingetcreate update RagnarSir.RagSnip `
    --version 1.0.1 `
    --urls https://github.com/RagnarSir/ragsnip/releases/download/v1.0.1/RagSnip-Setup-1.0.1.exe `
    --submit
```

That single command:
1. Downloads the new installer
2. Computes its SHA256
3. Updates the manifests in your fork of `microsoft/winget-pkgs`
4. Opens a PR for you

If you'd rather do it manually:

1. Fork [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs).
2. In your fork, copy these three YAMLs into `manifests/r/RagnarSir/RagSnip/<version>/`.
3. Validate locally on a Windows machine: `winget validate --manifest manifests\r\RagnarSir\RagSnip\1.0.1`
4. Test install (sandbox recommended): `winget install --manifest manifests\r\RagnarSir\RagSnip\1.0.1`
5. Open a PR back to `microsoft/winget-pkgs`. The bot runs CI checks; expect human review within a few days for new packages, hours for updates.

## License caveat

`License` in `RagnarSir.RagSnip.locale.en-US.yaml` is currently
`NoAssertion`. Adding a real `LICENSE` file to the repo (`MIT` is a
reasonable default for a small open-source tool) and updating the
manifest to the matching SPDX identifier will smooth review.
