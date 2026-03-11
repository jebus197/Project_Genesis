#!/usr/bin/env python3
"""Tests for file_integrity.py — defence-in-depth coordination file integrity.

Tests all three layers:
  Layer 1 — Local:  SHA-256 hash + Ed25519 signing + verification
  Layer 2 — Chain:  Append-only hash-chain linking + chain verification
  Layer 3 — Anchor: Merkle tree construction + rollup

OB database is NOT required — Layer 3 anchor test mocks the subprocess call.
Ed25519 keypair at ~/.openbrain/keys/ IS required for signing tests;
tests skip gracefully if absent.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Import module under test
import file_integrity as fi


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temp directory and redirect the integrity log there."""
    original_log = fi.INTEGRITY_LOG
    fi.INTEGRITY_LOG = tmp_path / ".integrity_chain.jsonl"
    yield tmp_path
    fi.INTEGRITY_LOG = original_log


@pytest.fixture
def sample_file(tmp_dir):
    """Create a sample file to sign."""
    p = tmp_dir / "sample.md"
    p.write_text("# Test\nSome content for integrity testing.\n")
    return p


@pytest.fixture
def has_keys():
    """Check whether Ed25519 keypair exists; skip test if not."""
    if not fi.HAS_CRYPTO:
        pytest.skip("cryptography library not installed")
    if not fi.PRIVATE_KEY_FILE.exists():
        pytest.skip("No Ed25519 keypair at ~/.openbrain/keys/")


# ---------------------------------------------------------------------------
# Layer 1 — File hashing
# ---------------------------------------------------------------------------

class TestFileHashing:
    def test_hash_file_returns_sha256_prefix(self, sample_file):
        result = fi.hash_file(sample_file)
        assert result.startswith("sha256:")
        assert len(result) == 7 + 64  # "sha256:" + 64 hex chars

    def test_hash_file_deterministic(self, sample_file):
        h1 = fi.hash_file(sample_file)
        h2 = fi.hash_file(sample_file)
        assert h1 == h2

    def test_hash_file_changes_with_content(self, tmp_dir):
        f = tmp_dir / "changing.txt"
        f.write_text("version 1")
        h1 = fi.hash_file(f)
        f.write_text("version 2")
        h2 = fi.hash_file(f)
        assert h1 != h2

    def test_hash_entry_deterministic(self):
        entry = {"file": "/test", "sha256": "sha256:abc", "agent": "cc",
                 "timestamp": "2026-01-01T00:00:00Z", "previous_hash": "sha256:genesis"}
        h1 = fi.hash_entry(entry)
        h2 = fi.hash_entry(entry)
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_hash_entry_key_order_irrelevant(self):
        """Canonical JSON is sorted — key insertion order doesn't matter."""
        e1 = {"file": "/a", "agent": "cc", "sha256": "sha256:x", "previous_hash": "sha256:genesis", "timestamp": "t"}
        e2 = {"agent": "cc", "timestamp": "t", "previous_hash": "sha256:genesis", "sha256": "sha256:x", "file": "/a"}
        assert fi.hash_entry(e1) == fi.hash_entry(e2)


# ---------------------------------------------------------------------------
# Layer 1 — Ed25519 signing
# ---------------------------------------------------------------------------

class TestEd25519Signing:
    def test_sign_and_verify(self, has_keys):
        content = b"test content for signing"
        sig = fi.sign_content(content)
        assert sig is not None
        assert fi.verify_ed25519(content, sig) is True

    def test_verify_rejects_tampered(self, has_keys):
        content = b"original"
        sig = fi.sign_content(content)
        assert fi.verify_ed25519(b"tampered", sig) is False

    def test_verify_rejects_bad_hex(self, has_keys):
        assert fi.verify_ed25519(b"anything", "not_valid_hex") is False

    def test_sign_returns_none_without_key(self):
        """If private key doesn't exist, sign_content returns None."""
        with mock.patch.object(fi, '_load_private_key', return_value=None):
            assert fi.sign_content(b"test") is None


# ---------------------------------------------------------------------------
# Layer 1 — File signing and verification
# ---------------------------------------------------------------------------

class TestFileSignAndVerify:
    def test_sign_file_creates_entry(self, tmp_dir, sample_file):
        entry = fi.cmd_sign_file(str(sample_file), "cc")
        assert entry["file"] == str(sample_file.resolve())
        assert entry["agent"] == "cc"
        assert entry["sha256"].startswith("sha256:")
        assert entry["previous_hash"] == fi.GENESIS_HASH
        assert "timestamp" in entry

    def test_sign_file_with_ed25519(self, tmp_dir, sample_file, has_keys):
        entry = fi.cmd_sign_file(str(sample_file), "cc")
        assert "signature" in entry
        assert len(entry["signature"]) == 128  # Ed25519 sig = 64 bytes = 128 hex

    def test_verify_file_returns_verified(self, tmp_dir, sample_file):
        fi.cmd_sign_file(str(sample_file), "cc")
        result = fi.cmd_verify_file(str(sample_file))
        assert result["status"] == "VERIFIED"

    def test_verify_file_detects_modification(self, tmp_dir, sample_file):
        fi.cmd_sign_file(str(sample_file), "cc")
        sample_file.write_text("Modified content!")
        result = fi.cmd_verify_file(str(sample_file))
        assert result["status"] == "MODIFIED"

    def test_verify_file_untracked(self, tmp_dir):
        f = tmp_dir / "untracked.txt"
        f.write_text("not signed")
        result = fi.cmd_verify_file(str(f))
        assert result["status"] == "UNTRACKED"

    def test_verify_file_not_found(self, tmp_dir):
        result = fi.cmd_verify_file("/nonexistent/file.md")
        assert result["status"] == "ERROR"

    def test_sign_file_not_found_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            fi.cmd_sign_file("/nonexistent/file.md", "cc")

    def test_verify_signature_valid(self, tmp_dir, sample_file, has_keys):
        """Full round-trip: sign → verify file → confirm signature_valid."""
        fi.cmd_sign_file(str(sample_file), "cc")
        result = fi.cmd_verify_file(str(sample_file))
        assert result["status"] == "VERIFIED"
        assert result["signature_valid"] is True

    def test_latest_entry_wins(self, tmp_dir, sample_file):
        """When signed multiple times, verify uses the latest entry."""
        fi.cmd_sign_file(str(sample_file), "cc")
        sample_file.write_text("updated content")
        fi.cmd_sign_file(str(sample_file), "cc")
        result = fi.cmd_verify_file(str(sample_file))
        assert result["status"] == "VERIFIED"


# ---------------------------------------------------------------------------
# Layer 2 — Hash chain
# ---------------------------------------------------------------------------

class TestHashChain:
    def test_chain_genesis(self, tmp_dir):
        """First entry links to GENESIS_HASH."""
        f = tmp_dir / "first.txt"
        f.write_text("first")
        entry = fi.cmd_sign_file(str(f), "cc")
        assert entry["previous_hash"] == fi.GENESIS_HASH

    def test_chain_linking(self, tmp_dir):
        """Second entry links to the hash of the first entry."""
        f1 = tmp_dir / "first.txt"
        f1.write_text("first")
        entry1 = fi.cmd_sign_file(str(f1), "cc")

        f2 = tmp_dir / "second.txt"
        f2.write_text("second")
        entry2 = fi.cmd_sign_file(str(f2), "cc")

        expected_prev = fi.hash_entry(entry1)
        assert entry2["previous_hash"] == expected_prev

    def test_verify_chain_empty(self, tmp_dir):
        """Empty chain is valid."""
        result = fi.verify_chain()
        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["broken_chain"] == []
        assert result["broken_sig"] == []

    def test_verify_chain_intact(self, tmp_dir):
        """Three entries: all valid, all linked."""
        for i in range(3):
            f = tmp_dir / f"file_{i}.txt"
            f.write_text(f"content {i}")
            fi.cmd_sign_file(str(f), "cc")

        result = fi.verify_chain()
        assert result["total"] == 3
        assert result["valid"] == 3
        assert result["broken_chain"] == []

    def test_verify_chain_detects_tamper(self, tmp_dir):
        """Tampering with the log breaks the chain."""
        for i in range(3):
            f = tmp_dir / f"file_{i}.txt"
            f.write_text(f"content {i}")
            fi.cmd_sign_file(str(f), "cc")

        # Tamper with the log — modify the second entry
        lines = fi.INTEGRITY_LOG.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        entry["sha256"] = "sha256:tampered_hash_value"
        lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        fi.INTEGRITY_LOG.write_text("\n".join(lines) + "\n")

        result = fi.verify_chain()
        assert len(result["broken_chain"]) > 0  # Chain broken by tamper

    def test_verify_chain_detects_sig_failure(self, tmp_dir, has_keys):
        """Invalid signature in a chain entry is detected."""
        f = tmp_dir / "signed.txt"
        f.write_text("content")
        fi.cmd_sign_file(str(f), "cc")

        # Corrupt the signature
        lines = fi.INTEGRITY_LOG.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        if "signature" in entry:
            entry["signature"] = "ff" * 64  # Invalid signature
            lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
            fi.INTEGRITY_LOG.write_text("\n".join(lines) + "\n")

            result = fi.verify_chain()
            assert len(result["broken_sig"]) > 0


# ---------------------------------------------------------------------------
# Layer 3 — Merkle rollup
# ---------------------------------------------------------------------------

class TestMerkleRollup:
    def test_merkle_root_empty(self):
        """Empty hash list returns GENESIS_HASH."""
        assert fi._build_merkle_root([]) == fi.GENESIS_HASH

    def test_merkle_root_single(self):
        """Single hash — root is hash of that hash."""
        h = "sha256:abc123"
        root = fi._build_merkle_root([h])
        expected = f"sha256:{hashlib.sha256(h.encode('utf-8')).hexdigest()}"
        assert root == expected

    def test_merkle_root_deterministic(self):
        """Same inputs produce same root."""
        hashes = ["sha256:aaa", "sha256:bbb", "sha256:ccc"]
        r1 = fi._build_merkle_root(hashes)
        r2 = fi._build_merkle_root(hashes)
        assert r1 == r2

    def test_merkle_root_order_sensitive(self):
        """Different order produces different root."""
        hashes = ["sha256:aaa", "sha256:bbb"]
        r1 = fi._build_merkle_root(hashes)
        r2 = fi._build_merkle_root(["sha256:bbb", "sha256:aaa"])
        assert r1 != r2

    def test_merkle_root_odd_promotion(self):
        """Odd number of leaves: last is duplicated, not dropped."""
        two = fi._build_merkle_root(["sha256:a", "sha256:b"])
        three = fi._build_merkle_root(["sha256:a", "sha256:b", "sha256:c"])
        assert two != three  # Third entry changes the root

    def test_rollup_without_anchor(self, tmp_dir):
        """Rollup computes Merkle root without requiring OB."""
        for i in range(3):
            f = tmp_dir / f"file_{i}.txt"
            f.write_text(f"content {i}")
            fi.cmd_sign_file(str(f), "cc")

        result = fi.cmd_rollup(anchor=False)
        assert result["entries"] == 3
        assert result["merkle_root"].startswith("sha256:")
        assert result["anchored"] is False

    def test_rollup_empty_chain(self, tmp_dir):
        """Rollup with no entries returns genesis."""
        result = fi.cmd_rollup(anchor=False)
        assert result["entries"] == 0
        assert result["merkle_root"] == fi.GENESIS_HASH

    def test_rollup_anchor_mocked(self, tmp_dir):
        """Anchor path calls OB CLI; mock it for unit testing."""
        f = tmp_dir / "test.txt"
        f.write_text("content")
        fi.cmd_sign_file(str(f), "cc")

        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            result = fi.cmd_rollup(anchor=True)
            assert result["anchored"] is True
            # Verify the subprocess was called with OB CLI args
            call_args = mock_run.call_args[0][0]
            assert "-m" in call_args
            assert "open_brain.cli" in call_args
            assert "capture" in call_args

    def test_rollup_anchor_graceful_degradation(self, tmp_dir):
        """When OB is unavailable, anchor fails gracefully."""
        f = tmp_dir / "test.txt"
        f.write_text("content")
        fi.cmd_sign_file(str(f), "cc")

        with mock.patch("subprocess.run", side_effect=OSError("No OB")):
            result = fi.cmd_rollup(anchor=True)
            assert result["anchored"] is False
            assert "anchor_error" in result


# ---------------------------------------------------------------------------
# Integration: full lifecycle
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_lifecycle(self, tmp_dir):
        """Sign 3 files → verify each → verify chain → rollup."""
        files = []
        for i in range(3):
            f = tmp_dir / f"file_{i}.txt"
            f.write_text(f"content for file {i}")
            files.append(f)
            fi.cmd_sign_file(str(f), "cc")

        # Verify each file
        for f in files:
            result = fi.cmd_verify_file(str(f))
            assert result["status"] == "VERIFIED"

        # Verify chain
        chain = fi.verify_chain()
        assert chain["total"] == 3
        assert chain["valid"] == 3
        assert chain["broken_chain"] == []

        # Rollup
        rollup = fi.cmd_rollup(anchor=False)
        assert rollup["entries"] == 3
        assert rollup["merkle_root"].startswith("sha256:")

    def test_modification_detection_lifecycle(self, tmp_dir):
        """Sign → modify → detect → re-sign → verify."""
        f = tmp_dir / "evolving.txt"
        f.write_text("version 1")
        fi.cmd_sign_file(str(f), "cc")

        # Modify
        f.write_text("version 2")
        result = fi.cmd_verify_file(str(f))
        assert result["status"] == "MODIFIED"

        # Re-sign
        fi.cmd_sign_file(str(f), "cc")
        result = fi.cmd_verify_file(str(f))
        assert result["status"] == "VERIFIED"

        # Chain still intact (re-sign adds entry, doesn't break chain)
        chain = fi.verify_chain()
        assert chain["broken_chain"] == []
