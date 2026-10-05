"""
Text normalizer for replacing dynamic values in alert descriptions.

Normalization improves consistency for ML models and is critical for
Stage 3 alert correlation.
"""

import re
from typing import List, Pattern, Tuple


class Normalizer:
    """
    Normalizes alert descriptions by replacing dynamic values with placeholders.
    
    Examples:
        - Timestamps → <timestamp>
        - IP addresses → <ip>
        - UUIDs → <uuid>
        - Request IDs → <id>
        - Large numeric IDs → <id>
    """
    
    def __init__(self, patterns: List[Tuple[Pattern, str]]):
        """
        Initialize normalizer with replacement patterns.
        
        Args:
            patterns: List of (regex_pattern, replacement_string) tuples.
        """
        self.patterns = patterns
    
    def normalize(self, text: str) -> str:
        """
        Normalize a text string by applying all replacement patterns.
        
        Args:
            text: Original text to normalize.
            
        Returns:
            Normalized text with dynamic values replaced.
        """
        if not text:
            return text
        
        normalized = text
        
        # Apply all regex patterns in order
        for pattern, replacement in self.patterns:
            normalized = pattern.sub(replacement, normalized)
        
        # Convert to lowercase for consistency
        normalized = normalized.lower()
        
        # Normalize whitespace (replace multiple spaces with single space)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def normalize_batch(self, texts: List[str]) -> List[str]:
        """
        Normalize a batch of text strings.
        
        Args:
            texts: List of text strings.
            
        Returns:
            List of normalized text strings.
        """
        return [self.normalize(text) for text in texts]
