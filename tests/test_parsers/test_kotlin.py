"""Tests for the Kotlin parser.

Covers JVM-typical Kotlin constructs that matter for architecture recovery:
package/imports (including aliases and star imports), class/interface/object/enum,
inheritance, nested/companion types, methods, top-level functions, and default package.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
from arcade_agent.parsers.base import get_parser  # noqa: E402
from arcade_agent.parsers.kotlin import KotlinParser  # noqa: E402
from arcade_agent.tools.ingest import ingest  # noqa: E402


def test_kotlin_parser_properties():
    parser = KotlinParser()
    assert parser.language == "kotlin"
    assert ".kt" in parser.file_extensions
    assert ".kts" in parser.file_extensions


def test_kotlin_parser_registered_for_language_and_extension():
    assert get_parser("kotlin").language == "kotlin"
    assert get_parser(".kt").language == "kotlin"
    assert get_parser(".kts").language == "kotlin"


def test_kotlin_parser_empty():
    parser = KotlinParser()
    graph = parser.parse([], Path("/tmp"))
    assert graph.num_entities == 0
    assert graph.num_edges == 0


def test_kotlin_parser_entities(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")

    assert "com.example.calc.Calculator" in graph.entities
    assert "com.example.calc.AdvancedCalculator" in graph.entities
    assert "com.example.calc.Ops" in graph.entities
    assert "com.example.calc.ExtendedOps" in graph.entities
    assert "com.example.util.MathHelper" in graph.entities
    assert "com.example.calc.Point" in graph.entities
    assert "com.example.calc.Mode" in graph.entities
    assert "com.example.calc.Result" in graph.entities
    assert "com.example.calc.Result.Ok" in graph.entities
    assert "com.example.calc.Result.Err" in graph.entities
    assert "com.example.calc.Calculator.Factory" in graph.entities
    assert "com.example.calc.topLevelHelper" in graph.entities
    assert "com.example.companion.Service" in graph.entities
    assert "com.example.companion.Service.Companion" in graph.entities
    assert "DefaultPackageType" in graph.entities
    assert "com.example.star.UsesStarImport" in graph.entities


def test_kotlin_parser_kinds(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")

    assert graph.entities["com.example.calc.Ops"].kind == "interface"
    assert graph.entities["com.example.calc.Calculator"].kind == "class"
    assert graph.entities["com.example.util.MathHelper"].kind == "object"
    assert graph.entities["com.example.calc.Mode"].kind == "enum"
    assert graph.entities["com.example.calc.Calculator.Factory"].kind == "object"
    assert graph.entities["com.example.companion.Service.Companion"].kind == "object"
    assert graph.entities["com.example.calc.topLevelHelper"].kind == "function"
    assert graph.entities["com.example.calc.Point"].properties.get("data") is True
    assert graph.entities["com.example.calc.Result"].properties.get("sealed") is True


def test_kotlin_parser_language_and_package(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")

    calc = graph.entities["com.example.calc.Calculator"]
    assert calc.language == "kotlin"
    assert calc.package == "com.example.calc"
    assert calc.name == "Calculator"
    assert "com.example.util.MathHelper" in calc.imports
    assert calc.properties.get("import_aliases") == {"MH": "com.example.util.MathHelper"}

    default_pkg = graph.entities["DefaultPackageType"]
    assert default_pkg.package == ""
    assert default_pkg.language == "kotlin"


def test_kotlin_parser_methods(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")

    assert "com.example.calc.Calculator.add" in graph.entities
    assert "com.example.calc.Calculator.multiply" in graph.entities
    assert "com.example.calc.Calculator.Factory.create" in graph.entities
    assert "com.example.companion.Service.Companion.default" in graph.entities
    method = graph.entities["com.example.calc.Calculator.add"]
    assert method.kind == "method"
    assert method.properties["owner"] == "com.example.calc.Calculator"


def test_kotlin_parser_packages(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")

    assert "com.example.calc" in graph.packages
    assert "com.example.util" in graph.packages
    assert "com.example.calc.Calculator" in graph.packages["com.example.calc"]
    assert "com.example.util.MathHelper" in graph.packages["com.example.util"]
    assert "DefaultPackageType" in graph.packages[""]


def test_kotlin_parser_import_and_inheritance_edges(kotlin_files, fixtures_dir):
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")
    edge_tuples = {(e.source, e.target, e.relation) for e in graph.edges}

    assert (
        "com.example.calc.Calculator",
        "com.example.util.MathHelper",
        "import",
    ) in edge_tuples
    assert (
        "com.example.calc.AdvancedCalculator",
        "com.example.calc.Calculator",
        "extends",
    ) in edge_tuples
    assert (
        "com.example.calc.Calculator",
        "com.example.calc.Ops",
        "implements",
    ) in edge_tuples
    assert (
        "com.example.calc.ExtendedOps",
        "com.example.calc.Ops",
        "implements",
    ) in edge_tuples
    assert (
        "com.example.calc.Result.Ok",
        "com.example.calc.Result",
        "extends",
    ) in edge_tuples


def test_kotlin_parser_star_import_does_not_create_fake_type_edge(kotlin_files, fixtures_dir):
    """`import pkg.*` should not invent an edge to a non-entity package FQN."""
    parser = KotlinParser()
    graph = parser.parse(kotlin_files, fixtures_dir / "kotlin_project")
    star_edges = [
        e
        for e in graph.edges
        if e.source == "com.example.star.UsesStarImport" and e.relation == "import"
    ]
    assert star_edges == []
    # Still recorded as an import string for resolution hints.
    imports = graph.entities["com.example.star.UsesStarImport"].imports
    assert "com.example.util" in imports


def test_kotlin_parser_deduplicates_import_edges_when_alias_repeats_target(tmp_path: Path):
    src = tmp_path / "DupImport.kt"
    src.write_text(
        """
package com.example.app

import com.example.app.Helper
import com.example.app.Helper as H

object Helper

class Client
""".strip()
        + "\n"
    )
    graph = KotlinParser().parse([src], tmp_path)
    import_edges = [
        e
        for e in graph.edges
        if e.source == "com.example.app.Client"
        and e.target == "com.example.app.Helper"
        and e.relation == "import"
    ]
    assert len(import_edges) == 1


def test_kotlin_parser_resolves_import_alias_for_inheritance(tmp_path: Path):
    """Alias should resolve when a type uses the alias in its parent clause."""
    src = tmp_path / "AliasUse.kt"
    src.write_text(
        """
package com.example.app

import com.example.app.Base as B

open class Base

class Child : B()
""".strip()
        + "\n"
    )
    graph = KotlinParser().parse([src], tmp_path)
    edge_tuples = {(e.source, e.target, e.relation) for e in graph.edges}
    assert ("com.example.app.Child", "com.example.app.Base", "extends") in edge_tuples


def test_kotlin_parser_resolves_qualified_superclass_and_interface(tmp_path: Path):
    """Qualified parent names must not be truncated to the first identifier."""
    util = tmp_path / "com" / "example" / "util"
    app = tmp_path / "com" / "example" / "app"
    util.mkdir(parents=True)
    app.mkdir(parents=True)
    (util / "MathHelper.kt").write_text(
        "package com.example.util\nopen class MathHelper\ninterface RunnableLike\n"
    )
    (app / "Child.kt").write_text(
        """
package com.example.app

class Child : com.example.util.MathHelper(), com.example.util.RunnableLike
""".strip()
        + "\n"
    )
    graph = KotlinParser().parse(
        [util / "MathHelper.kt", app / "Child.kt"],
        tmp_path,
    )
    child = graph.entities["com.example.app.Child"]
    assert child.superclass == "com.example.util.MathHelper"
    assert "com.example.util.RunnableLike" in child.interfaces
    edge_tuples = {(e.source, e.target, e.relation) for e in graph.edges}
    assert (
        "com.example.app.Child",
        "com.example.util.MathHelper",
        "extends",
    ) in edge_tuples
    assert (
        "com.example.app.Child",
        "com.example.util.RunnableLike",
        "implements",
    ) in edge_tuples


def test_kotlin_parser_skips_unreadable_files(tmp_path: Path):
    missing = tmp_path / "Missing.kt"
    empty = tmp_path / "Empty.kt"
    empty.write_text("")
    valid = tmp_path / "Ok.kt"
    valid.write_text("package com.example\nclass Ok\n")
    graph = KotlinParser().parse([missing, empty, valid], tmp_path)
    assert "com.example.Ok" in graph.entities


def test_kotlin_parser_script_extension_accepted(tmp_path: Path):
    script = tmp_path / "build.kts"
    script.write_text("package scripts\nobject Build { fun run() {} }\n")
    graph = KotlinParser().parse([script], tmp_path)
    assert "scripts.Build" in graph.entities
    assert graph.entities["scripts.Build"].kind == "object"


def test_ingest_discovers_kotlin_files(fixtures_dir):
    repo = ingest(
        str(fixtures_dir / "kotlin_project"),
        language="kotlin",
        exclude_tests=False,
    )
    try:
        assert repo.language == "kotlin"
        assert any(path.suffix == ".kt" for path in repo.source_files)
        assert any(path.name == "Calculator.kt" for path in repo.source_files)
    finally:
        repo.cleanup()


# ---------------------------------------------------------------------------
# Embabel-grounded regressions (minimized snippets from embabel-agent patterns)
# ---------------------------------------------------------------------------


def test_embabel_annotation_classes_extracted(kotlin_embabel_pattern_files, fixtures_dir):
    """annotation class (+ nested) from LlmTool/annotations.kt must still be entities.

    tree-sitter-kotlin may set has_error on some annotation ASTs; the parser must
    remain resilient and surface the declarations for architecture recovery.
    """
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    assert "com.embabel.patterns.annotation.LlmTool" in graph.entities
    assert "com.embabel.patterns.annotation.LlmTool.Meta" in graph.entities
    assert "com.embabel.patterns.annotation.LlmTool.Param" in graph.entities
    assert "com.embabel.patterns.annotation.EmbabelComponent" in graph.entities
    # Grammar currently surfaces annotations as class_declaration → kind "class".
    assert graph.entities["com.embabel.patterns.annotation.LlmTool"].kind in {
        "class",
        "annotation",
    }


def test_embabel_backtick_method_names_do_not_drop_outer_class(
    kotlin_embabel_pattern_files, fixtures_dir
):
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    assert "com.embabel.patterns.backtick.CustomValidationAnnotationTest" in graph.entities
    assert (
        "com.embabel.patterns.backtick.CustomValidationAnnotationTest.normalMethod"
        in graph.entities
    )


def test_embabel_property_accessor_annotations_still_extract_interfaces(
    kotlin_embabel_pattern_files, fixtures_dir
):
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    assert "com.embabel.patterns.accessors.PromptElement" in graph.entities
    assert "com.embabel.patterns.accessors.PromptContributor" in graph.entities
    assert graph.entities["com.embabel.patterns.accessors.PromptElement"].kind == "interface"
    edge_tuples = {(e.source, e.target, e.relation) for e in graph.edges}
    assert (
        "com.embabel.patterns.accessors.PromptContributor",
        "com.embabel.patterns.accessors.PromptElement",
        "implements",
    ) in edge_tuples


def test_embabel_extension_only_file_has_functions_without_receiver_edge(
    kotlin_embabel_pattern_files, fixtures_dir
):
    """Documented gap: extension functions are entities, but not linked to receiver."""
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    assert "com.embabel.patterns.extensions.PromptRunner" in graph.entities
    assert "com.embabel.patterns.extensions.withDocument" in graph.entities
    assert graph.entities["com.embabel.patterns.extensions.withDocument"].kind == "function"

    receiver_edges = [
        e
        for e in graph.edges
        if e.source == "com.embabel.patterns.extensions.withDocument"
        and e.target == "com.embabel.patterns.extensions.PromptRunner"
    ]
    assert receiver_edges == []


def test_embabel_top_level_val_file_contributes_no_type_from_that_file(
    kotlin_embabel_pattern_files, fixtures_dir
):
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    # PersonaSpec lives in a sibling file and is discovered.
    assert "com.embabel.patterns.toplevel.PersonaSpec" in graph.entities
    # Top-level vals are not modeled as entities today.
    assert "com.embabel.patterns.toplevel.MARVIN" not in graph.entities
    personas_types = [
        e
        for e in graph.entities.values()
        if e.kind in {"class", "interface", "object", "enum"}
        and e.file_path.endswith("toplevel/Personas.kt")
    ]
    assert personas_types == []


def test_embabel_annotation_only_file_still_yields_annotation_entity(
    kotlin_embabel_pattern_files, fixtures_dir
):
    """Meta-annotated annotation-only files (Provided.kt) must not disappear.

    tree-sitter often emits annotated_expression/infix_expression instead of
    class_declaration when `@Target`/`@Retention` wrap `annotation class`.
    """
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)
    assert "com.embabel.patterns.provided.Provided" in graph.entities


def test_embabel_unresolved_jdk_superclass_does_not_invent_extends_edge(
    kotlin_embabel_pattern_files, fixtures_dir
):
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)

    exc = graph.entities["com.embabel.patterns.jdk.SpecialReturnException"]
    assert exc.superclass == "RuntimeException"
    extends_edges = [
        e
        for e in graph.edges
        if e.source == "com.embabel.patterns.jdk.SpecialReturnException"
        and e.relation == "extends"
    ]
    assert extends_edges == []


def test_embabel_pattern_corpus_parses_without_throwing(
    kotlin_embabel_pattern_files, fixtures_dir
):
    root = fixtures_dir / "kotlin_embabel_patterns"
    graph = KotlinParser().parse(kotlin_embabel_pattern_files, root)
    assert graph.num_entities > 0
    assert any(
        e.file_path.endswith("annotation/LlmTool.kt") for e in graph.entities.values()
    )
