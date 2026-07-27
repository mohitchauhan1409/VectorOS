"""HTML cleaning utilities.

The selector agent should reason about *structure*, not noise. This strips
scripts, styles and other non-structural clutter so the HTML we send to the LLM
is small, cheap, and focused — while preserving tags, classes and ids that
selectors depend on.

News homepages are large (hundreds of KB) and the article grid often sits well
below the fold, after nav/marquee/ad markup. Naively truncating from the top
would miss it — so when the cleaned HTML exceeds the budget, we zoom into the
*link-dense region* (the window with the most anchor tags), which is reliably
where the article list lives.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

# Tags whose content is noise for structural analysis.
_STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe", "canvas", "template")


def clean_for_llm(html: str, *, max_chars: int) -> str:
    """Return structure-preserving HTML, focused on the article region.

    Removes scripts/styles/comments and collapses whitespace, keeping tags,
    classes and ids intact. If the result still exceeds ``max_chars``, returns
    the densest cluster of links (the likely article grid) instead of the top.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Prefer the semantic main-content root if present.
    root = soup.find("main") or soup.body or soup

    text = str(root)
    text = re.sub(r"\n\s*\n", "\n", text)   # collapse blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)  # collapse runs of spaces

    if len(text) <= max_chars:
        return text
    return _densest_link_window(text, max_chars)


# An article link's path usually ends in a multi-word hyphenated slug
# (e.g. /2026/07/16/openai-launches-new-model). Short nav links (/tech, /login)
# don't match, so this is a good site-agnostic signal for the article grid.
_ARTICLE_LINK = re.compile(r'href="[^"]*/[a-z0-9]+(?:-[a-z0-9]+){2,}')


def _densest_link_window(text: str, max_chars: int) -> str:
    """Return the ``max_chars`` window containing the most *article-like* links.

    News listings cluster many article links together; the densest window of
    slug-style links is a strong, site-agnostic proxy for the article grid.
    Falls back to all ``href`` links if no slug-style links are present.
    """
    positions = [m.start() for m in _ARTICLE_LINK.finditer(text)]
    if not positions:
        positions = [m.start() for m in re.finditer(r"href=", text)]
    if not positions:
        return text[:max_chars]

    best_start, best_count, j = positions[0], 0, 0
    for i, pos in enumerate(positions):
        while j < len(positions) and positions[j] < pos + max_chars:
            j += 1
        if (count := j - i) > best_count:
            best_count, best_start = count, pos

    start = max(0, best_start - 300)  # small margin to capture the container's opening tag
    return text[start:start + max_chars]
