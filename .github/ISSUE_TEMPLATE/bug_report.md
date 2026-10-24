---
name: Bug report
about: Report a reproducible problem without publishing resident data.
---

This issue is public. Follow [CONTRIBUTING.md](https://github.com/dirrgang/home-assistant-facilioo/blob/master/CONTRIBUTING.md):
never include credentials, tokens, names, addresses, account data, real meter IDs,
unredacted diagnostics, or complete real API responses.
For suspected vulnerabilities, use the private reporting instructions in
[SECURITY.md](https://github.com/dirrgang/home-assistant-facilioo/blob/master/SECURITY.md);
do not describe vulnerability details here.

Search existing issues before submitting. Replace the prompts below; omit optional
sections if they do not apply.

### Environment

- Home Assistant version:
- Facilioo integration version:
- Installation method: HACS or manual (no local filesystem paths needed)

### Observed and expected behavior

What happens, and what should happen instead? Facilioo readings are monthly,
not live telemetry. Other white-label portals are not verified; MFA is unsupported.

### Reproduction

1. Describe the smallest steps that reproduce the problem.

Does it happen always, intermittently, or only once? When did it start?

### Error category

If shown, give the category only, for example `invalid_auth`, `mfa_required`,
`not_authorized`, `rate_limited`, `cannot_connect`, `no_consumption_data`, or
`unknown_response`. Otherwise write "none" or "unknown".

### Sanitized logs (optional)

Include only a short relevant excerpt, reviewed and sanitized according to
CONTRIBUTING.md. Omit it if you cannot safely remove sensitive information.
Do not upload full logs, diagnostics, or screenshots containing private data.

### Synthetic schema example (optional, API/white-label variation only)

Provide only the smallest **invented** JSON example that preserves the relevant
field names, types, and nullability. Use invented IDs and values; never paste a
real raw payload. Explain the suspected variation without claiming compatibility.

- [ ] I reviewed the entire report and all attachments for sensitive information.
