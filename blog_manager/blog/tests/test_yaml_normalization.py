"""
Tests for YAML front-matter normalization.

These tests ensure that common YAML formatting issues are automatically
corrected during export to prevent validation errors.
"""
import pytest
from blog.exporter import _normalize_yaml_indentation, _extract_frontmatter_from_body


class TestYAMLNormalization:
    """Test automatic YAML normalization fixes."""
    
    def test_normalize_5_space_indentation_to_4(self):
        """Test that 5-space indentation is corrected to 4 spaces."""
        content = """---
faqs:
  - question: "What is this?"
     answer: "This has 5 spaces indentation"
  - question: "Another question?"
     answer: "Also 5 spaces"
---
Body content
"""
        
        result = _normalize_yaml_indentation(content)
        lines = result.split('\n')
        
        # Check that answer lines now have 4 spaces (not 5)
        answer_line_1 = lines[3]  # First answer
        answer_line_2 = lines[5]  # Second answer
        
        assert answer_line_1.startswith('    answer:'), f"Expected 4 spaces, got: {repr(answer_line_1)}"
        assert answer_line_2.startswith('    answer:'), f"Expected 4 spaces, got: {repr(answer_line_2)}"
        
        # Verify YAML parses correctly
        fm = _extract_frontmatter_from_body(result)
        assert 'faqs' in fm
        assert len(fm['faqs']) == 2
    
    def test_remove_double_punctuation_at_string_end(self):
        """Test that ?? at end of quoted strings is removed."""
        content = """---
title: "Test title"??
faqs:
  - question: "Is this okay?"??
    answer: "Yes it is"
---
"""
        
        result = _normalize_yaml_indentation(content)
        
        # Check that ?? is removed
        assert '"??' not in result
        assert 'title: "Test title"' in result
        assert 'question: "Is this okay?"' in result
        
        # Verify YAML parses correctly
        fm = _extract_frontmatter_from_body(result)
        assert fm['title'] == 'Test title'
        assert fm['faqs'][0]['question'] == 'Is this okay?'
    
    def test_preserve_correct_indentation(self):
        """Test that correctly indented YAML is not changed."""
        content = """---
title: "Correct YAML"
categories: ["test"]
faqs:
  - question: "Question?"
    answer: "Answer with 4 spaces"
---
Body
"""
        
        result = _normalize_yaml_indentation(content)
        
        # Should be unchanged (except maybe whitespace normalization)
        fm_original = _extract_frontmatter_from_body(content)
        fm_result = _extract_frontmatter_from_body(result)
        
        assert fm_original == fm_result
    
    def test_post_588_style_content(self):
        """Test real-world case from post 588 with multiple issues."""
        content = """---
title: "Test Article"
categories: ["burnout-e-lavoro"]
faqs:
  - question: "What is stress?"
     answer: "Stress is complex"
  - question: "Is burnout my fault?"??
     answer: "No, it's systemic"
  - question: "What helps?"
     answer: "Community support"
---
Article body
"""
        
        result = _normalize_yaml_indentation(content)
        
        # Verify all issues are fixed
        assert '"??' not in result
        
        # Check indentation
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if 'answer:' in line:
                stripped = line.lstrip(' ')
                indent = len(line) - len(stripped)
                assert indent == 4, f"Line {i+1} has {indent} spaces, expected 4: {repr(line)}"
        
        # Verify YAML parses successfully
        fm = _extract_frontmatter_from_body(result)
        assert 'faqs' in fm
        assert len(fm['faqs']) == 3
        assert fm['faqs'][1]['question'] == 'Is burnout my fault?'  # No ??
    
    def test_no_frontmatter_returns_unchanged(self):
        """Test that content without front-matter is returned unchanged."""
        content = "Just plain markdown\nNo YAML here\n"
        
        result = _normalize_yaml_indentation(content)
        
        assert result == content
    
    def test_empty_content_returns_empty(self):
        """Test that empty content is handled gracefully."""
        assert _normalize_yaml_indentation('') == ''
    
    def test_complex_faqs_with_indentation_issues(self):
        """Test complex FAQ structures with common indentation issues."""
        content = """---
title: "Complex Article"
categories: ["test"]
faqs:
  - question: "First question?"
     answer: "First answer with 5 spaces"
  - question: "Second question?"
     answer: "Second answer, also 5 spaces"
  - question: "Third?"??
     answer: "Third answer"
howto:
  name: "Test"
  steps:
    - "Step 1"
     - "Step 2 with wrong indent"
---
"""
        
        # Should auto-fix and parse successfully
        result = _normalize_yaml_indentation(content)
        fm = _extract_frontmatter_from_body(result)
        
        assert 'title' in fm
        assert 'faqs' in fm
        assert len(fm['faqs']) == 3
        # Check ?? was removed
        assert fm['faqs'][2]['question'] == 'Third?'
    
    def test_integration_with_extract_frontmatter(self):
        """Test that normalization is applied during extraction."""
        content = """---
title: "Test"??
faqs:
  - question: "Q?"
     answer: "A"
---
Body
"""
        
        # _extract_frontmatter_from_body should auto-normalize
        fm = _extract_frontmatter_from_body(content)
        
        assert fm['title'] == 'Test'  # No ??
        assert fm['faqs'][0]['answer'] == 'A'
    
    def test_preserves_body_content_after_frontmatter(self):
        """Test that body content after front-matter is preserved exactly."""
        body_content = """This is the body.
It has multiple lines.
And should not be modified.
"""
        
        content = f"""---
title: "Test"??
---
{body_content}"""
        
        result = _normalize_yaml_indentation(content)
        
        # Extract body (everything after second ---)
        parts = result.split('---', 2)
        result_body = parts[2] if len(parts) > 2 else ''
        
        assert result_body == '\n' + body_content


@pytest.mark.django_db
class TestYAMLNormalizationWithModels:
    """Test YAML normalization with actual Django models."""
    
    def test_validate_post_with_malformed_yaml(self):
        """Test that posts with malformed YAML can still be validated after normalization."""
        from blog.models import Post, Site, Author
        from blog.services.preview_service import validate_post_for_preview
        
        # Create a site
        site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            repo_path="/tmp/test-repo"
        )
        
        # Create an author
        author = Author.objects.create(
            site=site,
            name="Test Author",
            slug="test-author"
        )
        
        # Create post with malformed YAML (5-space indentation + ??)
        post = Post.objects.create(
            site=site,
            author=author,
            title="Test Post",
            slug="test-post",
            content="""---
title: "Test"
categories: ["test-cluster"]
faqs:
  - question: "Q?"??
     answer: "A with 5 spaces"
---
Body content
"""
        )
        
        # Should validate successfully due to normalization
        validate_post_for_preview(post)  # Should not raise
        
        # Cleanup
        post.delete()
        author.delete()
        site.delete()
