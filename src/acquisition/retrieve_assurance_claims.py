#!/usr/bin/env python3
"""Retrieve first-party public security-assurance claims.

The crawler checks dedicated trust, compliance, and security locations and
extracts visible assurance evidence from page text and image metadata. The
study construct covers ISO/IEC 27001, SOC 2, and CSA STAR. Mentions of GDPR,
HIPAA, FedRAMP, or PCI DSS are not counted as assurance claims because a page
mention alone does not establish the study's target evidence.
"""

import argparse
import csv
import os
import re
import socket
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Global socket timeout
socket.setdefaulttimeout(3.5)

# Suppress warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Exact target strings for the primary attestation construct.
PATTERNS = {
    "iso_27001": re.compile(r"\b(?:ISO(?:\/IEC)?\s?27001(?::2013|:2022)?)\b", re.IGNORECASE),
    "soc_2": re.compile(r"\bSOC\s*2(?:\s+Type\s+(?:I|II|1|2))?\b", re.IGNORECASE),
    "csa_star": re.compile(r"\b(?:CSA\s?STAR|Cloud\s+Security\s+Alliance\s+STAR)\b", re.IGNORECASE),
}

ATTESTATION_CONTEXT = {
    "iso_27001": re.compile(
        r"certif|certificate|attest|audit|accredit|achiev|maintain|compliance|compliant|trust",
        re.IGNORECASE,
    ),
    "soc_2": re.compile(
        r"type\s*(?:i|ii|1|2)|report|attest|audit|certif|compliant|compliance|trust",
        re.IGNORECASE,
    ),
    "csa_star": re.compile(
        r"level\s*[123]|registry|registr|attest|certif|compliance|trust",
        re.IGNORECASE,
    ),
}

# Phrases that usually describe a capability/product use case rather than the
# vendor's own attestation. These are conservative exclusions.
THIRD_PARTY_CONTEXT = re.compile(
    r"(?:support|supports|supporting|help|helps|helping).{0,80}"
    r"(?:iso(?:\/iec)?\s*27001|soc\s*2|csa\s*star).{0,60}(?:audit|compliance)"
    r"|(?:provider|vendor|customer|client)s?.{0,80}"
    r"(?:iso(?:\/iec)?\s*27001|soc\s*2|csa\s*star).{0,60}(?:certif|compliance)",
    re.IGNORECASE,
)

SECURITY_LINK_PATTERNS = re.compile(
    r"(?:security|trust|compliance|certifications|privacy|assurance|audit|cert)",
    re.IGNORECASE,
)

STANDARD_SUBDOMAINS = ["trust", "compliance", "security"]
STANDARD_DEEP_PATHS = [
    "/security",
    "/trust",
    "/compliance",
    "/compliance/programs/",
    "/trust-center",
    "/security/compliance",
    "/en/trust/legal-compliance/",
    "/legal/compliance",
]


def fetch_url(url: str, timeout: float = 2.5) -> Optional[Tuple[str, str]]:
    """
    Fetches URL and returns (html_content, final_url) with robust timeout.
    """
    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            verify=False,
            allow_redirects=True,
        )
        if resp.status_code == 200:
            return resp.text, resp.url
    except Exception:
        pass
    return None


def extract_page_text_with_badges(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()

    badge_texts = []
    for img in soup.find_all("img"):
        if img.get("alt"):
            badge_texts.append(img["alt"])
        if img.get("title"):
            badge_texts.append(img["title"])

    for elem in soup.find_all(attrs={"aria-label": True}):
        badge_texts.append(elem["aria-label"])

    body_text = soup.get_text(separator=" ")
    return body_text + " " + " ".join(badge_texts)


def discover_candidate_urls(base_domain: str, homepage_html: Optional[str], homepage_url: str) -> List[str]:
    high_yield_paths = [
        "/security",
        "/trust",
        "/compliance",
        "/compliance/programs/",
        "/trust-center",
        "/security/compliance",
        "/legal/compliance",
        "/features/security",
    ]
    standard_subdomains = ["trust", "security", "compliance"]
    deep_paths = [
        "/en/trust/legal-compliance/",
    ]

    ordered_candidates: List[str] = []
    seen: Set[str] = set()

    def add_url(u: str):
        u_clean = u.rstrip("/")
        if u_clean not in seen and not any(u_clean.lower().endswith(ext) for ext in [".pdf", ".png", ".jpg", ".zip"]):
            seen.add(u_clean)
            ordered_candidates.append(u)

    # 1. High yield root paths on base domain
    for p in high_yield_paths:
        add_url(f"https://{base_domain}{p}")

    # 2. Extract explicitly linked security/trust pages from homepage
    if homepage_html:
        base_netloc = urlparse(homepage_url).netloc.lower()
        soup = BeautifulSoup(homepage_html[:150000], "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            link_text = a.get_text().strip()
            if SECURITY_LINK_PATTERNS.search(href) or SECURITY_LINK_PATTERNS.search(link_text):
                full_url = urljoin(homepage_url, href)
                parsed = urlparse(full_url)
                if parsed.scheme in ["http", "https"] and (
                    parsed.netloc.lower() == base_netloc
                    or parsed.netloc.lower().endswith("." + base_domain.lower())
                ):
                    add_url(full_url)

    # 3. Dedicated subdomains
    for sub in standard_subdomains:
        add_url(f"https://{sub}.{base_domain}")

    # 4. Specialized deep paths
    for p in deep_paths:
        add_url(f"https://{base_domain}{p}")

    return ordered_candidates[:12]


def extract_attestation_hits(text: str, source_url: str) -> Dict[str, List[str]]:
    """Return high-precision first-party attestation evidence by target."""
    hits: Dict[str, List[str]] = {name: [] for name in PATTERNS}
    for name, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            start = max(0, m.start() - 180)
            end = min(len(text), m.end() + 180)
            context = " ".join(text[start:end].split())
            if not ATTESTATION_CONTEXT[name].search(context):
                continue
            if THIRD_PARTY_CONTEXT.search(context):
                continue
            hits[name].append(f"{source_url} :: ...{context}...")
            break
    return hits


def audit_vendor_compliance(row: Dict[str, str], timeout: float = 2.5) -> Dict[str, str]:
    domain = row.get("domain", "").strip()
    rank = row.get("rank", "")
    title = row.get("title", "")

    homepage_res = fetch_url(f"https://{domain}", timeout=timeout)
    if not homepage_res:
        homepage_res = fetch_url(f"http://{domain}", timeout=timeout)

    pages_checked = []
    evidence_by_claim: Dict[str, List[str]] = {name: [] for name in PATTERNS}

    hp_html = None
    hp_url = f"https://{domain}"

    if homepage_res:
        hp_html, hp_url = homepage_res
        pages_checked.append(hp_url)
        hp_text = extract_page_text_with_badges(hp_html)
        page_hits = extract_attestation_hits(hp_text, hp_url)
        for name, vals in page_hits.items():
            evidence_by_claim[name].extend(vals)

    candidates = discover_candidate_urls(domain, hp_html, hp_url)
    for c_url in candidates:
        if c_url not in pages_checked:
            c_res = fetch_url(c_url, timeout=timeout)
            if c_res:
                c_html, c_final = c_res
                pages_checked.append(c_final)
                c_text = extract_page_text_with_badges(c_html)
                page_hits = extract_attestation_hits(c_text, c_final)
                for name, vals in page_hits.items():
                    evidence_by_claim[name].extend(vals)

    iso = 1 if evidence_by_claim["iso_27001"] else 0
    soc2 = 1 if evidence_by_claim["soc_2"] else 0
    csa = 1 if evidence_by_claim["csa_star"] else 0
    total_attestations = iso + soc2 + csa
    evidence = []
    for name in ("iso_27001", "soc_2", "csa_star"):
        for item in evidence_by_claim[name][:1]:
            evidence.append(f"{name.upper()}: {item}")

    return {
        "rank": rank,
        "domain": domain,
        "title": title[:100],
        "has_iso_27001": str(iso),
        "has_soc_2": str(soc2),
        "has_csa_star": str(csa),
        "total_claimed_attestations": str(total_attestations),
        "attestation_audit_status": "observed" if pages_checked else "unreachable",
        "pages_inspected": ";".join(pages_checked),
        "attestation_evidence": " | ".join(evidence),
    }


def main():
    parser = argparse.ArgumentParser(description="Scrape public security compliance claims from SaaS domains")
    parser.add_argument(
        "--input",
        default="data/discovery/enterprise_services.csv",
        help="Input CSV of filtered SaaS domains",
    )
    parser.add_argument(
        "--output",
        default="data/discovery/automated_assurance_claims.csv",
        help="Output CSV of retrieved public-assurance claims",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Concurrent threads (default: 20)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Timeout per request in seconds (default: 2.5)",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=120.0,
        help="Maximum total wallclock wait time in seconds (default: 120.0)",
    )
    args = parser.parse_args()

    print(f"[*] Reading candidate SaaS domains from: {args.input}")
    vendors = []
    with open(args.input, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vendors.append(row)

    total = len(vendors)
    print(f"[*] Auditing {total} vendors across subdomains & trust centers with {args.concurrency} threads...")

    executor = ThreadPoolExecutor(max_workers=args.concurrency)
    future_to_vendor = {
        executor.submit(audit_vendor_compliance, v, args.timeout): v
        for v in vendors
    }

    wait_timeout = None if args.max_wait <= 0 else args.max_wait
    done, not_done = wait(future_to_vendor.keys(), timeout=wait_timeout)
    print(f"[*] Auditing completed: {len(done)}/{total} vendors audited (Timed out: {len(not_done)}). Shutting down...")
    executor.shutdown(wait=False, cancel_futures=True)

    results = []
    iso_count = 0
    soc2_count = 0
    csa_count = 0
    any_cert_count = 0

    for future in done:
        try:
            res = future.result()
        except Exception:
            v_info = future_to_vendor[future]
            res = {
                "rank": v_info.get("rank", ""),
                "domain": v_info.get("domain", ""),
                "title": v_info.get("title", ""),
                "has_iso_27001": "0",
                "has_soc_2": "0",
                "has_csa_star": "0",
                "total_claimed_attestations": "0",
                "attestation_audit_status": "error",
                "pages_inspected": "",
                "attestation_evidence": "",
            }
        results.append(res)
        if int(res["has_iso_27001"]) > 0:
            iso_count += 1
        if int(res["has_soc_2"]) > 0:
            soc2_count += 1
        if int(res["has_csa_star"]) > 0:
            csa_count += 1
        if int(res["total_claimed_attestations"]) > 0:
            any_cert_count += 1

    for future in not_done:
        v_info = future_to_vendor[future]
        results.append({
            "rank": v_info.get("rank", ""),
            "domain": v_info.get("domain", ""),
            "title": v_info.get("title", ""),
            "has_iso_27001": "0",
            "has_soc_2": "0",
            "has_csa_star": "0",
            "total_claimed_attestations": "0",
            "attestation_audit_status": "timed_out",
            "pages_inspected": "timed_out",
            "attestation_evidence": "",
        })

    results.sort(key=lambda x: int(x["rank"]) if x["rank"].isdigit() else 999999)

    fieldnames = [
        "rank",
        "domain",
        "title",
        "has_iso_27001",
        "has_soc_2",
        "has_csa_star",
        "total_claimed_attestations",
        "attestation_audit_status",
        "pages_inspected",
        "attestation_evidence",
    ]

    with open(args.output, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n[+] Successfully wrote {len(results)} public-assurance retrieval records to: {args.output}")
    print("--- Empirical Compliance Claim Statistics ---")
    print(f"Total Unique Vendors Audited: {total}")
    print(f"Vendors Claiming ISO 27001:  {iso_count} ({iso_count/max(1, total)*100:.1f}%)")
    print(f"Vendors Claiming SOC 2:      {soc2_count} ({soc2_count/max(1, total)*100:.1f}%)")
    print(f"Vendors Claiming CSA STAR:  {csa_count} ({csa_count/max(1, total)*100:.1f}%)")
    print(f"Vendors Claiming Any Cert:   {any_cert_count} ({any_cert_count/max(1, total)*100:.1f}%)")
    print(f"Vendors with Zero Claims:    {total - any_cert_count} ({(total - any_cert_count)/max(1, total)*100:.1f}%)")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
