"""Predicate canonicalization and semantic alignment resolver."""

from __future__ import annotations

import re
import difflib

try:
    from rapidfuzz import fuzz
except ImportError:
    class FuzzFallback:
        @staticmethod
        def ratio(s1: str, s2: str) -> float:
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100.0
    fuzz = FuzzFallback()


class PredicateResolver:
    """
    Normalizes and canonicalizes fact predicates to enable robust comparison
    across documents with varying wording (e.g. 'reported revenue of' vs 'total income').
    """

    SYNONYM_GROUPS: dict[str, list[str]] = {
        "REVENUE": [
            "revenue", "total revenue", "sales", "net sales", "total sales",
            "turnover", "total turnover", "total income", "gross income",
            "gross revenue", "topline", "top line", "reported revenue",
        ],
        "NET_INCOME": [
            "net income", "net profit", "profit after tax", "pat",
            "net earnings", "net loss", "bottom line", "net profit after tax",
            "reported net income", "consolidated net profit",
        ],
        "OPERATING_INCOME": [
            "operating income", "operating profit", "ebit", "operating earnings",
            "operating result", "profit from operations",
        ],
        "EBITDA": [
            "ebitda", "adjusted ebitda", "operating ebitda", "normalized ebitda",
        ],
        "GROSS_PROFIT": [
            "gross profit", "gross income", "gross earnings",
        ],
        "GROSS_MARGIN": [
            "gross margin", "gross profit margin", "gross margin percentage",
        ],
        "OPERATING_MARGIN": [
            "operating margin", "operating profit margin", "ebit margin",
        ],
        "NET_MARGIN": [
            "net margin", "net profit margin", "profit margin",
        ],
        "EPS": [
            "eps", "earnings per share", "diluted eps", "basic eps",
            "diluted earnings per share", "basic earnings per share",
        ],
        "GROWTH_RATE": [
            "growth rate", "gdp growth", "gdp growth rate", "expansion rate",
            "annual growth", "economic growth", "real gdp growth rate",
            "gdp constant prices", "growth", "growth trend",
        ],
        "DECLINE_RATE": [
            "decline rate", "contraction rate", "drop rate", "fall rate",
        ],
        "INFLATION_RATE": [
            "inflation rate", "headline inflation", "cpi inflation", "wpi inflation",
            "inflation trend", "consumer price index", "inflation",
        ],
        "POLICY_RATE": [
            "policy rate", "repo rate", "policy repo rate", "benchmark rate",
            "reverse repo rate", "discount rate", "interest rate",
        ],
        "FISCAL_DEFICIT": [
            "fiscal deficit", "fiscal deficit ratio", "deficit ratio",
            "government deficit", "budget deficit",
        ],
        "CURRENT_ACCOUNT_DEFICIT": [
            "current account deficit", "cad", "cad ratio",
        ],
        "HEADCOUNT": [
            "headcount", "employees", "total employees", "workforce",
            "full-time employees", "number of employees", "staff count",
        ],
        "CASH_AND_EQUIVALENTS": [
            "cash and cash equivalents", "cash and equivalents", "total cash",
            "cash balance", "cash and bank balances",
        ],
        "TOTAL_DEBT": [
            "total debt", "total borrowings", "debt", "gross debt", "borrowings",
        ],
        "TOTAL_ASSETS": [
            "total assets", "assets", "aggregate assets",
        ],
        "TOTAL_LIABILITIES": [
            "total liabilities", "liabilities", "aggregate liabilities",
        ],
        "CAPITAL_EXPENDITURE": [
            "capital expenditure", "capex", "capital spending",
        ],
        "FREE_CASH_FLOW": [
            "free cash flow", "fcf", "operating cash flow minus capex",
        ],
        "CREDIT_GROWTH": [
            "credit growth", "bank credit growth", "loan growth",
        ],
        "DEPOSIT_GROWTH": [
            "deposit growth", "bank deposit growth", "aggregate deposits",
        ],
        "CERTIFICATES_OF_DEPOSIT": [
            "certificates of deposit", "cds", "issuances of certificates of deposit",
            "issuances of cds", "cd issuances",
        ],
        "CHIEF_EXECUTIVE_OFFICER": [
            "ceo", "chief executive officer", "managing director", "md & ceo",
            "executive officer",
        ],
        "CHIEF_FINANCIAL_OFFICER": [
            "cfo", "chief financial officer", "finance director",
        ],
        "FISCAL_POLICY": [
            "fiscal policy", "fiscal consolidation", "fiscal consolidation path",
        ],
    }

    FILLER_PREFIXES = [
        r"^(?:reported|posted|generated|totaled|achieved|amounted\s+to|recorded|registered|showed|delivered|clocked)\s+",
        r"^(?:is\s+estimated\s+to\s+have\s+grown\s+by|estimated\s+to\s+grow\s+by)\s+",
        r"^(?:is|was|are|were|has|have|had|been)\s+",
        r"^(?:estimated|projected|expected|forecasted)\s+",
    ]

    TRAILING_WORDS = r"\s+(?:of|was|is|at|for|in|to|by|on)$"

    def __init__(self):
        self._synonym_index: dict[str, str] = {}
        for canonical, variants in self.SYNONYM_GROUPS.items():
            self._synonym_index[canonical.lower().replace("_", " ")] = canonical
            for variant in variants:
                norm = self._clean_string(variant)
                self._synonym_index[norm] = canonical

    def _clean_string(self, text: str) -> str:
        s = text.lower().strip()
        for pat in self.FILLER_PREFIXES:
            s = re.sub(pat, "", s).strip()
        s = re.sub(self.TRAILING_WORDS, "", s).strip()
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def canonicalize(self, predicate: str) -> str:
        cleaned = self._clean_string(predicate)
        if cleaned in self._synonym_index:
            return self._synonym_index[cleaned]

        # Match longest synonym variant contained in cleaned string with word boundaries
        best_match = None
        best_len = 0
        for variant, canonical in self._synonym_index.items():
            if len(variant) >= 3 and re.search(r'\b' + re.escape(variant) + r'\b', cleaned):
                if len(variant) > best_len:
                    best_len = len(variant)
                    best_match = canonical

        if best_match:
            return best_match

        return cleaned.upper().replace(" ", "_")

    def are_same_predicate(self, pred_a: str, pred_b: str) -> bool:
        clean_a = self._clean_string(pred_a)
        clean_b = self._clean_string(pred_b)

        if clean_a == clean_b:
            return True

        canon_a = self.canonicalize(pred_a)
        canon_b = self.canonicalize(pred_b)
        if canon_a and canon_b and canon_a == canon_b and not canon_a.startswith("GENERAL_"):
            return True

        if clean_a in self._synonym_index and clean_b in self._synonym_index:
            if self._synonym_index[clean_a] == self._synonym_index[clean_b]:
                return True

        words_a = set(clean_a.split())
        words_b = set(clean_b.split())
        if words_a and words_b:
            intersection = words_a.intersection(words_b)
            significant = [w for w in intersection if len(w) > 2]
            if len(significant) >= min(len(words_a), len(words_b)) and len(significant) >= 1:
                return True

        sim = fuzz.ratio(clean_a, clean_b)
        return sim >= 82.0
