"""The "1σ accuracy" the site prints, defined once.

Two definitions, each kept where it belongs (Antonio, 2026-10-17):

* releases already published (2025 and before, the 2026 (1,2)-sector update):
  as in their papers' tables, one sixth of the 3σ range divided by the best
  fit, for every parameter (Phys. Rev. D 111, 093006, Table I). Their printed
  values are shown as published, never recomputed.
* Bari Release 2026.a: its errors are Gaussian to a very good approximation,
  so the usual definition — the 1σ error (half the 1σ range) divided by the
  best fit — for every parameter, δ/π included (its profile is far from
  Gaussian, but not because of the octant degeneracy); only for sin²θ₂₃, whose
  allowed range spans both octants, one sixth of the 3σ range divided by the
  best fit.

Every generator imports this module; tools/tests/test_accuracy.py checks the
built pages against it.
"""

from __future__ import annotations

# The one parameter measured by its 3σ range in release 2026.a, under each
# naming the site uses (releases.yaml / history.yaml, and the release JSON).
WIDE = {"sin2_th23", "s2_23"}

NOTE_PAPERS = ("one sixth of the 3σ range divided by the best fit, in percent, "
               "as in the tables of our papers")
NOTE = ("1σ accuracy, in percent. Bari Release 2026.a: the 1σ error (half the 1σ "
        "range) divided by the best fit — its errors are Gaussian to a very good "
        "approximation; δ/π too, whose profile is far from Gaussian but not because of "
        "the octant degeneracy — except sin²θ₂₃: one sixth of the 3σ range divided by "
        "the best fit, since its range spans both octants. Earlier releases: as "
        "published, " + NOTE_PAPERS + ".")
NOTE_HTML = ("1&sigma; accuracy, in percent. Bari Release 2026.a: the 1&sigma; error "
             "(half the 1&sigma; range) divided by the best fit &mdash; its errors are "
             "Gaussian to a very good approximation; &delta;/&pi; too, whose profile is far "
             "from Gaussian but not because of the octant degeneracy &mdash; except "
             "sin&sup2;&theta;<sub>23</sub>: one sixth of the 3&sigma; range divided by the "
             "best fit, since its range spans both octants. Earlier releases: as published, "
             "one sixth of the 3&sigma; range divided by the best fit, as in the tables of "
             "our papers.")


def accuracy(param: str, best, s1, s3, rule: str = "2026a") -> float | None:
    """Percent, or None if the needed range is missing. rule "2026a" (release
    2026.a) or "papers" (earlier releases). Ranges are [lo, hi] pairs; for a
    range split in pieces pass its two ends."""
    wide = rule == "papers" or param in WIDE
    rng = s3 if wide else s1
    if not rng or best in (None, "") or not float(best):
        return None
    width = abs(float(rng[1]) - float(rng[0]))
    return width / (6.0 if wide else 2.0) / abs(float(best)) * 100.0


def text(param: str, best, s1, s3, rule: str = "2026a", nd: int = 1) -> str:
    a = accuracy(param, best, s1, s3, rule)
    return "" if a is None else f"{a:.{nd}f}"
