#!/usr/bin/env python3
"""
Phase 3: Deterministic Technical Hygiene Scanner (D-VPF Probe)
Measures externally observable network and infrastructure configuration across 4 pillars:
1. Transport Security (negotiated TLS version, AEAD suite, HSTS/subdomains) [25 pts]
2. DNS & Email Trust (DMARC policy, SPF, CAA records) [25 pts]
3. HTTP Defensive Surface (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy) [25 pts]
4. PKI & Certificate Hygiene (valid trust chain, issuance-date-aware lifespan,
   RSA >= 2048 / EC >= 256 bits) [25 pts]

Outputs:
- vendor_technical_hygiene.csv
- final_empirical_dataset.csv (IV: Compliance Claims + DV: Technical Posture Score)

Part of the study data-acquisition and empirical-evaluation pipeline.
"""

import argparse
import csv
import datetime
import os
import re
import socket
import ssl
import sys
import time
import urllib3
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Dict, List, Optional, Tuple

import dns.resolver
import requests
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa

# Suppress insecure request warnings for passive probing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
socket.setdefaulttimeout(3.0)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

CUSTOM_RESOLVER = dns.resolver.Resolver()
CUSTOM_RESOLVER.timeout = 2.0
CUSTOM_RESOLVER.lifetime = 2.5
CUSTOM_RESOLVER.nameservers = ["1.1.1.1", "8.8.8.8"]


def probe_tls_and_pki(domain: str, timeout: float = 2.5) -> Tuple[int, int, Dict[str, str]]:
    """
    Pillar 1: Transport Security (0 - 25)
    Pillar 4: PKI & Certificate Hygiene (0 - 25)
    """
    tls_score = 0
    pki_score = 0
    details = {
        "tls_version": "None",
        "cipher_suite": "None",
        "cert_valid": "False",
        "cert_days_left": "0",
        "cert_lifespan_days": "0",
        "cert_max_allowed_days": "0",
        "key_type": "Unknown",
        "key_bits": "0",
        "tls_validation_status": "failed",
    }

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        with socket.create_connection((domain, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                version = ssock.version()
                cipher = ssock.cipher()
                cert = ssock.getpeercert()
                cert_der = ssock.getpeercert(binary_form=True)

                details["tls_version"] = str(version)
                if cipher:
                    details["cipher_suite"] = str(cipher[0])

                # Pillar 1 Scoring:
                if version == "TLSv1.3":
                    tls_score += 15
                elif version == "TLSv1.2":
                    tls_score += 10

                # Check modern AEAD cipher
                if cipher and any(aead in cipher[0] for aead in ["GCM", "CHACHA20", "POLY1305"]):
                    tls_score += 5

                # Pillar 4: PKI Scoring
                if cert:
                    details["cert_valid"] = "True"
                    details["tls_validation_status"] = "verified"
                    pki_score += 10

                    # Parse dates
                    not_before_str = cert.get("notBefore")
                    not_after_str = cert.get("notAfter")
                    if not_before_str and not_after_str:
                        fmt = "%b %d %H:%M:%S %Y %Z"
                        nb = datetime.datetime.strptime(not_before_str, fmt)
                        na = datetime.datetime.strptime(not_after_str, fmt)
                        now = datetime.datetime.utcnow()

                        days_left = (na - now).days
                        lifespan = (na - nb).days
                        details["cert_days_left"] = str(days_left)
                        details["cert_lifespan_days"] = str(lifespan)

                        if days_left > 0:
                            pki_score += 5

                        # CA/Browser Forum phased maximum TLS certificate lifetime:
                        # 398 days before 15 Mar 2026; 200 days on/after that date.
                        max_allowed = 200 if nb >= datetime.datetime(2026, 3, 15) else 398
                        details["cert_max_allowed_days"] = str(max_allowed)
                        if lifespan <= max_allowed:
                            pki_score += 5
                        else:
                            pki_score += 2

                    # Public-key strength check from the leaf certificate.
                    if cert_der:
                        parsed = x509.load_der_x509_certificate(cert_der)
                        public_key = parsed.public_key()
                        if isinstance(public_key, rsa.RSAPublicKey):
                            bits = public_key.key_size
                            details["key_type"] = "RSA"
                            details["key_bits"] = str(bits)
                            if bits >= 2048:
                                pki_score += 5
                        elif isinstance(public_key, ec.EllipticCurvePublicKey):
                            bits = public_key.key_size
                            details["key_type"] = f"EC-{public_key.curve.name}"
                            details["key_bits"] = str(bits)
                            if bits >= 256:
                                pki_score += 5

    except Exception:
        # If strict TLS fails, try with non-strict to diagnose
        try:
            unverified_ctx = ssl._create_unverified_context()
            with socket.create_connection((domain, 443), timeout=timeout) as sock:
                with unverified_ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    version = ssock.version()
                    details["tls_version"] = str(version)
                    details["tls_validation_status"] = "unverified"
                    if version in ["TLSv1.2", "TLSv1.3"]:
                        tls_score = 5
        except Exception:
            pass

    return min(20, tls_score), min(25, pki_score), details


def probe_http_headers_and_hsts(domain: str, timeout: float = 2.5) -> Tuple[int, int, Dict[str, str]]:
    """
    Extracts HSTS (+5 pts to Pillar 1)
    Pillar 3: HTTP Defensive Headers (0 - 25)
    """
    hsts_bonus = 0
    http_score = 0
    details = {
        "hsts": "None",
        "csp": "None",
        "x_frame_options": "None",
        "x_content_type_options": "None",
        "referrer_policy": "None",
        "http_probe_status": "failed",
    }

    url = f"https://{domain}"
    resp = None
    for attempt in range(3):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                verify=False,
                allow_redirects=True,
            )
            break
        except Exception:
            if attempt < 2:
                time.sleep(0.25)

    if resp is not None:
        try:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            details["http_probe_status"] = "observed"

            # HSTS check
            hsts_header = headers.get("strict-transport-security")
            if hsts_header:
                details["hsts"] = hsts_header
                hsts_bonus += 3
                if "includesubdomains" in hsts_header.lower():
                    hsts_bonus += 2

            # Content Security Policy (CSP)
            csp_header = headers.get("content-security-policy")
            if csp_header:
                details["csp"] = "Present"
                http_score += 8
                if "frame-ancestors" in csp_header.lower():
                    http_score += 2

            # X-Frame-Options
            xfo = headers.get("x-frame-options")
            if xfo:
                details["x_frame_options"] = xfo
                if xfo.upper() in ["DENY", "SAMEORIGIN"]:
                    http_score += 5

            # X-Content-Type-Options
            xcto = headers.get("x-content-type-options")
            if xcto:
                details["x_content_type_options"] = xcto
                if "nosniff" in xcto.lower():
                    http_score += 5

            # Referrer-Policy
            ref = headers.get("referrer-policy")
            if ref:
                details["referrer_policy"] = ref
                if any(r in ref.lower() for r in ["strict-origin", "no-referrer", "same-origin"]):
                    http_score += 5
        except Exception:
            details["http_probe_status"] = "failed"

    return min(5, hsts_bonus), min(25, http_score), details


def probe_dns_email_trust(domain: str) -> Tuple[int, Dict[str, str]]:
    """
    Pillar 2: DNS & Email Trust (0 - 25)
    Checks DMARC, SPF, and CAA records.
    """
    dns_score = 0
    details = {
        "dmarc_policy": "None",
        "has_spf": "False",
        "has_caa": "False",
        "dns_probe_status": "observed",
    }
    transient_failures = []

    # 1. DMARC check at _dmarc.{domain}
    try:
        dmarc_target = f"_dmarc.{domain}"
        answers = CUSTOM_RESOLVER.resolve(dmarc_target, "TXT")
        for rdata in answers:
            txt_str = "".join([b.decode("utf-8", errors="ignore") for b in rdata.strings])
            if "v=DMARC1" in txt_str.upper():
                dns_score += 5
                # Extract policy
                p_match = re.search(r"\bp=([a-zA-Z]+)", txt_str, re.IGNORECASE)
                if p_match:
                    policy = p_match.group(1).lower()
                    details["dmarc_policy"] = policy
                    if policy == "reject":
                        dns_score += 10
                    elif policy == "quarantine":
                        dns_score += 7
                    elif policy == "none":
                        dns_score += 2
                break
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass
    except Exception as exc:
        transient_failures.append(f"DMARC:{type(exc).__name__}")

    # 2. SPF check on root domain
    try:
        answers = CUSTOM_RESOLVER.resolve(domain, "TXT")
        for rdata in answers:
            txt_str = "".join([b.decode("utf-8", errors="ignore") for b in rdata.strings])
            if "v=spf1" in txt_str.lower():
                details["has_spf"] = "True"
                dns_score += 5
                break
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass
    except Exception as exc:
        transient_failures.append(f"SPF:{type(exc).__name__}")

    # 3. CAA check on root domain
    try:
        answers = CUSTOM_RESOLVER.resolve(domain, "CAA")
        if len(answers) > 0:
            details["has_caa"] = "True"
            dns_score += 5
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass
    except Exception as exc:
        transient_failures.append(f"CAA:{type(exc).__name__}")

    if transient_failures:
        details["dns_probe_status"] = "partial_failure:" + ",".join(transient_failures)

    return min(25, dns_score), details


def audit_vendor_hygiene(row: Dict[str, str], timeout: float = 2.5) -> Dict[str, str]:
    domain = row.get("domain", "").strip()
    rank = row.get("rank", "")
    title = row.get("title", "")

    # Run probes
    tls_pts, pki_pts, tls_details = probe_tls_and_pki(domain, timeout=timeout)
    hsts_bonus, http_pts, http_details = probe_http_headers_and_hsts(domain, timeout=timeout)
    dns_pts, dns_details = probe_dns_email_trust(domain)

    pillar1_tls = min(25, tls_pts + hsts_bonus)
    pillar2_dns = dns_pts
    pillar3_http = http_pts
    pillar4_pki = pki_pts

    total_d_vpf = pillar1_tls + pillar2_dns + pillar3_http + pillar4_pki

    result = {
        "rank": rank,
        "domain": domain,
        "title": title[:60],
        "score_tls_transport": str(pillar1_tls),
        "score_dns_email": str(pillar2_dns),
        "score_http_headers": str(pillar3_http),
        "score_pki_cert": str(pillar4_pki),
        "d_vpf_technical_score": str(total_d_vpf),
        "tls_version": tls_details["tls_version"],
        "tls_validation_status": tls_details["tls_validation_status"],
        "cert_lifespan_days": tls_details["cert_lifespan_days"],
        "cert_max_allowed_days": tls_details["cert_max_allowed_days"],
        "key_type": tls_details["key_type"],
        "key_bits": tls_details["key_bits"],
        "dmarc_policy": dns_details["dmarc_policy"],
        "has_spf": dns_details["has_spf"],
        "has_caa": dns_details["has_caa"],
        "hsts_present": "True" if http_details["hsts"] != "None" else "False",
        "csp_present": "True" if http_details["csp"] != "None" else "False",
        "http_probe_status": http_details["http_probe_status"],
        "dns_probe_status": dns_details["dns_probe_status"],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Deterministic Technical Security Hygiene Scanner (D-VPF)")
    parser.add_argument(
        "--compliance-input",
        default="5_Experiments_Simulations/data/vendor_compliance_baseline.csv",
        help="Input CSV containing vendor compliance claims",
    )
    parser.add_argument(
        "--output-hygiene",
        default="5_Experiments_Simulations/data/vendor_technical_hygiene.csv",
        help="Output CSV for technical posture scores",
    )
    parser.add_argument(
        "--output-merged",
        default="5_Experiments_Simulations/data/final_empirical_dataset.csv",
        help="Output CSV merging IV claims and DV technical scores",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=25,
        help="Concurrent threads (default: 25)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Probe timeout in seconds (default: 2.5)",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=90.0,
        help="Max total execution seconds (default: 90.0)",
    )
    args = parser.parse_args()

    print(f"[*] Reading compliance baseline vendors: {args.compliance_input}")
    compliance_rows = []
    with open(args.compliance_input, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            compliance_rows.append(r)

    total = len(compliance_rows)
    print(f"[*] Starting D-VPF passive technical probe for {total} vendors with {args.concurrency} threads...")

    executor = ThreadPoolExecutor(max_workers=args.concurrency)
    future_to_vendor = {
        executor.submit(audit_vendor_hygiene, v, args.timeout): v
        for v in compliance_rows
    }

    wait_timeout = None if args.max_wait <= 0 else args.max_wait
    done, not_done = wait(future_to_vendor.keys(), timeout=wait_timeout)
    print(f"[*] Completed {len(done)}/{total} vendors (Timed out: {len(not_done)}). Shutting down...")
    executor.shutdown(wait=False, cancel_futures=True)

    hygiene_results = []
    for future in done:
        try:
            res = future.result()
        except Exception as exc:
            v_info = future_to_vendor[future]
            res = {
                "rank": v_info.get("rank", ""),
                "domain": v_info.get("domain", ""),
                "title": v_info.get("title", ""),
                "score_tls_transport": "0",
                "score_dns_email": "0",
                "score_http_headers": "0",
                "score_pki_cert": "0",
                "d_vpf_technical_score": "0",
                "tls_version": "error",
                "tls_validation_status": "error",
                "cert_lifespan_days": "",
                "cert_max_allowed_days": "",
                "key_type": "",
                "key_bits": "",
                "dmarc_policy": "None",
                "has_spf": "False",
                "has_caa": "False",
                "hsts_present": "False",
                "csp_present": "False",
                "http_probe_status": "error",
                "dns_probe_status": "error",
            }
        hygiene_results.append(res)

    for future in not_done:
        v_info = future_to_vendor[future]
        hygiene_results.append({
            "rank": v_info.get("rank", ""),
            "domain": v_info.get("domain", ""),
            "title": v_info.get("title", ""),
            "score_tls_transport": "0",
            "score_dns_email": "0",
            "score_http_headers": "0",
            "score_pki_cert": "0",
            "d_vpf_technical_score": "0",
            "tls_version": "timed_out",
            "tls_validation_status": "timed_out",
            "cert_lifespan_days": "",
            "cert_max_allowed_days": "",
            "key_type": "",
            "key_bits": "",
            "dmarc_policy": "None",
            "has_spf": "False",
            "has_caa": "False",
            "hsts_present": "False",
            "csp_present": "False",
            "http_probe_status": "timed_out",
            "dns_probe_status": "timed_out",
        })

    hygiene_results.sort(key=lambda x: int(x["rank"]) if x["rank"].isdigit() else 999999)

    # Write vendor_technical_hygiene.csv
    hygiene_fieldnames = [
        "rank",
        "domain",
        "title",
        "score_tls_transport",
        "score_dns_email",
        "score_http_headers",
        "score_pki_cert",
        "d_vpf_technical_score",
        "tls_version",
        "tls_validation_status",
        "cert_lifespan_days",
        "cert_max_allowed_days",
        "key_type",
        "key_bits",
        "dmarc_policy",
        "has_spf",
        "has_caa",
        "hsts_present",
        "csp_present",
        "http_probe_status",
        "dns_probe_status",
    ]
    with open(args.output_hygiene, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=hygiene_fieldnames)
        writer.writeheader()
        writer.writerows(hygiene_results)
    print(f"[+] Technical hygiene results saved to: {args.output_hygiene}")

    # Merge compliance IV and technical hygiene DV
    hygiene_by_domain = {r["domain"]: r for r in hygiene_results}
    merged_results = []
    for c in compliance_rows:
        dom = c["domain"]
        h = hygiene_by_domain.get(dom, {})
        merged = {**c, **{
            "score_tls_transport": h.get("score_tls_transport", "0"),
            "score_dns_email": h.get("score_dns_email", "0"),
            "score_http_headers": h.get("score_http_headers", "0"),
            "score_pki_cert": h.get("score_pki_cert", "0"),
            "d_vpf_technical_score": h.get("d_vpf_technical_score", "0"),
            "dmarc_policy": h.get("dmarc_policy", "None"),
            "hsts_present": h.get("hsts_present", "False"),
            "csp_present": h.get("csp_present", "False"),
            "tls_validation_status": h.get("tls_validation_status", "failed"),
            "cert_lifespan_days": h.get("cert_lifespan_days", ""),
            "cert_max_allowed_days": h.get("cert_max_allowed_days", ""),
            "key_type": h.get("key_type", ""),
            "key_bits": h.get("key_bits", ""),
            "http_probe_status": h.get("http_probe_status", "failed"),
            "dns_probe_status": h.get("dns_probe_status", "failed"),
        }}
        merged_results.append(merged)

    merged_fieldnames = list(compliance_rows[0].keys()) + [
        "score_tls_transport",
        "score_dns_email",
        "score_http_headers",
        "score_pki_cert",
        "d_vpf_technical_score",
        "dmarc_policy",
        "hsts_present",
        "csp_present",
        "tls_validation_status",
        "cert_lifespan_days",
        "cert_max_allowed_days",
        "key_type",
        "key_bits",
        "http_probe_status",
        "dns_probe_status",
    ]
    with open(args.output_merged, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=merged_fieldnames)
        writer.writeheader()
        writer.writerows(merged_results)
    print(f"[+] Merged empirical dataset (IV + DV) saved to: {args.output_merged}")

    # Compute descriptive statistics
    claimers_scores = [
        float(r["d_vpf_technical_score"])
        for r in merged_results
        if int(r.get("total_claimed_attestations", 0)) > 0
    ]
    non_claimers_scores = [
        float(r["d_vpf_technical_score"])
        for r in merged_results
        if int(r.get("total_claimed_attestations", 0)) == 0
    ]

    mean_claimers = sum(claimers_scores) / max(1, len(claimers_scores))
    mean_non_claimers = sum(non_claimers_scores) / max(1, len(non_claimers_scores))

    print("\n============================================================")
    print(f"      D-VPF EMPIRICAL MEASUREMENT FINDINGS (N={total})          ")
    print("============================================================")
    print(f"Claiming Vendors (N={len(claimers_scores)}) Mean D-VPF Score:     {mean_claimers:.2f} / 100")
    print(f"Non-Claiming Vendors (N={len(non_claimers_scores)}) Mean D-VPF Score: {mean_non_claimers:.2f} / 100")
    print(f"Empirical Posture Gap:                       {mean_claimers - mean_non_claimers:+.2f} points")
    print("============================================================")

    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
