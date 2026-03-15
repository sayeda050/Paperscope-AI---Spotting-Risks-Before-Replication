from __future__ import annotations

import re

from rest_framework import serializers


PDF_MAX_BYTES = 50 * 1024 * 1024
ARXIV_ID_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(?P<id>\d{4}\.\d{4,5})(?:v\d+)?", re.I)


def validate_uploaded_pdf(uploaded_file):
    if not uploaded_file:
        raise serializers.ValidationError('PDF file is required.')

    name = getattr(uploaded_file, 'name', '') or ''
    content_type = getattr(uploaded_file, 'content_type', '') or ''

    if not name.lower().endswith('.pdf') and content_type != 'application/pdf':
        raise serializers.ValidationError('Only PDF files are allowed.')

    size = getattr(uploaded_file, 'size', 0) or 0
    if size > PDF_MAX_BYTES:
        raise serializers.ValidationError('File size must be 50MB or less.')

    return uploaded_file


def extract_arxiv_id(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        raise serializers.ValidationError('arXiv link or ID is required.')

    match = ARXIV_ID_RE.search(raw)
    if match:
        return match.group('id')

    if re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?', raw):
        return raw.split('v')[0]

    raise serializers.ValidationError('Enter a valid arXiv link or arXiv ID.')
