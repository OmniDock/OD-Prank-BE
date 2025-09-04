"""
Design chat nodes for interactive scenario refinement
"""
from .refine_node import refine_description_node
from .suggestion_node import generate_suggestion_node

__all__ = [
    'refine_description_node',
    'generate_suggestion_node'
]
