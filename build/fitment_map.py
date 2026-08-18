# Normalises the live store's `pa_year-range` attribute terms into structured fitment
# the YMM lookup can query: {yearFrom, yearTo, makes, models}.
#
# The store uses only 13 distinct terms across 238 products, so this is a small lookup
# table rather than per-product work. Terms that carry no make (e.g. a bare "2019-2024")
# fall through to title parsing in generate_products.py.
import re

# Chassis families a term expands into. "Ford Super Duty" covers F-250/350/450 because
# the store lists all three together and the parts are shared across the range.
TERM_MAP = {
    "2023-2026 Ford Super Duty": (2023, 2026, ["Ford"], ["F-250", "F-350", "F-450"]),
    "2020-2022 Ford Super Duty": (2020, 2022, ["Ford"], ["F-250", "F-350", "F-450"]),
    "2017-2019 Ford Super Duty": (2017, 2019, ["Ford"], ["F-250", "F-350", "F-450"]),
    "2011-2016 Ford Super Duty": (2011, 2016, ["Ford"], ["F-250", "F-350", "F-450"]),
    "2023-2026 Ford Ranger": (2023, 2026, ["Ford"], ["Ranger", "Ranger Raptor"]),
    "2019-2026 Ram 2500/3500": (2019, 2026, ["Ram"], ["Ram 2500", "Ram 3500"]),
    "2010-2018 Ram 2500/3500": (2010, 2018, ["Ram"], ["Ram 2500", "Ram 3500"]),
    "2020-2026 Chevy Silverado HD": (2020, 2026, ["Chevrolet"], ["Silverado 2500", "Silverado 3500"]),
    "2015-2019 Chevy Silverado HD": (2015, 2019, ["Chevrolet"], ["Silverado 2500", "Silverado 3500"]),
    "2020-2026 GMC Sierra HD": (2020, 2026, ["GMC"], ["Sierra 2500", "Sierra 3500"]),
}

YEARS_ONLY = re.compile(r"^\s*(\d{4})\s*[-–]\s*(\d{4})\s*$")


def normalise(term):
    """Return (yearFrom, yearTo, makes, models) or None when the term can't be resolved.

    A bare year range with no make ("2019-2024") is unusable on its own — the caller
    should fall back to parsing the product title."""
    if not term:
        return None
    t = " ".join(term.split())
    if t in TERM_MAP:
        return TERM_MAP[t]
    m = YEARS_ONLY.match(t)
    if m:
        # years are trustworthy, make/models are not — signal a partial hit
        return (int(m.group(1)), int(m.group(2)), [], [])
    return None


def unmapped(terms):
    """Terms seen in the data that this table doesn't cover — surfaces drift when the
    store adds a new Year Range term."""
    return sorted({" ".join(t.split()) for t in terms
                   if " ".join(t.split()) not in TERM_MAP and not YEARS_ONLY.match(" ".join(t.split()))})
