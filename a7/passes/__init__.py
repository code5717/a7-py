"""
Semantic analysis passes for A7.

Implements multi-pass semantic analysis:
1. Name resolution - Build symbol tables and resolve names
2. Type checking - Infer and check types
3. Semantic validation - Validate control flow, memory management, etc.
4. Safety proof - Prove risky operations and create a backend plan
"""

from .name_resolution import NameResolutionPass
from .type_checker import TypeCheckingPass
from .semantic_validator import SemanticValidationPass
from a7.safety import SafetyProofPass

__all__ = [
    'NameResolutionPass',
    'TypeCheckingPass',
    'SemanticValidationPass',
    'SafetyProofPass',
]
