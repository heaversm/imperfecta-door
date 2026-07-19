"""Experimental effect roster — Mac preview rig ONLY.

palette.py (production, deployed to the Pi) does NOT import this, so these effects
never enter the gallery loop. Add a thin wrapper + one EXPERIMENTAL_PALETTE entry per
effect as it is built. Promote by moving the function into effects.py and adding a
STILL_PALETTE entry in palette.py.
"""
import effects_experimental as fx  # noqa: F401  (used by wrappers added per effect)

# The 2026-07-18 reference batch was promoted into palette.py's STILL_PALETTE, so the
# staging roster is empty until the next experiment. Add wrappers + entries here to
# preview new effects_experimental functions in the rig.
EXPERIMENTAL_PALETTE = []
