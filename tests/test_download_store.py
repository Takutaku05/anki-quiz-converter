import unittest
from datetime import UTC, datetime, timedelta

from src.download_store import InMemoryDownloadStore


class DownloadStoreTests(unittest.TestCase):
    def setUp(self):
        self.current = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
        self.store = InMemoryDownloadStore(
            expires_in_seconds=600,
            max_entries=2,
            now=lambda: self.current,
        )

    def test_put_and_get_roundtrip(self):
        token, expires_at = self.store.put(b"apkg-bytes", "deck.apkg", "application/octet-stream")

        self.assertEqual(expires_at, self.current + timedelta(seconds=600))
        stored = self.store.get(token)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.content, b"apkg-bytes")
        self.assertEqual(stored.filename, "deck.apkg")
        self.assertEqual(stored.content_type, "application/octet-stream")

    def test_get_unknown_token_returns_none(self):
        self.assertIsNone(self.store.get("missing"))

    def test_expired_entry_is_removed(self):
        token, _ = self.store.put(b"apkg-bytes", "deck.apkg", "application/octet-stream")

        self.current += timedelta(seconds=601)
        self.assertIsNone(self.store.get(token))

    def test_entry_remains_available_until_expiry(self):
        token, _ = self.store.put(b"apkg-bytes", "deck.apkg", "application/octet-stream")

        self.current += timedelta(seconds=599)
        self.assertIsNotNone(self.store.get(token))
        self.assertIsNotNone(self.store.get(token))

    def test_oldest_entry_is_evicted_when_full(self):
        first, _ = self.store.put(b"1", "a.apkg", "application/octet-stream")
        second, _ = self.store.put(b"2", "b.apkg", "application/octet-stream")
        third, _ = self.store.put(b"3", "c.apkg", "application/octet-stream")

        self.assertIsNone(self.store.get(first))
        self.assertIsNotNone(self.store.get(second))
        self.assertIsNotNone(self.store.get(third))

    def test_tokens_are_unique(self):
        tokens = {self.store.put(b"x", "a.apkg", "application/octet-stream")[0] for _ in range(2)}
        self.assertEqual(len(tokens), 2)


if __name__ == "__main__":
    unittest.main()
