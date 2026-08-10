"""Neutrino News — daily pipeline behind site-src/content/Neutrino-News.md.

Deterministic fetchers write dated raw caches; one Claude call turns those
records into prose; the renderer resolves every link from the cache, never
from the model's text. See docs/superpowers/specs/2026-08-09-neutrino-news-design.md.
"""
