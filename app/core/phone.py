"""Kenyan mobile number normalization (strategic plan W4).

``normalize_ke_msisdn`` is the single canonical write/lookup form for phone
numbers across members, payment intents, and provider adapters. The STK
adapter keeps its stricter Safaricom-only contract on top of this helper.
"""

import re

_NONDIGIT = re.compile(r"\D")


def normalize_ke_msisdn(raw: str) -> str:
    """Return the ``254...`` international form of a Kenyan mobile number.

    Strips ``+`` and separators, then folds the common national variants:
    - ``07XXXXXXXX``  -> ``2547XXXXXXXX``
    - ``7XXXXXXXX``   -> ``2547XXXXXXXX``
    - ``011XXXXXXX``  -> ``25411XXXXXXX`` (Safaricom 011x range)
    - ``+2547...``    -> ``2547...`` (unchanged)

    Non-dialable strings are returned digit-only, matching the historical
    lenient member storage; provider adapters apply their own strictness.
    """
    digits = _NONDIGIT.sub("", raw)
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    return digits
