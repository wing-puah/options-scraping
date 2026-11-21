"""Pre-registration pages: rendered beside the dashboard, linked from the study map."""
import re
from pathlib import Path

from scripts import dashboard as d
from scripts.study_map import build, catalog, digest, render

REG = """# state_map: a registration

Intro with a [sibling](other.md#the-rule), a [missing one](gone.md) and `code [x](y)`.

| cell | rule |
|---|---|
| Q1 | `S-BEAR` |

- top item
  continues here
  - nested one
  - nested two
- second item

## The rule
"""


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "pre-registrations"
    (root / "f1" / "g").mkdir(parents=True)
    (root / "f1" / "g" / "state_map.md").write_text(REG)
    (root / "f1" / "other.md").write_text("# other\n\n## The rule\n\ntext\n")
    (root / "f2").mkdir()
    (root / "f2" / "other.md").write_text("# other again\n")
    return root


def test_stem_names_the_page_and_a_shared_stem_falls_back_to_the_path(tmp_path):
    names = render.prereg_pages(make_root(tmp_path))
    by_rel = {p.relative_to(tmp_path / "pre-registrations").as_posix(): n for p, n in names.items()}
    assert by_rel["f1/g/state_map.md"] == "prereg-state_map.html"
    assert by_rel["f1/other.md"] == "prereg-f1-other.html"
    assert by_rel["f2/other.md"] == "prereg-f2-other.html"
    assert len(set(names.values())) == len(names)


def test_registration_with_a_table_renders_a_table_and_only_under_the_site_dir(tmp_path):
    root, site = make_root(tmp_path), tmp_path / "site"
    written = digest.write_prereg(site, root)
    assert {p.parent for p in written} == {site}
    page = (site / "prereg-state_map.html").read_text()
    assert "<table>" in page and "<th>cell</th>" in page
    assert 'href="dashboard.html#studies"' in page
    assert "state_map.md</code>" in page
    assert "<ul><li>top item continues here<ul><li>nested one</li>" in page
    assert '<h2 id="the-rule">' in page
    assert "<code>S-BEAR</code>" in page
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pre-registrations", "site"]


def test_relative_links_point_at_a_sibling_page_or_fall_back_to_code(tmp_path):
    root, site = make_root(tmp_path), tmp_path / "site"
    digest.write_prereg(site, root)
    page = (site / "prereg-state_map.html").read_text()
    # other.md is not in g/, so the link cannot resolve and shows as code
    assert "<code>missing one</code>" in page
    assert "<code>code [x](y)</code>" in page


def test_a_sibling_in_the_same_folder_links_to_its_page(tmp_path):
    root, site = make_root(tmp_path), tmp_path / "site"
    (root / "f1" / "g" / "third.md").write_text("# third\n\nsee [state](state_map.md#x)\n")
    digest.write_prereg(site, root)
    assert 'href="prereg-state_map.html#x"' in (site / "prereg-third.html").read_text()


def test_study_with_a_registration_links_to_a_written_page_and_one_without_does_not(tmp_path, monkeypatch):
    root, site = make_root(tmp_path), tmp_path / "site"
    names = list(catalog.STUDIES)
    with_reg, without = names[0], names[1]
    (root / f"{with_reg}.md").write_text("# a\n")
    digest.write_prereg(site, root)
    frag = build.build_fragment(out_dir=tmp_path / "none", log_path=tmp_path / "absent.md", prereg_dir=root)
    link = f"prereg-{with_reg}.html"
    assert f'<a href="{link}">' in frag and (site / link).is_file()
    block = re.search(rf'data-study="{without}".*?</li>', frag, re.S)[0]
    assert "Registration:" not in block and "prereg-" not in block


def test_dashboard_main_writes_registration_pages_beside_the_dashboard(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    monkeypatch.setattr(d, "PREREG", root)
    out = tmp_path / "site" / "dashboard.html"
    d.main(["--out", str(out), "--quiet"])
    assert (tmp_path / "site" / "prereg-state_map.html").is_file()
