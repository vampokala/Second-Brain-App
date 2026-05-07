"""Reference-based and reference-free generation metrics."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Sequence

from rouge_score import rouge_scorer


class GenerationMetrics:
    """ROUGE / BLEU / BERTScore wrappers plus simple faithfulness heuristics."""

    def __init__(self) -> None:
        self._rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)

    def rouge_scores(self, hypothesis: str, reference: str) -> Dict[str, float]:
        if not (hypothesis or "").strip() or not (reference or "").strip():
            return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
        scores = self._rouge.score(reference, hypothesis)
        return {
            "rouge1": float(scores["rouge1"].fmeasure),
            "rouge2": float(scores["rouge2"].fmeasure),
            "rougeL": float(scores["rougeL"].fmeasure),
        }

    @staticmethod
    def bleu_score(hypothesis: str, reference: str) -> float:
        try:
            from sacrebleu.metrics import BLEU  # type: ignore[import-untyped]
        except ImportError:
            return 0.0
        if not (hypothesis or "").strip() or not (reference or "").strip():
            return 0.0
        bleu = BLEU(effective_order=True)
        s = bleu.sentence_score(hypothesis, [reference])
        return float(s.score) / 100.0

    @staticmethod
    def bert_score_f1(hypothesis: str, reference: str) -> float:
        try:
            from bert_score import score as bert_score  # type: ignore[import-untyped]
        except ImportError:
            return 0.0
        if not (hypothesis or "").strip() or not (reference or "").strip():
            return 0.0
        _p, _r, f1 = bert_score([hypothesis], [reference], lang="en", verbose=False)
        f1_val = f1[0]
        return float(f1_val.item() if hasattr(f1_val, "item") else f1_val)

    @staticmethod
    def faithfulness_score(response: str, source_docs: Sequence[str]) -> float:
        """Token overlap of response with union of sources (0..1)."""
        text = (response or "").lower()
        r_tokens = {t for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2}
        if not r_tokens:
            return 0.0
        corpus = " ".join(source_docs).lower()
        s_tokens = {t for t in re.findall(r"[a-z0-9]+", corpus) if len(t) > 2}
        if not s_tokens:
            return 0.0
        return len(r_tokens & s_tokens) / max(len(r_tokens), 1)

    def evaluate_generation(
        self,
        response: str,
        query: str,
        source_docs: Sequence[str],
        reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "faithfulness": self.faithfulness_score(response, source_docs),
            "relevance_to_query": self.faithfulness_score(response, [query]),
        }
        if reference:
            out["rouge"] = self.rouge_scores(response, reference)
            out["bleu"] = self.bleu_score(response, reference)
            out["bertscore_f1"] = self.bert_score_f1(response, reference)
        return out
