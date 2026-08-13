# SnipTag Privacy Policy Design

Date: 2026-08-13  
Status: Approved for implementation

## Goal

Publish a stable, bilingual privacy-policy page that SignPath reviewers and
SnipTag users can verify against the application's actual behavior.

## Verified application behavior

- SnipTag has no runtime analytics, advertising, account system, telemetry, or
  network-request code.
- Screen captures and clipboard images are processed locally and are saved only
  when the user invokes the relevant feature.
- Captured images are written to the directory selected by the user.
- Application preferences are stored locally in
  `%APPDATA%\SnipTag\config.json`.
- Optional Windows startup registration is stored locally under the current
  user's Windows registry settings.

## Document structure

`PRIVACY.md` will place English first for SignPath review, followed by an
equivalent Traditional Chinese version. Each language will cover:

1. Scope and effective date.
2. No collection, analytics, tracking, sale, or sharing of personal data.
3. Local-only handling of screen captures, clipboard content, saved images,
   preferences, and optional startup settings.
4. The required network-transfer statement: the program does not transfer
   information to networked systems unless the user or operator specifically
   requests it.
5. User control and deletion instructions for images, configuration, and the
   optional startup entry.
6. No runtime third-party services, plus a clarification that GitHub downloads
   and external links are governed by those sites' own policies.
7. A contact route through the repository's GitHub Issues page and a brief
   policy-change notice.

The README will link to `PRIVACY.md` so the public URL is easy to provide in the
SignPath Foundation application.

## Accuracy constraints

- Do not claim legal certifications or regulatory compliance that has not been
  independently established.
- Do not imply that GitHub, SignPath, or Windows services are part of the
  SnipTag runtime.
- Keep the English and Traditional Chinese sections materially equivalent.
- If networking, crash reporting, cloud sync, or telemetry is added later, the
  policy must be updated before that feature is released.

## Validation

- Confirm that `PRIVACY.md` contains both language sections and the exact
  network-transfer statement already used in the code-signing policy.
- Confirm that the README link resolves to the repository privacy file.
- Re-run a source search for network and telemetry libraries before publishing.
- Run `git diff --check` and verify that no application code changed.

