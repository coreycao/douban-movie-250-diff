import unittest
from datetime import date
from types import SimpleNamespace

from src.readme_renderer import (
    extract_date_headings,
    extract_history_sections,
    render_diff_section,
    render_header,
)


class TestReadmeRenderer(unittest.TestCase):
    """测试 README Markdown 渲染工具"""

    def test_render_header_contains_project_links_and_update_date(self):
        header = render_header(date(2026, 6, 29))

        self.assertIn("# Douban-Movie-250-Diff", header)
        self.assertIn("[GitHub Pages](https://coreycao.github.io/douban-movie-250-diff/)", header)
        self.assertIn("*Updated on 2026-06-29*", header)

    def test_render_diff_section_covers_all_change_types(self):
        changes = SimpleNamespace(
            added=[
                {'rank': '4', 'name': 'Mock Movie E', 'link': 'https://example.com/e', 'score': '9.3'}
            ],
            removed=[
                {'rank': '5', 'name': 'Mock Movie D', 'link': 'https://example.com/d', 'score': '9.2'}
            ],
            changed=[
                (
                    {'rank': '1', 'name': 'Mock Movie A', 'link': 'https://example.com/a', 'score': '9.7'},
                    {'rank': '2', 'name': 'Mock Movie A', 'link': 'https://example.com/a', 'score': '9.8'}
                )
            ],
        )

        section = render_diff_section("2026-06-29", changes)

        self.assertIn("## 2026-06-29", section)
        self.assertIn("新上榜电影", section)
        self.assertIn("退出榜单电影", section)
        self.assertIn("排名及分数变化", section)
        self.assertIn("↓ 1→2 (-1)", section)
        self.assertIn("↑ 9.7→9.8 (+0.1)", section)

    def test_extract_history_sections_skips_current_and_empty_sections(self):
        lines = [
            "# Douban-Movie-250-Diff\n",
            "\n",
            "## 2026-06-29\n",
            "\n",
            "current content\n",
            "## 2026-06-01\n",
            "\n",
            "## 2026-05-01\n",
            "\n",
            "history content\n",
        ]

        sections = extract_history_sections(lines, "2026-06-29")

        self.assertNotIn("## 2026-06-29\n", sections)
        self.assertNotIn("## 2026-06-01\n", sections)
        self.assertIn("## 2026-05-01\n", sections)
        self.assertIn("history content\n", sections)

    def test_extract_date_headings(self):
        content = "## 2026-06-29\n\ncontent\n## 2026-06-01\n"

        self.assertEqual(extract_date_headings(content), ["2026-06-29", "2026-06-01"])


if __name__ == '__main__':
    unittest.main()
