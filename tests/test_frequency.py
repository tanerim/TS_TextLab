import unittest
from collections import Counter
from unittest.mock import Mock, patch

from ts_tokenizer import tr_lowercase

from app.analysis_service import AnalysisDocument, TokenInfo
from app.main_window import NlpWorker
from app.tokenizer_service import TokenizerResult, TokenizerService


SAMPLE = "Başlangıç iyi oldu umarım devamı gelir #millitakım\nBir kahve alayım tuzsuz olsun 😏"


class FrequencyTests(unittest.TestCase):
    def setUp(self):
        self.service = TokenizerService()

    def test_sample_keeps_all_thirteen_tokens_in_both_modes(self):
        for mode in ("sensitive", "insensitive"):
            with self.subTest(mode=mode):
                result = self.service.frequency(SAMPLE, mode)
                source = SAMPLE if mode == "sensitive" else tr_lowercase(SAMPLE)
                expected = {token: "1" for token in source.split()}
                self.assertEqual(dict(result.rows), expected)
                self.assertEqual(len(result.rows), 13)
                self.assertEqual(result.headers, ["Token", "Count"])
                self.assertEqual(result.copy_text, "\n".join("\t".join(row) for row in result.rows))

    def test_lowercase_is_applied_to_source_before_tokenization(self):
        source = "I İ #MİLLİTAKIM 😏"
        # Classification can change after case conversion. The returned surface
        # must remain exactly as the tokenizer emits it.
        emitted = TokenizerResult("tokenized", ["Token"], [("OUTPUT",)], "OUTPUT")
        for mode in ("sensitive", "insensitive"):
            with self.subTest(mode=mode), patch.object(self.service, "tokenize", return_value=emitted) as tokenize:
                self.assertEqual(self.service.frequency(source, mode).rows, [("OUTPUT", "1")])
                tokenize.assert_called_once_with(
                    source if mode == "sensitive" else tr_lowercase(source), "tokenized"
                )

    def test_turkish_case_variants_and_non_word_units(self):
        source = "ISLAK ıslak İYİ iyi #TAKIM #takım 😏 😏 @TANER https://example.com 123 !"
        for mode in ("sensitive", "insensitive"):
            with self.subTest(mode=mode):
                text = source if mode == "sensitive" else tr_lowercase(source)
                expected = Counter(row[0] for row in self.service.tokenize(text).rows)
                actual = {token: int(count) for token, count in self.service.frequency(source, mode).rows}
                self.assertEqual(actual, expected)
                self.assertEqual(actual["😏"], 2)
                self.assertIn("!", actual)
                if mode == "insensitive":
                    self.assertEqual(actual["ıslak"], 2)
                    self.assertEqual(actual["iyi"], 2)
                    self.assertEqual(actual["#takım"], 2)

    def test_worker_counts_source_even_with_a_cached_document(self):
        cached = AnalysisDocument([TokenInfo("stale", 1, "Valid_Word")])
        for mode in ("sensitive", "insensitive"):
            with self.subTest(mode=mode):
                worker = NlpWorker(
                    "frequency", SAMPLE, "tokenized", "full", mode,
                    2, set(), "", 3, cached, self.service, Mock(),
                )
                results, errors = [], []
                worker.signals.finished.connect(results.append)
                worker.signals.failed.connect(errors.append)
                worker.run()
                self.assertEqual(errors, [])
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].rows, self.service.frequency(SAMPLE, mode).rows)
                self.assertIs(results[0].document, cached)


if __name__ == "__main__":
    unittest.main()
