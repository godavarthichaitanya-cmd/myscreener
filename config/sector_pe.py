"""
config/sector_pe.py — rough, static sector-average PE benchmarks, since a
flat "PE under 25x" cutoff doesn't fit every industry equally (e.g. IT
services and FMCG typically trade at very different average multiples
than capital-intensive sectors like steel or utilities).

These are hand-set approximations, NOT live market data — treat them as
directional context next to a stock's own PE, not a precise or current
figure. Update the numbers here periodically if they drift noticeably
from reality; there's no automated refresh for this.
"""

SECTOR_PE_BENCHMARKS = {
    "Technology": 28,
    "Financial Services": 18,
    "Healthcare": 32,
    "Consumer Cyclical": 35,
    "Consumer Defensive": 45,
    "Energy": 12,
    "Basic Materials": 15,
    "Industrials": 30,
    "Communication Services": 25,
    "Utilities": 18,
    "Real Estate": 30,
}


def get_sector_pe_benchmark(sector):
    """Returns the benchmark PE for a sector string, or None if the
    sector is unknown/unmapped (a new sector not yet added above, or the
    literal "Unknown" from an un-built universe entry)."""
    if not sector:
        return None
    return SECTOR_PE_BENCHMARKS.get(sector)