"""Experimental effect roster — Mac preview rig ONLY.

palette.py (production, deployed to the Pi) does NOT import this, so these effects
never enter the gallery loop. Add a thin wrapper + one EXPERIMENTAL_PALETTE entry per
effect as it is built. Promote by moving the function into effects.py and adding a
STILL_PALETTE entry in palette.py.
"""
import effects_experimental as fx  # noqa: F401  (used by wrappers added per effect)

EXPERIMENTAL_PALETTE = []
