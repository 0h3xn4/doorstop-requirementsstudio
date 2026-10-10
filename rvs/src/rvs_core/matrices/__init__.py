"""Matrices: traceability and verification control, as plain tables with provenance."""

from rvs_core.matrices.provenance import Provenance
from rvs_core.matrices.table import MatrixTable
from rvs_core.matrices.tables import coverage_table, impact_table
from rvs_core.matrices.traceability import build_traceability
from rvs_core.matrices.vcm import VcmFilter, build_vcm
from rvs_core.trace.status import aggregate_status

__all__ = [
    "MatrixTable",
    "Provenance",
    "VcmFilter",
    "aggregate_status",
    "build_traceability",
    "build_vcm",
    "coverage_table",
    "impact_table",
]
