#!/usr/bin/env python3
"""Explore the JLCPCB PCB-Assembly (SMT) quote flow with the authenticated profile.

Answers: what URL serves the assembly quote, what file inputs it exposes
(BOM / CPL / gerbers), and what the page says before anything is uploaded.
Read-only: no uploads.
"""
import os
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import QUOTE_URL  # noqa: E402

CANDIDATES = [
    "https://cart.jlcpcb.com/quote/pcbOrderFoi",
    "https://cart.jlcpcb.com/quote",
    "https://jlcpcb.com/pcb-assembly",
    "https://cart.jlcpcb.com/quote/pcbAssembly",
]


def dump(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    print(f"\n{'='*70}\n{url}  -> {page.url}\n{'='*70}")
    # auth check
    txt = page.inner_text("body")[:4000]
    print("auth 'My Account' present:", "My Account" in txt)
    print("has 'Sign In' nav:", "Sign In" in txt[:1500])
    # all file inputs
    inputs = page.eval_on_selector_all(
        "input[type=file]",
        "els => els.map(e => ({id:e.id, name:e.name, cls:e.className, accept:e.accept}))",
    )
    print(f"file inputs ({len(inputs)}):")
    for i in inputs:
        print("   ", i)
    # buttons / links with BOM/CPL/assembly text
    hits = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('a,button,div,span,li').forEach(e => {
                const t = (e.innerText||'').trim();
                if (!t || t.length > 60) return;
                if (/\\bBOM\\b|CPL|pick.?and.?place|assembly|add.*gerber|upload/i.test(t)) {
                    out.push({tag:e.tagName, text:t, cls:(e.className||'').slice(0,60)});
                }
            });
            return out.slice(0, 40);
        }"""
    )
    print(f"assembly-related elements ({len(hits)}):")
    for h in hits:
        print("   ", h)
    print("--- text snippet ---")
    print(txt[:900].replace("\n", " | "))


def main():
    with browser() as page:
        for url in CANDIDATES:
            try:
                dump(page, url)
            except Exception as e:  # noqa: BLE001
                print(f"\n=== {url} FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
