"""Shared document/query preprocessing, without downloaded NLTK resources."""
from dataclasses import asdict, dataclass
from functools import lru_cache
import re
import unicodedata

from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


def clean(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\\(?:text|textrm|textbf|textit|mathrm|mathbf|emph)\s*\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\([A-Za-z]+)', r' \1 ', text)
    text = re.sub(r'[{}$]', ' ', text)
    return ' '.join(text.split())


@dataclass
class LexicalTokenizer:
    stemming: bool = True
    stopwords: bool = True

    def __call__(self, text: str) -> list[str]:
        tokens = re.findall(r'[a-z0-9]+(?:\+\+|(?:[-^][a-z0-9]+)*)', clean(text).lower())
        return [stem(t) if self.stemming else t for t in tokens
                if not self.stopwords or t not in ENGLISH_STOP_WORDS]

    def configuration(self) -> dict:
        return {'version': 1, **asdict(self), 'stemmer': 'NLTK PorterStemmer default mode',
                'stopword_set': 'sklearn ENGLISH_STOP_WORDS', 'title_weight': 1}


@lru_cache(maxsize=100000)
def stem(token: str) -> str:
    return PorterStemmer().stem(token)


def lexical_text(paper: dict) -> str:
    return paper['title'] + '\n' + paper['abstract']


def semantic_text(paper: dict) -> str:
    return f'Title: {clean(paper["title"])}\n\nAbstract: {clean(paper["abstract"])}'
