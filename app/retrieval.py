"""Sparse TF-IDF and cosine retrieval implemented using the standard library."""
from collections import Counter
import math
import re


def tokens(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower().replace("_", " ")
    return re.findall(r"[a-z0-9]+", text)


class Tfidf:
    def __init__(self, mode="word_bigram"):
        self.mode = mode
        self.idf = {}

    def features(self, text):
        words = tokens(text)
        terms = ["w:" + word for word in words]
        if self.mode != "unigram":
            terms += ["b:" + a + " " + b for a, b in zip(words, words[1:])]
        if self.mode == "word_char":
            for word in words:
                padded = "^" + word + "$"
                for n in (2, 3, 4):
                    terms += [f"c{n}:" + padded[i:i+n] for i in range(len(padded)-n+1)]
        return Counter(terms)

    def fit(self, texts):
        df = Counter(term for text in texts for term in self.features(text))
        self.idf = {term: math.log((len(texts)+1)/(count+1))+1 for term, count in df.items()}
        return self

    def transform(self, text):
        vector = {term: (1+math.log(count))*self.idf[term]
                  for term, count in self.features(text).items() if term in self.idf}
        norm = math.sqrt(sum(value*value for value in vector.values()))
        return {term: value/norm for term, value in vector.items()} if norm else {}

    @staticmethod
    def cosine(left, right):
        if len(left) > len(right):
            left, right = right, left
        return sum(value*right.get(term, 0) for term, value in left.items())


def parse_examples(files):
    examples = []
    for file in files:
        if not file["path"].endswith((".http", ".rest", ".txt")):
            continue
        parts = re.split(r"^###\s*", file["content"], flags=re.M)
        for part in parts:
            lines = part.strip().splitlines()
            if not lines:
                continue
            request = next((re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(\S+)", line.strip())
                            for line in lines if re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+", line.strip())), None)
            if not request:
                continue
            title = lines[0] if not re.match(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+", lines[0]) else "Request example"
            identifier, _, caption = title.partition(" | ")
            examples.append({"id": identifier if caption else f"EX-{len(examples)+1:02d}",
                             "title": caption or title, "method": request[1], "url": request[2],
                             "text": part.strip(), "file": file["path"]})
    ids = [row["id"] for row in examples]
    if len(ids) != len(set(ids)):
        raise ValueError("Usage example IDs must be unique across files.")
    return examples


class ExampleIndex:
    def __init__(self, examples, mode="word_bigram"):
        self.examples = examples
        self.vectorizer = Tfidf(mode).fit([row["text"] for row in examples])
        self.vectors = [self.vectorizer.transform(row["text"]) for row in examples]

    def search(self, query, limit=3):
        vector = self.vectorizer.transform(query)
        ranking = sorted(enumerate(self.vectors), key=lambda pair: -self.vectorizer.cosine(vector, pair[1]))
        return [{**self.examples[i], "similarity": round(self.vectorizer.cosine(vector, value), 4)}
                for i, value in ranking[:limit] if self.vectorizer.cosine(vector, value) > 0]
