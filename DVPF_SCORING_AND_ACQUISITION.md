# D-VPF Scoring and Acquisition Specification

## Transport (cap 25)
- TLS 1.3: 15 points; TLS 1.2: 10.
- Negotiated cipher name contains GCM, CHACHA20, or POLY1305: 5.
- HSTS present: 3; includeSubDomains: +2.
- If strict TLS verification fails, one unverified diagnostic handshake is attempted. TLS 1.2/1.3 in that fallback earns 5 transport points; PKI remains 0.

## DNS/email (cap 25)
- DMARC exists: 5.
- DMARC p=reject: +10; p=quarantine: +7; p=none: +2.
- Apex SPF exists: 5.
- Apex CAA exists: 5.
- NXDOMAIN/NoAnswer yields 0 for that record; transient failures are recorded.

## HTTP (cap 25)
- CSP present: 8; frame-ancestors: +2.
- X-Frame-Options DENY or SAMEORIGIN: 5.
- X-Content-Type-Options nosniff: 5.
- Referrer-Policy containing strict-origin, no-referrer, or same-origin: 5.

## PKI (cap 25)
- Strictly verified chain: 10.
- Certificate unexpired: 5.
- Lifetime within issuance-date maximum: 5; longer lifetime: 2.
- Maximum: 398 days before 15 March 2026; 200 days on/after for the study period.
- RSA >=2048 bits or EC >=256 bits: 5.
- Unverified diagnostic TLS fallback earns 0 PKI points.

## Acquisition defaults
- DNS resolvers: 1.1.1.1 and 8.8.8.8.
- DNS timeout/lifetime: 2.0/2.5 s.
- TLS: port 443; 2.5 s probe timeout; 3.0 s process socket default.
- HTTP: unauthenticated HTTPS GET, redirects followed, 2.5 s timeout.
- HTTP certificate verification disabled for header observation after TLS/PKI is measured separately.
- Up to 3 HTTP attempts, 0.25 s pause after failed attempts.
- Concurrency: 25 threads.
- Default maximum total scanner wait: 90 s.
- Fixed Chrome-like desktop User-Agent.

## Timing provenance
Per-request wall-clock timestamps were not persisted. Frozen CSVs, code, and settings define the analyzed state.
