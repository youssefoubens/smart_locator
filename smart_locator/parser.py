"""DOM extraction utilities."""

from __future__ import annotations

from typing import Dict, List


PARSER_SCRIPT = r"""
const interactiveTags = new Set(["input", "button", "a", "select", "textarea"]);
const results = [];

function cleanText(value) {
  return (value || "").replace(/\s+/g, " ").trim();
}

function pickAttributes(element) {
  const names = ["id", "name", "class", "placeholder", "aria-label", "data-testid", "type", "href", "role"];
  const attrs = {};
  for (const name of names) {
    const value = element.getAttribute(name);
    if (value) {
      attrs[name] = value;
    }
  }
  return attrs;
}

function cssPath(node) {
  if (!node || node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }
  const parts = [];
  let current = node;
  while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.documentElement) {
    let selector = current.tagName.toLowerCase();
    if (current.id) {
      selector += "#" + CSS.escape(current.id);
      parts.unshift(selector);
      break;
    }
    const siblings = Array.from(current.parentElement ? current.parentElement.children : []);
    const sameTag = siblings.filter((child) => child.tagName === current.tagName);
    if (sameTag.length > 1) {
      selector += `:nth-of-type(${sameTag.indexOf(current) + 1})`;
    }
    parts.unshift(selector);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

function parentContext(element) {
  const parent = element.parentElement;
  if (!parent) {
    return null;
  }
  return {
    tag: parent.tagName.toLowerCase(),
    text: cleanText(parent.innerText || parent.textContent || ""),
    attributes: pickAttributes(parent)
  };
}

function visit(root, framePath = [], shadowPath = []) {
  const elements = root.querySelectorAll("*");
  for (const element of elements) {
    const tag = element.tagName.toLowerCase();
    if (interactiveTags.has(tag) || element.getAttribute("role") === "button") {
      results.push({
        tag,
        text: cleanText(element.innerText || element.textContent || ""),
        attributes: pickAttributes(element),
        parent: parentContext(element),
        frame_path: framePath,
        shadow_path: shadowPath,
        css_path: cssPath(element)
      });
    }
    if (element.shadowRoot) {
      const host = cssPath(element) || tag;
      visit(element.shadowRoot, framePath, shadowPath.concat(host));
    }
    if (tag === "iframe") {
      const marker = cssPath(element) || "iframe";
      try {
        const doc = element.contentDocument;
        if (doc) {
          visit(doc, framePath.concat(marker), shadowPath);
        }
      } catch (err) {
        // Cross-origin frames are skipped.
      }
    }
  }
}

visit(document);
return results;
"""


def parse_dom(driver) -> List[Dict[str, object]]:
    """Extract interactive elements from the live DOM."""

    return list(driver.execute_script(PARSER_SCRIPT))


def truncate_context(elements: List[Dict[str, object]], limit: int = 50) -> List[Dict[str, object]]:
    """Keep prompt payloads reasonably small."""

    return list(elements[:limit])
