"""Universal document metadata extraction for various document types.

Supports:
- Academic papers (논문)
- Corporate documents (회사 문서)
- Presentations (PPT)
- Meeting minutes (회의록)
- Legal documents (법적 문서, 계약서)
- Insurance policies (보험약관)
- General documents
"""

import re
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Document type classification."""

    PAPER = "paper"              # 학술 논문
    CORPORATE = "corporate"      # 회사 문서
    PRESENTATION = "presentation"  # PPT, 슬라이드
    MEETING = "meeting"          # 회의록
    LEGAL = "legal"              # 법적 문서, 계약서
    INSURANCE = "insurance"      # 보험약관
    REPORT = "report"            # 보고서
    MANUAL = "manual"            # 매뉴얼, 가이드
    GENERAL = "general"          # 일반 문서


class DocumentMetadata(BaseModel):
    """Universal document metadata model."""

    # Common fields (모든 문서 공통)
    doc_type: DocumentType = Field(default=DocumentType.GENERAL, description="문서 유형")
    title: Optional[str] = Field(default=None, description="문서 제목")
    date: Optional[str] = Field(default=None, description="작성일/발행일")

    # Author/Source info
    author: Optional[str] = Field(default=None, description="작성자 (개인)")
    authors: Optional[str] = Field(default=None, description="작성자들 (복수)")
    organization: Optional[str] = Field(default=None, description="조직/기관/회사")
    department: Optional[str] = Field(default=None, description="부서")

    # Paper-specific (논문)
    journal: Optional[str] = Field(default=None, description="저널/학회")
    doi: Optional[str] = Field(default=None, description="DOI")
    abstract: Optional[str] = Field(default=None, description="초록")
    keywords: Optional[list[str]] = Field(default=None, description="키워드")

    # Corporate/Legal
    version: Optional[str] = Field(default=None, description="버전")
    classification: Optional[str] = Field(default=None, description="보안등급/분류")
    contract_parties: Optional[list[str]] = Field(default=None, description="계약 당사자")
    effective_date: Optional[str] = Field(default=None, description="시행일/효력발생일")

    # Meeting
    attendees: Optional[list[str]] = Field(default=None, description="참석자")
    agenda: Optional[list[str]] = Field(default=None, description="안건")

    # Insurance
    product_name: Optional[str] = Field(default=None, description="상품명")
    insurer: Optional[str] = Field(default=None, description="보험사")

    # Section info
    sections: Optional[list[str]] = Field(default=None, description="섹션/조항 목록")


# Document type detection patterns
DOCUMENT_PATTERNS = {
    DocumentType.PAPER: [
        r"(?i)abstract",
        r"(?i)introduction",
        r"(?i)references",
        r"(?i)doi:",
        r"(?i)journal",
        r"(?i)proceedings",
        r"(?i)arxiv",
        r"(?i)et\s+al\.",
        r"(?i)university",
        r"(?i)institute",
    ],
    DocumentType.MEETING: [
        r"(?i)회의록",
        r"(?i)meeting\s+minutes",
        r"(?i)참석자",
        r"(?i)attendees",
        r"(?i)안건",
        r"(?i)agenda",
        r"(?i)결정사항",
        r"(?i)action\s+items",
    ],
    DocumentType.LEGAL: [
        r"(?i)계약서",
        r"(?i)contract",
        r"(?i)agreement",
        r"(?i)약정서",
        r"(?i)제\s*\d+\s*조",
        r"(?i)article\s+\d+",
        r"(?i)갑.*을",
        r"(?i)party\s+a.*party\s+b",
        r"(?i)hereby",
        r"(?i)법률",
    ],
    DocumentType.INSURANCE: [
        r"(?i)보험약관",
        r"(?i)insurance\s+policy",
        r"(?i)보험금",
        r"(?i)피보험자",
        r"(?i)보장내용",
        r"(?i)coverage",
        r"(?i)premium",
        r"(?i)보험료",
    ],
    DocumentType.PRESENTATION: [
        r"(?i)slide\s+\d+",
        r"(?i)슬라이드",
        r"(?i)발표자료",
        r"(?i)presentation",
    ],
    DocumentType.CORPORATE: [
        r"(?i)confidential",
        r"(?i)internal\s+use",
        r"(?i)대외비",
        r"(?i)사내문서",
        r"(?i)업무\s*보고",
        r"(?i)품의서",
        r"(?i)결재",
    ],
    DocumentType.REPORT: [
        r"(?i)보고서",
        r"(?i)report",
        r"(?i)분석\s*결과",
        r"(?i)executive\s+summary",
        r"(?i)findings",
    ],
    DocumentType.MANUAL: [
        r"(?i)매뉴얼",
        r"(?i)manual",
        r"(?i)guide",
        r"(?i)가이드",
        r"(?i)사용\s*방법",
        r"(?i)how\s+to",
    ],
}


def detect_document_type(text: str, file_name: str = "") -> DocumentType:
    """
    Detect document type from text content and file name.

    Args:
        text: Document text content (first few pages)
        file_name: Original file name

    Returns:
        Detected DocumentType
    """
    text_lower = text.lower()
    file_lower = file_name.lower()

    # Score each document type
    scores = {doc_type: 0 for doc_type in DocumentType}

    for doc_type, patterns in DOCUMENT_PATTERNS.items():
        for pattern in patterns:
            matches = len(re.findall(pattern, text[:5000]))  # Check first 5000 chars
            scores[doc_type] += matches

    # File name hints
    if any(ext in file_lower for ext in [".ppt", ".pptx", "slide", "presentation"]):
        scores[DocumentType.PRESENTATION] += 5
    if any(word in file_lower for word in ["contract", "계약", "agreement", "약정"]):
        scores[DocumentType.LEGAL] += 5
    if any(word in file_lower for word in ["meeting", "회의", "minutes"]):
        scores[DocumentType.MEETING] += 5
    if any(word in file_lower for word in ["insurance", "보험", "약관"]):
        scores[DocumentType.INSURANCE] += 5
    if any(word in file_lower for word in ["paper", "논문", "research"]):
        scores[DocumentType.PAPER] += 5

    # Get highest scoring type
    max_type = max(scores, key=scores.get)

    # Return GENERAL if no strong signal
    if scores[max_type] < 2:
        return DocumentType.GENERAL

    return max_type


def extract_universal_metadata(
    text: str,
    file_name: str = "",
    doc_type: Optional[DocumentType] = None,
) -> dict[str, Any]:
    """
    Extract metadata based on document type.

    Args:
        text: Document text content
        file_name: Original file name
        doc_type: Override document type detection

    Returns:
        Extracted metadata dictionary
    """
    # Detect document type if not provided
    if doc_type is None:
        doc_type = detect_document_type(text, file_name)

    # Base metadata
    metadata = {"doc_type": doc_type.value}

    # Extract based on document type
    if doc_type == DocumentType.PAPER:
        metadata.update(_extract_paper_metadata(text))
    elif doc_type == DocumentType.MEETING:
        metadata.update(_extract_meeting_metadata(text))
    elif doc_type == DocumentType.LEGAL:
        metadata.update(_extract_legal_metadata(text))
    elif doc_type == DocumentType.INSURANCE:
        metadata.update(_extract_insurance_metadata(text))
    elif doc_type == DocumentType.CORPORATE:
        metadata.update(_extract_corporate_metadata(text))
    elif doc_type == DocumentType.PRESENTATION:
        metadata.update(_extract_presentation_metadata(text))
    else:
        metadata.update(_extract_general_metadata(text))

    # Clean up empty values
    metadata = {k: v for k, v in metadata.items() if v is not None and v != ""}

    return metadata


def _extract_paper_metadata(text: str) -> dict[str, Any]:
    """Extract academic paper metadata."""
    metadata = {}
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        return metadata

    # Title: Usually first line (may span multiple lines)
    title_lines = []
    for i, line in enumerate(lines[:5]):
        # Stop if we hit author-like content or abstract
        if re.search(r"(?i)^(abstract|university|department|\d{4})", line):
            break
        if len(line) > 10:  # Skip very short lines
            title_lines.append(line)
        if len(" ".join(title_lines)) > 150:  # Title shouldn't be too long
            break

    if title_lines:
        metadata["title"] = " ".join(title_lines[:2])  # Max 2 lines for title

    # Authors: Look for names between title and abstract
    author_section = []
    in_author_section = False

    for line in lines:
        line_lower = line.lower()

        # Start after title-like content
        if not in_author_section and len(line) > 20:
            in_author_section = True
            continue

        # Stop at abstract/introduction
        if re.match(r"(?i)^(abstract|introduction|keywords)", line_lower):
            break

        # Skip institutional lines for author extraction
        if in_author_section:
            # Check if line looks like author names (contains names, not just org)
            if re.search(r"(?i)(university|institute|department|college|school|@|email)", line):
                # This is organization info, extract it
                if "organization" not in metadata:
                    org_match = re.search(r"(?i)([\w\s]+(?:university|institute|college|school|center)[\w\s]*)", line)
                    if org_match:
                        metadata["organization"] = org_match.group(1).strip()
            elif re.search(r"[A-Z][a-z]+\s+[A-Z]", line) or re.search(r"[\uAC00-\uD7AF]{2,}", line):
                # Looks like names (English pattern or Korean)
                author_section.append(line)

    if author_section:
        # Clean and join authors
        authors = []
        for author_line in author_section[:3]:  # Max 3 lines
            # Remove symbols and clean
            cleaned = re.sub(r"[†‡*∗\d,]+$", "", author_line).strip()
            cleaned = re.sub(r"\s+", " ", cleaned)
            if cleaned and len(cleaned) > 2:
                authors.append(cleaned)

        if authors:
            metadata["authors"] = ", ".join(authors)

    # Date: Look for year pattern
    date_match = re.search(r"\b(19|20)\d{2}\b", text[:2000])
    if date_match:
        metadata["date"] = date_match.group()

    # DOI
    doi_match = re.search(r"10\.\d{4,}/[^\s]+", text)
    if doi_match:
        metadata["doi"] = doi_match.group()

    # Journal/Conference
    journal_patterns = [
        r"(?i)(?:published\s+(?:in|by)|proceedings\s+of|journal\s+of)\s+([^\n]+)",
        r"(?i)([\w\s]+(?:conference|journal|symposium|workshop|proceedings)[\w\s]*)",
    ]
    for pattern in journal_patterns:
        match = re.search(pattern, text[:3000])
        if match:
            metadata["journal"] = match.group(1).strip()[:100]
            break

    # Abstract
    abstract = _extract_abstract(text)
    if abstract:
        metadata["abstract"] = abstract

    # Keywords
    keywords = _extract_keywords(text)
    if keywords:
        metadata["keywords"] = keywords

    return metadata


def _extract_meeting_metadata(text: str) -> dict[str, Any]:
    """Extract meeting minutes metadata."""
    metadata = {}
    text_lower = text.lower()

    # Title
    title_match = re.search(r"(?i)(?:회의록|meeting\s+minutes?)[:\s]*([^\n]+)", text)
    if title_match:
        metadata["title"] = title_match.group(1).strip()
    else:
        # First line might be title
        first_line = text.split("\n")[0].strip()
        if first_line:
            metadata["title"] = first_line[:100]

    # Date
    date_patterns = [
        r"(?:일시|date|날짜)[:\s]*([^\n]+)",
        r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})",
        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["date"] = match.group(1).strip()
            break

    # Attendees
    attendees_match = re.search(
        r"(?i)(?:참석자|attendees?|참가자)[:\s]*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*(?:안건|agenda|목적|purpose|\d+\.|•))",
        text
    )
    if attendees_match:
        attendees_text = attendees_match.group(1)
        attendees = re.split(r"[,;·•\n]", attendees_text)
        metadata["attendees"] = [a.strip() for a in attendees if a.strip() and len(a.strip()) > 1]

    # Agenda
    agenda_match = re.search(
        r"(?i)(?:안건|agenda)[:\s]*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*(?:결정|decision|내용|content|본문))",
        text
    )
    if agenda_match:
        agenda_text = agenda_match.group(1)
        agenda = re.split(r"[\n•\-]", agenda_text)
        metadata["agenda"] = [a.strip() for a in agenda if a.strip() and len(a.strip()) > 3]

    return metadata


def _extract_legal_metadata(text: str) -> dict[str, Any]:
    """Extract legal document metadata."""
    metadata = {}

    # Title/Contract type
    title_patterns = [
        r"^([^\n]+(?:계약서|약정서|합의서|contract|agreement))",
        r"(?i)(?:제목|title)[:\s]*([^\n]+)",
    ]
    for pattern in title_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            metadata["title"] = match.group(1).strip()
            break

    # Contract parties
    parties = []

    # Korean pattern: 갑, 을
    gap_match = re.search(r"[\"']?갑[\"']?\s*[:\s은는]?\s*([^\n,()]+)", text)
    if gap_match:
        parties.append(f"갑: {gap_match.group(1).strip()}")

    eul_match = re.search(r"[\"']?을[\"']?\s*[:\s은는]?\s*([^\n,()]+)", text)
    if eul_match:
        parties.append(f"을: {eul_match.group(1).strip()}")

    # English pattern
    party_match = re.search(r"(?i)(?:between|party\s+[ab])[:\s]*([^\n]+)", text)
    if party_match and not parties:
        parties.append(party_match.group(1).strip())

    if parties:
        metadata["contract_parties"] = parties

    # Date
    date_patterns = [
        r"(?:체결일|계약일|작성일|effective\s+date)[:\s]*([^\n]+)",
        r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})",
        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["date"] = match.group(1).strip()
            break

    # Effective date
    eff_match = re.search(r"(?i)(?:시행일|효력\s*발생|effective)[:\s]*([^\n]+)", text)
    if eff_match:
        metadata["effective_date"] = eff_match.group(1).strip()

    # Sections/Articles
    sections = re.findall(r"(?:제\s*(\d+)\s*조|article\s+(\d+))[^\n]*", text, re.IGNORECASE)
    if sections:
        metadata["sections"] = [f"제{s[0] or s[1]}조" for s in sections[:10]]

    return metadata


def _extract_insurance_metadata(text: str) -> dict[str, Any]:
    """Extract insurance policy metadata."""
    metadata = {}

    # Product name
    product_patterns = [
        r"(?i)(?:상품명|product\s+name)[:\s]*([^\n]+)",
        r"([^\n]+(?:보험|insurance))",
    ]
    for pattern in product_patterns:
        match = re.search(pattern, text[:1000])
        if match:
            metadata["product_name"] = match.group(1).strip()[:100]
            break

    # Insurer
    insurer_patterns = [
        r"(?i)(?:보험사|보험회사|insurer)[:\s]*([^\n]+)",
        r"([^\n]+(?:생명|화재|해상|손해)보험)",
    ]
    for pattern in insurer_patterns:
        match = re.search(pattern, text[:2000])
        if match:
            metadata["insurer"] = match.group(1).strip()[:100]
            break

    # Effective date
    date_patterns = [
        r"(?i)(?:시행일|효력\s*발생일?|effective)[:\s]*([^\n]+)",
        r"(?i)(?:\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["effective_date"] = match.group(1).strip() if match.lastindex else match.group().strip()
            break

    # Version
    version_match = re.search(r"(?i)(?:버전|version|개정)[:\s]*([^\n]+)", text)
    if version_match:
        metadata["version"] = version_match.group(1).strip()[:50]

    # Title
    title_match = re.search(r"^([^\n]+약관)", text, re.MULTILINE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    return metadata


def _extract_corporate_metadata(text: str) -> dict[str, Any]:
    """Extract corporate document metadata."""
    metadata = {}

    # Title
    first_lines = [l.strip() for l in text.split("\n")[:5] if l.strip()]
    if first_lines:
        metadata["title"] = first_lines[0][:150]

    # Author/Writer
    author_patterns = [
        r"(?i)(?:작성자|author|writer|담당자)[:\s]*([^\n]+)",
        r"(?i)(?:기안자|기안)[:\s]*([^\n]+)",
    ]
    for pattern in author_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["author"] = match.group(1).strip()[:100]
            break

    # Department
    dept_match = re.search(r"(?i)(?:부서|department|팀)[:\s]*([^\n]+)", text)
    if dept_match:
        metadata["department"] = dept_match.group(1).strip()[:100]

    # Date
    date_patterns = [
        r"(?i)(?:작성일|date|일자)[:\s]*([^\n]+)",
        r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["date"] = match.group(1).strip()
            break

    # Version
    version_match = re.search(r"(?i)(?:버전|version|v)[\s.:]*(\d+[\d.]*)", text)
    if version_match:
        metadata["version"] = version_match.group(1)

    # Classification
    class_patterns = [
        r"(?i)(confidential|대외비|internal\s+use|사내\s*한정|극비|비밀)",
    ]
    for pattern in class_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["classification"] = match.group(1).strip()
            break

    # Organization
    org_match = re.search(r"(?i)(?:회사|company|기업)[:\s]*([^\n]+)", text)
    if org_match:
        metadata["organization"] = org_match.group(1).strip()[:100]

    return metadata


def _extract_presentation_metadata(text: str) -> dict[str, Any]:
    """Extract presentation/PPT metadata."""
    metadata = {}

    # Title (usually first significant line)
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
    if lines:
        metadata["title"] = lines[0][:200]

    # Author/Presenter
    author_patterns = [
        r"(?i)(?:발표자|presenter|작성자|author)[:\s]*([^\n]+)",
        r"(?i)(?:by|prepared\s+by)[:\s]*([^\n]+)",
    ]
    for pattern in author_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["author"] = match.group(1).strip()[:100]
            break

    # Date
    date_match = re.search(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})", text)
    if date_match:
        metadata["date"] = date_match.group(1)

    # Organization/Company
    org_match = re.search(r"(?i)(?:회사|company|팀|team|부서)[:\s]*([^\n]+)", text)
    if org_match:
        metadata["organization"] = org_match.group(1).strip()[:100]

    return metadata


def _extract_general_metadata(text: str) -> dict[str, Any]:
    """Extract general document metadata."""
    metadata = {}

    # Title
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        metadata["title"] = lines[0][:200]

    # Date
    date_patterns = [
        r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})",
        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text[:2000])
        if match:
            metadata["date"] = match.group(1)
            break

    # Author (generic)
    author_match = re.search(r"(?i)(?:작성자|author|by)[:\s]*([^\n]+)", text)
    if author_match:
        metadata["author"] = author_match.group(1).strip()[:100]

    return metadata


def _extract_abstract(text: str) -> Optional[str]:
    """Extract abstract from document."""
    patterns = [
        r"(?i)abstract[:\s]*\n?(.*?)(?=\n\s*(?:introduction|keywords|1\.|I\.))",
        r"(?i)abstract[:\s]*\n?(.*?)(?=\n\n)",
        r"(?i)요약[:\s]*\n?(.*?)(?=\n\s*(?:서론|목차|1\.))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            if len(abstract) > 50:
                return abstract[:2000]  # Limit length

    return None


def _extract_keywords(text: str) -> Optional[list[str]]:
    """Extract keywords from document."""
    patterns = [
        r"(?i)keywords?[:\s]*\n?(.*?)(?=\n\s*(?:introduction|1\.|I\.))",
        r"(?i)키워드[:\s]*\n?(.*?)(?=\n\s*(?:서론|목차|1\.))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            keywords_text = match.group(1).strip()
            keywords = re.split(r"[;,·•]|\s{2,}", keywords_text)
            result = [k.strip() for k in keywords if k.strip() and 2 < len(k.strip()) < 50]
            if result:
                return result[:10]  # Max 10 keywords

    return None


def format_citation(metadata: dict[str, Any], ref_id: str = "") -> str:
    """
    Format citation string based on document type.

    Args:
        metadata: Document metadata
        ref_id: Reference ID

    Returns:
        Formatted citation string
    """
    doc_type = metadata.get("doc_type", "general")

    if doc_type == DocumentType.PAPER.value:
        # Academic citation: Author et al., "Title", Journal, Year
        parts = []

        if metadata.get("authors"):
            # Get first author's last name
            authors = metadata["authors"]
            first_author = authors.split(",")[0].strip()
            last_name = first_author.split()[-1] if first_author else "Unknown"
            parts.append(f"{last_name} et al.")

        if metadata.get("title"):
            title = metadata["title"][:80]
            parts.append(f'"{title}"')

        if metadata.get("journal"):
            parts.append(metadata["journal"][:50])

        if metadata.get("date"):
            parts.append(f"({metadata['date']})")

        return ", ".join(parts) if parts else "Unknown Paper"

    elif doc_type == DocumentType.LEGAL.value:
        # Legal citation: Contract Title, Parties, Date
        parts = []

        if metadata.get("title"):
            parts.append(metadata["title"][:80])

        if metadata.get("contract_parties"):
            parties = metadata["contract_parties"][:2]
            parts.append(" & ".join(parties))

        if metadata.get("date"):
            parts.append(metadata["date"])

        return ", ".join(parts) if parts else "Legal Document"

    elif doc_type == DocumentType.MEETING.value:
        # Meeting citation: Meeting Title, Date, Attendees count
        parts = []

        if metadata.get("title"):
            parts.append(metadata["title"][:80])

        if metadata.get("date"):
            parts.append(metadata["date"])

        if metadata.get("attendees"):
            parts.append(f"참석자 {len(metadata['attendees'])}명")

        return ", ".join(parts) if parts else "회의록"

    elif doc_type == DocumentType.INSURANCE.value:
        # Insurance citation: Product Name, Insurer, Effective Date
        parts = []

        if metadata.get("product_name"):
            parts.append(metadata["product_name"][:80])

        if metadata.get("insurer"):
            parts.append(metadata["insurer"])

        if metadata.get("effective_date"):
            parts.append(f"시행일: {metadata['effective_date']}")

        return ", ".join(parts) if parts else "보험약관"

    elif doc_type == DocumentType.CORPORATE.value:
        # Corporate citation: Title, Department, Author, Date
        parts = []

        if metadata.get("title"):
            parts.append(metadata["title"][:80])

        if metadata.get("department"):
            parts.append(metadata["department"])

        if metadata.get("author"):
            parts.append(metadata["author"])

        if metadata.get("date"):
            parts.append(metadata["date"])

        return ", ".join(parts) if parts else "사내문서"

    else:
        # General citation
        parts = []

        if metadata.get("title"):
            parts.append(metadata["title"][:100])

        if metadata.get("author") or metadata.get("authors"):
            author = metadata.get("author") or metadata.get("authors", "").split(",")[0]
            parts.append(author[:50])

        if metadata.get("date"):
            parts.append(metadata["date"])

        return ", ".join(parts) if parts else "문서"
