"""Memory summarization logic (domain-level, no LLM calls)."""

from typing import Sequence


def extract_keywords(texts: Sequence[str], max_keywords: int = 10) -> list[str]:
    """Extract keywords from texts (simple domain logic, not AI)."""
    # Placeholder: real implementation would use domain heuristics
    # This is NOT LLM - it's pure domain logic
    words = []
    for text in texts:
        words.extend(text.lower().split())
    
    # Simple frequency-based extraction
    from collections import Counter
    counter = Counter(words)
    return [word for word, _ in counter.most_common(max_keywords)]
