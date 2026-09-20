#!/usr/bin/env python3
"""Screen enterprise-facing technology services from a Tranco seed list.

The classifier uses explicit inclusion terms, consumer and non-commercial
exclusions, and service-domain alias deduplication. Each submitted seed retains
its original rank even when a network request fails.
"""

import argparse
import csv
import os
import re
import socket
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Dict, List, Optional, Tuple, Set

import requests
import urllib3
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Global socket timeout
socket.setdefaulttimeout(3.0)

# Suppress warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# High-specificity terms. One hit is sufficient for inclusion.
HIGH_CONFIDENCE_KEYWORDS = [
    r"\bsaas\b",
    r"\bsoftware as a service\b",
    r"\bb2b\b",
    r"\benterprise\b",
    r"\bcloud platform\b",
    r"\bcloud infrastructure\b",
    r"\bcloud services\b",
    r"\bdeveloper platform\b",
    r"\bapi\b",
    r"\bapis\b",
    r"\bdevops\b",
    r"\bcybersecurity\b",
    r"\bsecurity platform\b",
    r"\bdata platform\b",
    r"\banalytics platform\b",
    r"\bcrm\b",
    r"\berp\b",
    r"\bworkflow automation\b",
    r"\bcollaboration software\b",
    r"\bbusiness software\b",
    r"\bcompliance\b",
    r"\bidentity management\b",
    r"\bobservability\b",
    r"\bit management\b",
    r"\bweb hosting\b",
    r"\bcloud hosting\b",
    r"\bcontent delivery network\b",
    r"\bproject management\b",
    r"\bdata management\b",
]

# Generic technology terms are too broad individually. At least two distinct
# weak terms are required when no high-confidence term is present.
WEAK_KEYWORDS = [
    r"\bcloud\b",
    r"\bdevelopers\b",
    r"\bdeveloper\b",
    r"\bsecurity\b",
    r"\bmonitoring\b",
    r"\bcollaboration\b",
    r"\binfrastructure\b",
    r"\bcdn\b",
    r"\bai platform\b",
    r"\bdatabase\b",
    r"\bsoftware\b",
    r"\bplatform\b",
]

# Negative consumer / sensitive keywords
NEGATIVE_KEYWORDS = [
    r"\bcasino\b",
    r"\bgambling\b",
    r"\bbetting\b",
    r"\bporn\b",
    r"\badult\b",
    r"\bxxx\b",
    r"\btorrent\b",
    r"\bfree movies\b",
    r"\bstreaming movies\b",
    r"\bdating\b",
    r"\bescort\b",
    r"\bvideo games\b",
    r"\bonline games\b",
    r"\bindie games\b",
    r"\bgame developer\b",
    r"\bmanga\b",
    r"\banime\b",
    r"\bblog tool\b",
    r"\bdigital publishing platform\b",
    r"\bweb browser\b",
    r"\bhome security\b",
    r"\bsmart home\b",
    r"\bcrowdfunding\b",
    r"\bfundraising platform\b",
    r"\bpress release distribution\b",
    r"\bstatistics portal\b",
    r"\bgif\b",
]

# Non-commercial / government / pure foundation domains to exclude from B2B SaaS study
NON_COMMERCIAL_EXCLUSIONS = {
    "nist.gov",
    "apache.org",
    "mozilla.org",
    "lencr.org",
    "w3.org",
    "ietf.org",
    "wikipedia.org",
    "wikimedia.org",
    "archive.org",
    "gnu.org",
    "debian.org",
    "kernel.org",
    "eff.org",
    "icann.org",
    "iana.org",
    "unesco.org",
    "letsencrypt.org",
    "wordpress.org",
}

# Known aliases for the same externally marketed service. This is intentionally
# narrower than corporate-parent ownership: separately operated products (for
# example GitHub and Microsoft) remain separate observations.
PARENT_ENTITY_MAPPING = {
    "workers.dev": "cloudflare.com",
    "pages.dev": "cloudflare.com",
    "windows.net": "microsoft.com",
    "windows.com": "microsoft.com",
    "azure.com": "microsoft.com",
    "fastly.net": "fastly.com",
    "doubleclick.net": "google.com",
    "b-cdn.net": "bunny.net",
    "cdninstagram.com": "meta.com",
    "fbcdn.net": "meta.com",
    "whatsapp.com": "meta.com",
    "googleusercontent.com": "google.com",
    "googlevideo.com": "google.com",
    "ytimg.com": "google.com",
    "amazonaws.com": "amazon.com",
    "elasticbeanstalk.com": "amazon.com",
    "nginx.com": "f5.com",
    "zoom.us": "zoom.com",
    "mailchi.mp": "mailchimp.com",
    "onelink.me": "appsflyer.com",
    "atlassian.net": "atlassian.com",
    "wpguardian.io": "wpguardian.com",
    "digitaloceanspaces.com": "digitalocean.com",
    "visualstudio.com": "microsoft.com",
    "netlify.app": "netlify.com",
    "vercel.app": "vercel.com",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_page_metadata(domain: str, timeout: float = 2.5) -> Tuple[str, str, int]:
    urls_to_try = [f"https://{domain}", f"http://{domain}"]
    for url in urls_to_try:
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                verify=False,
                allow_redirects=True,
            )
            status_code = resp.status_code
            if status_code in [200, 301, 302, 403]:
                text = resp.text[:65536]
                soup = BeautifulSoup(text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                desc = ""
                meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
                if not meta_desc:
                    meta_desc = soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})
                if meta_desc and meta_desc.get("content"):
                    desc = meta_desc["content"].strip()

                clean_title = " ".join(title.split())
                clean_desc = " ".join(desc.split())
                if clean_title or clean_desc:
                    return clean_title, clean_desc, status_code
        except Exception:
            continue
    return "", "", 0


def classify_domain(domain: str, title: str, description: str) -> Tuple[bool, List[str], str]:
    if any(domain.endswith(ext) for ext in [".gov", ".mil", ".edu"]) or domain in NON_COMMERCIAL_EXCLUSIONS:
        return False, [], "excluded_non_commercial_or_gov"

    combined = f"{title} {description}".lower()
    if not combined.strip():
        return False, [], "no_content_fetched"

    for neg in NEGATIVE_KEYWORDS:
        if re.search(neg, combined):
            return False, [], "excluded_consumer_or_sensitive"

    high_matches = []
    for pos in HIGH_CONFIDENCE_KEYWORDS:
        if re.search(pos, combined):
            high_matches.append(pos.replace(r"\b", ""))

    weak_matches = []
    for pos in WEAK_KEYWORDS:
        if re.search(pos, combined):
            weak_matches.append(pos.replace(r"\b", ""))

    unique_high = sorted(set(high_matches))
    unique_weak = sorted(set(weak_matches))
    unique_matches = unique_high + [m for m in unique_weak if m not in unique_high]
    if unique_high or len(unique_weak) >= 2:
        return True, unique_matches, ""
    return False, unique_matches, "insufficient_enterprise_evidence"


def process_domain(row: Dict[str, str], timeout: float) -> Dict[str, str]:
    rank = row.get("rank", "")
    domain = row.get("domain", "").strip()

    title, desc, status_code = fetch_page_metadata(domain, timeout=timeout)
    is_saas, matches, reason = classify_domain(domain, title, desc)

    return {
        "rank": rank,
        "domain": domain,
        "is_saas": "True" if is_saas else "False",
        "title": title[:100],
        "meta_description": desc[:150],
        "matched_keywords": ";".join(matches),
        "exclusion_reason": reason,
        "status_code": str(status_code),
    }


def main():
    parser = argparse.ArgumentParser(description="Filter SaaS/Technology Domains from Tranco list")
    parser.add_argument(
        "--input",
        default="data/discovery/tranco_seed.csv",
        help="Input CSV containing rank,domain",
    )
    parser.add_argument(
        "--output",
        default="data/discovery/enterprise_services.csv",
        help="Output CSV of screened enterprise-service domains",
    )
    parser.add_argument(
        "--output-all",
        default="data/discovery/screening_log.csv",
        help="Output CSV of all screened domains and decision metadata",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum domains to inspect from input (default: 1000)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=35,
        help="Concurrent threads for fetching (default: 35)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="HTTP timeout in seconds (default: 2.5)",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=90.0,
        help="Maximum total wallclock wait time in seconds (default: 90.0)",
    )
    args = parser.parse_args()

    print(f"[*] Reading input seed list: {args.input}")
    domains_to_process = []
    with open(args.input, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= args.limit:
                break
            domains_to_process.append(row)

    total = len(domains_to_process)
    print(f"[*] Starting classification of top {total} domains with {args.concurrency} threads...")

    executor = ThreadPoolExecutor(max_workers=args.concurrency)
    future_to_row = {
        executor.submit(process_domain, row, args.timeout): row
        for row in domains_to_process
    }

    wait_timeout = None if args.max_wait <= 0 else args.max_wait
    done, not_done = wait(future_to_row.keys(), timeout=wait_timeout)
    print(f"[*] Completed {len(done)}/{total} domains (Timed out: {len(not_done)}). Shutting down workers...")
    executor.shutdown(wait=False, cancel_futures=True)

    results = []
    saas_count = 0
    for future in done:
        try:
            res = future.result()
        except Exception as exc:
            original = future_to_row[future]
            res = {
                "rank": original.get("rank", ""),
                "domain": original.get("domain", ""),
                "is_saas": "False",
                "title": "",
                "meta_description": "",
                "matched_keywords": "",
                "exclusion_reason": f"error_{str(exc)[:30]}",
                "status_code": "0",
            }
        results.append(res)
        if res["is_saas"] == "True":
            saas_count += 1

    for future in not_done:
        original = future_to_row[future]
        results.append({
            "rank": original.get("rank", ""),
            "domain": original.get("domain", ""),
            "is_saas": "False",
            "title": "",
            "meta_description": "",
            "matched_keywords": "",
            "exclusion_reason": "worker_pool_timeout",
            "status_code": "0",
        })

    results.sort(key=lambda x: int(x["rank"]) if x["rank"].isdigit() else 999999)

    # Write full classification log
    fieldnames = [
        "rank",
        "domain",
        "is_saas",
        "title",
        "meta_description",
        "matched_keywords",
        "exclusion_reason",
        "status_code",
    ]
    with open(args.output_all, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"[+] Full classification log saved to: {args.output_all}")

    # Deduplicate service aliases. The first (best-ranked) representative is kept.
    seen_entities: Set[str] = set()
    deduped_saas = []

    for r in results:
        if r["is_saas"] == "True":
            dom = r["domain"]
            canonical_entity = PARENT_ENTITY_MAPPING.get(dom, dom)
            if canonical_entity not in seen_entities:
                seen_entities.add(canonical_entity)
                r["primary_domain"] = canonical_entity
                deduped_saas.append(r)

    saas_fieldnames = ["rank", "domain", "title", "matched_keywords"]
    with open(args.output, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=saas_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deduped_saas)

    print(f"[+] Screened and deduplicated enterprise-service cohort: {len(deduped_saas)} service domains saved to: {args.output}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
