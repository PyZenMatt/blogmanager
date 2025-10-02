"""
Debug script to test the actual front matter issue seen in the exported files.
"""
import re
import yaml
from blog.exporter import _normalize_leading_frontmatter, FRONTMATTER_RE


def debug_front_matter_issue():
    # This is the actual content from the exported file that shows the bug
    actual_problematic_content = """---
title: Test Hierarchical Export
---

---
categories: ["case-study"]
---

# Test

Test gerarchico.
"""
    
    print("=== ORIGINAL CONTENT ===")
    print(repr(actual_problematic_content))
    print("\n=== VISUAL CONTENT ===")
    print(actual_problematic_content)
    
    # Extract front matter blocks
    print("\n=== FRONT MATTER BLOCKS FOUND ===")
    blocks = FRONTMATTER_RE.findall(actual_problematic_content)
    print(f"Number of blocks: {len(blocks)}")
    for i, block in enumerate(blocks):
        print(f"Block {i+1}:")
        print(repr(block))
        try:
            data = yaml.safe_load(block)
            print(f"Parsed: {data}")
        except Exception as e:
            print(f"Parse error: {e}")
        print()
    
    # Test normalization
    print("=== NORMALIZED CONTENT ===")
    normalized = _normalize_leading_frontmatter(actual_problematic_content)
    print(repr(normalized))
    print("\n=== VISUAL NORMALIZED ===")
    print(normalized)
    
    # Check normalized blocks
    print("\n=== NORMALIZED FRONT MATTER BLOCKS ===")
    norm_blocks = FRONTMATTER_RE.findall(normalized)
    print(f"Number of blocks after normalization: {len(norm_blocks)}")
    for i, block in enumerate(norm_blocks):
        print(f"Block {i+1}:")
        try:
            data = yaml.safe_load(block)
            print(f"Parsed: {data}")
        except Exception as e:
            print(f"Parse error: {e}")
        print()


if __name__ == "__main__":
    debug_front_matter_issue()