"""IoA-Bench v5 scientific measurement layer.

Everything under this package belongs to the v5 scientific line (ADR-V5-000). It never imports
v4 suite runtimes or scorers; it reuses only provider-neutral infrastructure (ModelPort, hashing,
AttemptJournal, replay container).
"""

V5_LAYER_VERSION = "5.0.0-dev"
