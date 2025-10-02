"""
Management command to debug the front matter issue.
"""
from django.core.management.base import BaseCommand
import re
import yaml
from blog.exporter import _normalize_leading_frontmatter, FRONTMATTER_RE


class Command(BaseCommand):
    help = "Debug front matter duplication issue"

    def handle(self, *args, **options):
        # Test case 1: With blank line between blocks (current exported file issue)
        content1 = """---
title: Test Hierarchical Export
---

---
categories: ["case-study"]
---

# Test

Test gerarchico.
"""
        
        # Test case 2: Consecutive blocks (no blank line) 
        content2 = """---
title: Test Hierarchical Export
---
---
categories: ["case-study"]
---

# Test

Test gerarchico.
"""
        
        # Test case 3: With default UI title
        content3 = """---
title: nuovo post
---
---
title: Test Hierarchical Export
categories: ["case-study"]
---

# Test

Test gerarchico.
"""
        
        test_cases = [
            ("With blank line between blocks", content1),
            ("Consecutive blocks", content2),
            ("With default UI title", content3),
        ]
        
        for name, content in test_cases:
            self.stdout.write(f"\n\n===== TEST CASE: {name} ====")
            self.debug_content(content)
            
    def debug_content(self, content):
        self.stdout.write("=== ORIGINAL CONTENT ===")
        self.stdout.write(repr(content))
        
        # Extract front matter blocks using the regex
        self.stdout.write("\n=== FRONT MATTER BLOCKS FOUND ===")
        blocks = FRONTMATTER_RE.findall(content)
        self.stdout.write(f"Number of blocks: {len(blocks)}")
        for i, block in enumerate(blocks):
            self.stdout.write(f"Block {i+1}: {repr(block)}")
            try:
                data = yaml.safe_load(block)
                self.stdout.write(f"Parsed: {data}")
            except Exception as e:
                self.stdout.write(f"Parse error: {e}")
        
        # Test normalization
        self.stdout.write("\n=== AFTER NORMALIZATION ===")
        normalized = _normalize_leading_frontmatter(content)
        norm_blocks = FRONTMATTER_RE.findall(normalized)
        self.stdout.write(f"Number of blocks after normalization: {len(norm_blocks)}")
        for i, block in enumerate(norm_blocks):
            try:
                data = yaml.safe_load(block)
                self.stdout.write(f"Normalized Block {i+1}: {data}")
            except Exception as e:
                self.stdout.write(f"Parse error: {e}")
        
        self.stdout.write(f"Final normalized content:\n{normalized}")