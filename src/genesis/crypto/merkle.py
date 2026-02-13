"""Merkle tree implementation for deterministic root computation.

Uses SHA-256 as the hash function. Leaves are sorted before tree
construction to ensure determinism (canonical ordering).

The tree is constructed over canonicalized JSON (RFC 8785 / JCS) in
production, but this module works with pre-hashed leaf values.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MerkleProof:
    """An inclusion proof for a single leaf."""
    leaf_hash: str
    path: list[tuple[str, str]]  # List of (sibling_hash, position: "L" | "R")
    root: str


class MerkleTree:
    """A deterministic Merkle tree using SHA-256.

    Usage:
        tree = MerkleTree()
        tree.add_leaf("sha256:abc123...")
        tree.add_leaf("sha256:def456...")
        root = tree.compute_root()
        proof = tree.inclusion_proof("sha256:abc123...")
    """

    def __init__(self) -> None:
        self._leaves: list[str] = []
        self._tree: list[list[str]] = []
        self._computed = False

    def add_leaf(self, leaf_hash: str) -> None:
        """Add a leaf hash. Must be called before compute_root."""
        if self._computed:
            raise RuntimeError("Tree already computed. Create a new tree.")
        self._leaves.append(leaf_hash)

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    def compute_root(self) -> str:
        """Compute the Merkle root.

        Leaves are sorted for determinism. If no leaves,
        returns a hash of empty string (null root).
        """
        if not self._leaves:
            return _sha256_hex(b"")

        # Sort leaves for canonical ordering
        sorted_leaves = sorted(self._leaves)
        self._tree = [sorted_leaves]

        current_level = sorted_leaves
        while len(current_level) > 1:
            next_level: list[str] = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent = _hash_pair(left, right)
                next_level.append(parent)
            self._tree.append(next_level)
            current_level = next_level

        self._computed = True
        return f"sha256:{current_level[0]}" if not current_level[0].startswith("sha256:") else current_level[0]

    def inclusion_proof(self, leaf_hash: str) -> MerkleProof | None:
        """Generate an inclusion proof for a leaf.

        Returns None if the leaf is not in the tree.
        Must call compute_root first.
        """
        if not self._computed:
            raise RuntimeError("Must call compute_root before generating proofs")

        sorted_leaves = self._tree[0]
        if leaf_hash not in sorted_leaves:
            return None

        idx = sorted_leaves.index(leaf_hash)
        path: list[tuple[str, str]] = []

        current_idx = idx
        for level in self._tree[:-1]:
            if current_idx % 2 == 0:
                sibling_idx = current_idx + 1
                if sibling_idx < len(level):
                    path.append((level[sibling_idx], "R"))
                else:
                    path.append((level[current_idx], "R"))  # Duplicate
            else:
                path.append((level[current_idx - 1], "L"))
            current_idx //= 2

        root = self._tree[-1][0]
        if not root.startswith("sha256:"):
            root = f"sha256:{root}"

        return MerkleProof(leaf_hash=leaf_hash, path=path, root=root)


def _sha256_hex(data: bytes) -> str:
    """Compute SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Hash two nodes together. Strips sha256: prefix if present."""
    left_clean = left.removeprefix("sha256:")
    right_clean = right.removeprefix("sha256:")
    combined = f"{left_clean}{right_clean}".encode("utf-8")
    return _sha256_hex(combined)
