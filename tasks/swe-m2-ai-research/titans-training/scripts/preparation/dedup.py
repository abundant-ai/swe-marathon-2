"""Whole-document identity and sampled-shingle duplicate screening."""

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict


class DuplicateIndex:
    """Reject repeat groups, normalized exact copies and high-overlap text copies.

    Five-word shingles are sampled by a fixed hash predicate (one in 64). A
    document is a near duplicate when at least eight sampled shingles overlap
    and that overlap covers at least 80% of the smaller signature. This also
    screens copies of a long book excerpt inside a shorter web document. It is
    a heuristic, not a guarantee against paraphrases or short copied passages.
    """

    def __init__(self) -> None:
        """Create an empty index shared across all selected corpora and splits."""
        self.groups: set[str] = set()
        self.exact: set[str] = set()
        self.sizes: list[int] = []
        self.postings: dict[int, list[int]] = defaultdict(list)
        self.counts: Counter[str] = Counter()

    def accept(self, group: str, text: str) -> str | None:
        """Register a new document only if it passes the duplicate checks.

        Args:
            group: Canonical URL, book ID or article identity.
            text: Original source text; normalization is for screening only.

        Returns:
            Normalized text SHA-256 when accepted, otherwise None.
        """
        self.counts["examined"] += 1
        normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        if group in self.groups:
            self.counts["repeat_group"] += 1
            return None
        if digest in self.exact:
            self.counts["exact_copy"] += 1
            return None
        words = re.findall(r"\w+", normalized)
        signature: set[int] = set()
        for start in range(len(words) - 4):
            value = int.from_bytes(hashlib.blake2b(" ".join(words[start:start + 5]).encode(),
                                                  digest_size=8).digest(), "little")
            if value & 63 == 0:
                signature.add(value)
        matches: Counter[int] = Counter()
        for value in signature:
            matches.update(self.postings.get(value, ()))
        if any(shared >= 8 and shared / min(len(signature), self.sizes[other]) >= 0.8
               for other, shared in matches.items()):
            self.counts["near_copy"] += 1
            return None
        index = len(self.sizes)
        self.sizes.append(len(signature))
        for value in signature:
            self.postings[value].append(index)
        self.groups.add(group)
        self.exact.add(digest)
        self.counts["accepted"] += 1
        return digest
