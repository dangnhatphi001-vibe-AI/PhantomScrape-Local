import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

def html_to_markdown(html_content: str) -> str:
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Strip structural and styling boilerplates
    garbage_tags = [
        "script", "style", "nav", "footer", "header", "form", 
        "iframe", "noscript", "svg", "path", "aside", "meta", "link"
    ]
    for tag in soup(garbage_tags):
        tag.decompose()
        
    # 2. Identify target elements to protect (main content body)
    protected_containers = []
    for tag_name in ["main", "article", "feed", "shreddit-feed"]:
        found = soup.find(tag_name)
        if found:
            protected_containers.append(found)
            
    # 3. Strip standard social media sidebar, login, navigation elements
    to_decompose = []
    for class_keyword in ["header", "sidebar", "nav", "footer", "login", "signup", "menu", "banner", "terms"]:
        for tag in soup.find_all(class_=re.compile(class_keyword, re.I)):
            if tag.parent is None:
                continue
                
            # Protect tags that are ancestors or descendants of critical content areas
            is_protected = False
            for protected in protected_containers:
                if tag == protected:
                    is_protected = True
                    break
                # Check if tag is ancestor
                curr = protected.parent
                while curr:
                    if curr == tag:
                        is_protected = True
                        break
                    curr = curr.parent
                if is_protected:
                    break
                # Check if tag is descendant
                curr = tag.parent
                while curr:
                    if curr == protected:
                        is_protected = True
                        break
                    curr = curr.parent
                if is_protected:
                    break
            
            if is_protected:
                continue
                
            to_decompose.append(tag)
            
    for tag in to_decompose:
        try:
            tag.decompose()
        except Exception:
            pass
            
    body = soup.find("body")
    cleaned_html = str(body) if body else str(soup)
    
    # 4. Convert clean HTML to markdown (Keep img and a tags to show thumbnails and video links)
    markdown = md(
        cleaned_html,
        heading_style="ATX",
        bullets="-"
    )
    
    # 5. Clean line-by-line to remove common boilerplate phrases
    lines = markdown.splitlines()
    cleaned_lines = []
    
    # Regex patterns of garbage phrases to strip from the final Markdown
    garbage_patterns = [
        r"^\s*log\s*in\s*$",
        r"^\s*sign\s*up\s*$",
        r"^\s*upload\s*$",
        r"^\s*profile\s*$",
        r"^\s*for\s*you\s*$",
        r"^\s*explore\s*$",
        r"^\s*following\s*$",
        r"^\s*live\s*$",
        r"^\s*company\s*$",
        r"^\s*terms\s*&\s*policies\s*$",
        r"^\s*about\s*$",
        r"^\s*terms\s*of\s*service\s*$",
        r"^\s*privacy\s*policy\s*$",
        r"^\s*copyright\s*$",
        r"^\s*tiktok\s*$",
        r"^\s*reddit\s*$",
        r"^\s*create\s*post\s*$",
        r"^\s*open\s*sort\s*options\s*$",
        r"^\s*change\s*post\s*view\s*$",
        r"^\s*card\s*$",
        r"^\s*compact\s*$",
        r"^\s*program\s*$",
        r"^\s*top\s*$",
        r"^\s*users\s*$",
        r"^\s*videos\s*$",
        r"^\s*photo\s*$",
        r"^\s*more\s*$"
    ]
    
    for line in lines:
        stripped = line.strip().lower()
        if not stripped:
            cleaned_lines.append("")
            continue
        
        # Skip garbage match
        if any(re.match(pattern, stripped) for pattern in garbage_patterns):
            continue
            
        # Skip lines that are login / signup URLs
        if "login" in stripped and ("http://" in stripped or "https://" in stripped):
            continue
        if "signup" in stripped and ("http://" in stripped or "https://" in stripped):
            continue
            
        cleaned_lines.append(line)
        
    # Reassemble and normalize newlines
    markdown = "\n".join(cleaned_lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    # Strip double space lines
    markdown = "\n".join(line.strip() for line in markdown.splitlines())
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    
    return markdown.strip()
