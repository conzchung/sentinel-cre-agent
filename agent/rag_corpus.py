"""Load and validate the illustrative analyst-commentary corpus (JSONL)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

REQUIRED_FIELDS = ("id", "title", "text", "source", "as_of", "theme")

# agent/rag_corpus.py -> repo root is one level up; corpus lives in data/
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "research_corpus.jsonl"


def load_corpus(path: Optional[Path] = None) -> List[dict]:
    """Parse the JSONL corpus and validate every note.

    Raises ValueError if a note is missing a required field or has empty text.
    """
    corpus_path = Path(path) if path is not None else _DEFAULT_PATH
    notes: List[dict] = []
    with corpus_path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            note = json.loads(line)
            for field in REQUIRED_FIELDS:
                if field not in note:
                    raise ValueError(
                        f"Note on line {lineno} missing required field '{field}'."
                    )
            if not str(note["text"]).strip():
                raise ValueError(f"Note '{note.get('id')}' has empty text.")
            notes.append(note)
    return notes
