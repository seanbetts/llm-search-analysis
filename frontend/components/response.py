"""Response formatting and display utilities."""

import re


def sanitize_response_markdown(text: str) -> str:
  """Remove heavy dividers and downscale large headings so they don't exceed the section title.

  Args:
    text: Markdown text to sanitize

  Returns:
    Cleaned markdown text
  """
  if not text:
    return ""

  cleaned_lines = []
  divider_pattern = re.compile(r"^\s*[-_*]{3,}\s*$")
  heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

  for line in text.splitlines():
    # Drop markdown horizontal rules
    if divider_pattern.match(line):
      continue

    # Normalize headings: ensure none are larger than level 3
    m = heading_pattern.match(line)
    if m:
      hashes, content = m.groups()
      # Downscale: any heading becomes at most level 4 to stay below section titles
      line = f"#### {content}"
    cleaned_lines.append(line)

  cleaned = "\n".join(cleaned_lines)
  # Remove simple HTML <hr> tags as well
  cleaned = re.sub(r"<\s*hr\s*/?\s*>", "", cleaned, flags=re.IGNORECASE)
  return cleaned.strip()


def format_response_text(text: str, citations: list) -> str:
  """Format response text by converting reference-style citation links to inline links.

  ChatGPT includes markdown reference links at the bottom like:
  [1]: URL "Title"
  [2]: URL "Title"

  And uses them inline like: [Text][1]

  We convert these to inline markdown links: [Text](URL)
  Then remove the reference definitions.

  Args:
    text: Response text with reference-style links
    citations: List of citation objects (not used in current implementation)

  Returns:
    Formatted markdown text with inline links
  """
  if not text:
    return ""

  # Step 1: Extract reference-style link definitions into a mapping
  # Pattern: [N]: URL "Title" or [N]: URL
  # Handle titles with escaped quotes by matching everything after URL to end of line
  reference_pattern = r'^\[(\d+)\]:\s+(https?://\S+)(?:\s+.*)?$'
  references = {}
  for match in re.finditer(reference_pattern, text, flags=re.MULTILINE):
    ref_num = match.group(1)
    url = match.group(2)
    references[ref_num] = url

  # Step 2: Replace reference-style links with inline links
  # Pattern: [text][N] where N is a number
  def replace_reference_link(match):
    link_text = match.group(1)
    ref_num = match.group(2)
    if ref_num in references:
      return f"[{link_text}]({references[ref_num]})"
    return match.group(0)  # Keep original if reference not found

  text = re.sub(r'\[([^\]]+)\]\[(\d+)\]', replace_reference_link, text)

  # Step 3: Remove the reference definitions from the bottom
  text = re.sub(reference_pattern, '', text, flags=re.MULTILINE)

  # Step 4: Clean up any resulting multiple newlines
  text = re.sub(r'\n{3,}', '\n\n', text)

  return sanitize_response_markdown(text.strip())


def extract_images_from_response(text: str):
  """Extract image URLs from markdown or img tags and return cleaned text.

  Args:
    text: Response text containing images

  Returns:
    Tuple of (cleaned_text, list_of_image_urls)
  """
  if not text:
    return text, []
  images = []

  # Markdown images ![alt](url)
  def md_repl(match):
    url = match.group(1)
    if url:
      images.append(url)
    return ""  # strip from text
  text = re.sub(r"!\[[^\]]*\]\(([^) ]+)[^)]*\)", md_repl, text)

  # HTML img tags
  def html_repl(match):
    src = match.group(1)
    if src:
      images.append(src)
    return ""
  text = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', html_repl, text, flags=re.IGNORECASE)

  return text.strip(), images
