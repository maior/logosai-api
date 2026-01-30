"""Paper metadata extraction for academic documents."""

import re
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PaperMetadata(BaseModel):
    """Paper metadata model."""

    title: Optional[str] = Field(default=None, description="The title of the paper")
    authors: Optional[str] = Field(
        default=None, description="The authors of the paper, separated by commas"
    )
    journal: Optional[str] = Field(
        default=None, description="The name of the journal or conference"
    )
    publication_date: Optional[str] = Field(
        default=None, description="The publication date of the paper"
    )
    doi: Optional[str] = Field(
        default=None, description="The DOI of the paper, if available"
    )
    abstract: Optional[str] = Field(
        default=None, description="The abstract of the paper"
    )


def extract_paper_metadata(text: str) -> dict[str, Any]:
    """
    Extract paper metadata using regex patterns.

    Args:
        text: First page text of the paper

    Returns:
        Extracted metadata dictionary
    """
    metadata = {}

    # Split and clean lines
    lines = text.split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    if not lines:
        return metadata

    # First non-empty line is usually the title
    metadata["title"] = lines[0]

    # Initialize tracking variables
    author_lines = []
    date_found = False
    journal_found = False

    # Patterns
    date_pattern = re.compile(r"\b(19|20)\d{2}\b")
    journal_keywords = ["journal", "conference", "proceedings", "symposium", "workshop"]
    doi_pattern = re.compile(r"10\.\d{4,}/[^\s]+")

    # Iterate over lines
    for line in lines[1:]:
        lower_line = line.lower()

        # Stop at abstract/introduction
        if re.match(r"^(abstract|introduction)", lower_line):
            break

        # Check for journal
        if any(keyword in lower_line for keyword in journal_keywords):
            if not journal_found:
                metadata["journal"] = line
                journal_found = True
        # Check for date
        elif date_pattern.search(line):
            if not date_found:
                metadata["publication_date"] = date_pattern.search(line).group()
                date_found = True
        else:
            author_lines.append(line)

    # Assign authors
    if author_lines:
        metadata["authors"] = ", ".join(author_lines[:5])  # Limit to 5 lines

    # Extract DOI
    doi_match = doi_pattern.search(text)
    if doi_match:
        metadata["doi"] = doi_match.group()

    # Secondary checks
    if not date_found or not journal_found:
        for line in lines:
            lower_line = line.lower()
            if not date_found and date_pattern.search(line):
                metadata["publication_date"] = date_pattern.search(line).group()
                date_found = True
            if not journal_found and any(
                keyword in lower_line for keyword in journal_keywords
            ):
                metadata["journal"] = line
                journal_found = True
            if date_found and journal_found:
                break

    return metadata


async def extract_paper_metadata_llm(
    text: str,
    llm: Any,
) -> dict[str, Any]:
    """
    Extract paper metadata using LLM.

    Args:
        text: First page text of the paper
        llm: LangChain LLM instance

    Returns:
        Extracted metadata dictionary
    """
    try:
        from langchain_core.output_parsers import PydanticOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        # Create output parser
        output_parser = PydanticOutputParser(pydantic_object=PaperMetadata)

        # Create prompt template
        template = """
Extract the following information from the given academic paper text.
If a piece of information is not present, leave it as null.

{format_instructions}

Text: {text}

Extracted information:
"""

        prompt = ChatPromptTemplate.from_template(template)

        # Format the prompt
        messages = prompt.format_messages(
            format_instructions=output_parser.get_format_instructions(),
            text=text[:3000],  # Limit text length
        )

        # Get LLM response
        response = await llm.ainvoke(messages)

        # Parse response
        try:
            parsed_metadata = output_parser.parse(response.content)
            return parsed_metadata.model_dump()
        except Exception as parse_error:
            logger.warning(f"Failed to parse LLM response: {parse_error}")
            # Fallback to regex extraction
            return extract_paper_metadata(text)

    except ImportError:
        logger.warning("LangChain not available, using regex extraction")
        return extract_paper_metadata(text)
    except Exception as e:
        logger.error(f"Error extracting metadata with LLM: {e}")
        return extract_paper_metadata(text)


def extract_abstract(text: str) -> Optional[str]:
    """
    Extract abstract from paper text.

    Args:
        text: Paper text

    Returns:
        Extracted abstract or None
    """
    try:
        # Common abstract patterns
        patterns = [
            r"(?i)abstract[:\s]*\n?(.*?)(?=\n\s*(?:introduction|keywords|1\.|I\.))",
            r"(?i)abstract[:\s]*\n?(.*?)(?=\n\n)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                if len(abstract) > 50:  # Minimum length check
                    return abstract

        return None

    except Exception as e:
        logger.error(f"Abstract extraction error: {e}")
        return None


def extract_keywords(text: str) -> list[str]:
    """
    Extract keywords from paper text.

    Args:
        text: Paper text

    Returns:
        List of keywords
    """
    try:
        # Look for keywords section
        pattern = r"(?i)keywords?[:\s]*\n?(.*?)(?=\n\s*(?:introduction|1\.|I\.))"
        match = re.search(pattern, text, re.DOTALL)

        if match:
            keywords_text = match.group(1).strip()
            # Split by common separators
            keywords = re.split(r"[;,·•]|\s{2,}", keywords_text)
            return [k.strip() for k in keywords if k.strip() and len(k.strip()) > 2]

        return []

    except Exception as e:
        logger.error(f"Keywords extraction error: {e}")
        return []


def enrich_document_metadata(
    document: dict[str, Any],
    first_page_text: str,
    use_llm: bool = False,
    llm: Any = None,
) -> dict[str, Any]:
    """
    Enrich document metadata with paper-specific information.

    Args:
        document: Original document dict
        first_page_text: Text from first page
        use_llm: Whether to use LLM for extraction
        llm: LLM instance (required if use_llm is True)

    Returns:
        Enriched document dictionary
    """
    try:
        # Extract metadata
        if use_llm and llm:
            import asyncio

            metadata = asyncio.run(extract_paper_metadata_llm(first_page_text, llm))
        else:
            metadata = extract_paper_metadata(first_page_text)

        # Extract abstract
        abstract = extract_abstract(first_page_text)
        if abstract:
            metadata["abstract"] = abstract

        # Extract keywords
        keywords = extract_keywords(first_page_text)
        if keywords:
            metadata["keywords"] = keywords

        # Merge with existing metadata
        existing_metadata = document.get("metadata", {})
        existing_metadata.update(metadata)
        document["metadata"] = existing_metadata

        # Prepend abstract to content if available
        if abstract and "content" in document:
            document["content"] = f"{abstract}\n\n{document['content']}"

        return document

    except Exception as e:
        logger.error(f"Error enriching document metadata: {e}")
        return document
