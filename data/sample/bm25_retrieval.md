# BM25 Sparse Retrieval

BM25 (Best Matching 25) is a ranking function used in information retrieval to score the relevance of documents to a query. It is a probabilistic model that improves on earlier TF-IDF weighting schemes by accounting for document length and term saturation. BM25 remains one of the strongest baselines for text retrieval and is widely used in production search systems.

## The BM25 Formula

Given a query Q with terms q1, q2, ..., qn and a document D, the BM25 score is:

```
BM25(D, Q) = Σ IDF(q) * (tf(q, D) * (k1 + 1)) / (tf(q, D) + k1 * (1 - b + b * |D| / avgdl))
```

Where:
- `tf(q, D)` is the frequency of term q in document D.
- `IDF(q)` is the inverse document frequency of term q across the corpus.
- `|D|` is the length of document D in tokens.
- `avgdl` is the average document length across the corpus.
- `k1` controls term frequency saturation (typically 1.2–2.0).
- `b` controls length normalization (typically 0.75).

## Key Properties

**Term frequency saturation:** Unlike TF-IDF, BM25's term frequency contribution is bounded. A word appearing 100 times in a document does not score 100× higher than one appearing once. The k1 parameter controls where this saturation kicks in.

**Length normalization:** Longer documents naturally contain more term occurrences. BM25 normalizes for document length using the b parameter, so short documents that match a query well are not penalized relative to long documents.

**Inverse document frequency:** Terms that appear in many documents (common words like "the" or "is") receive a low IDF score. Terms that are rare across the corpus but present in a document receive a high IDF score, signalling greater relevance.

## Strengths of BM25

- **Exact match:** BM25 rewards exact lexical overlap. When a user queries a technical term, abbreviation, or product name, BM25 retrieves documents containing that exact term reliably.
- **Efficiency:** BM25 runs entirely in sparse space. Inverted indexes allow it to skip zero-frequency terms, making retrieval fast even on millions of documents.
- **No model required:** Unlike dense retrieval, BM25 requires no embedding model. It works directly on tokenized text, making it fast to index new documents.
- **Interpretability:** BM25 scores are explainable — each term's contribution to the final score is independently calculable.

## Weaknesses of BM25

- **Vocabulary mismatch:** BM25 cannot match synonyms or paraphrases. A query for "automobile" will not retrieve a document that uses only the word "car".
- **No semantic understanding:** BM25 treats all words as independent tokens with no understanding of meaning, context, or relationships.
- **Requires exact term presence:** If the query term does not appear in a document at all, that document scores zero, regardless of semantic relevance.

## BM25 in Hybrid Retrieval

BM25 and dense vector search are complementary: BM25 excels at exact keyword matching while dense search captures semantic similarity. In a hybrid RAG system, both methods are run in parallel and their result lists are merged using a fusion algorithm.

**Reciprocal Rank Fusion (RRF)** is the most common fusion method:

```
RRF_score(doc) = Σ 1 / (k + rank(doc, method))
```

Where k is a constant (typically 60) that reduces the impact of very high-ranked results from a single method. RRF has been shown to be surprisingly robust and typically outperforms weighted score combinations because it is invariant to the arbitrary scaling of individual retrieval scores.

## BM25 Index Management

A BM25 index is built by:
1. Tokenizing all documents in the corpus.
2. Computing term frequencies per document.
3. Computing IDF scores across the corpus.

When new documents are ingested, the index must be updated. Incremental updates are possible but require recalculating IDF values as the corpus changes, which can change the relative ranking of existing documents.
