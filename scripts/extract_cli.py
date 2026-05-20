from __future__ import annotations

#!/usr/bin/env python3
"""CLI to test document extraction without HTTP."""

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.pipeline import run_extraction_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract student profile from a document")
    parser.add_argument("file", type=Path, help="Path to PDF, image, or Excel file")
    parser.add_argument(
        "--document-type",
        default="admission_form",
        help="Document template type (default: admission_form)",
    )
    args = parser.parse_args()

    if not args.file.is_file():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    data = args.file.read_bytes()
    result = run_extraction_pipeline(
        data=data,
        filename=args.file.name,
        content_type=None,
        document_type=args.document_type,
        settings=settings,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
