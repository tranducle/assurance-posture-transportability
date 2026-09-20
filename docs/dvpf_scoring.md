# D-VPF scoring and acquisition

## Transport (25-point cap)

- TLS 1.3: 15 points; TLS 1.2: 10 points.
- Negotiated cipher name contains GCM, CHACHA20, or POLY1305: 5 points.
- HSTS present: 3 points; `includeSubDomains`: 2 additional points.
- If strict TLS verification fails, one unverified diagnostic handshake is attempted. TLS 1.2 or 1.3 in that fallback receives 5 transport points. PKI remains 0.

## DNS and email (25-point cap)

- DMARC exists: 5 points.
- DMARC `p=reject`: 10 additional points; `p=quarantine`: 7; `p=none`: 2.
- Apex SPF exists: 5 points.
- Apex CAA exists: 5 points.
- NXDOMAIN or NoAnswer receives 0 for that record. Transient failures are recorded.

## HTTP headers (25-point cap)

- CSP present: 8 points; `frame-ancestors`: 2 additional points.
- X-Frame-Options set to DENY or SAMEORIGIN: 5 points.
- X-Content-Type-Options set to nosniff: 5 points.
- Referrer-Policy containing strict-origin, no-referrer, or same-origin: 5 points.

## PKI (25-point cap)

- Strictly verified chain: 10 points.
- Certificate unexpired: 5 points.
- Certificate lifetime within the issuance-date maximum: 5 points; longer lifetime: 2 points.
- Study-period maximum lifetime: 398 days before 15 March 2026 and 200 days on or after that date.
- RSA key at least 2048 bits or EC key at least 256 bits: 5 points.
- An unverified diagnostic TLS fallback receives 0 PKI points.

## Acquisition settings

- DNS resolvers: 1.1.1.1 and 8.8.8.8.
- DNS timeout and lifetime: 2.0 s and 2.5 s.
- TLS port: 443.
- TLS probe timeout: 2.5 s; process socket default: 3.0 s.
- HTTP request: unauthenticated HTTPS GET with redirects enabled and a 2.5 s timeout.
- HTTP certificate verification is disabled only for header observation after TLS and PKI are measured separately.
- HTTP attempts: up to 3, with a 0.25 s pause after a failed attempt.
- Concurrency: 25 threads.
- Default maximum scanner wait: 90 s.
- User-Agent: fixed Chrome-like desktop string.

## Timing note

Per-request wall-clock timestamps were not stored. Exact reproduction therefore uses the frozen measurements rather than a later live reacquisition.
