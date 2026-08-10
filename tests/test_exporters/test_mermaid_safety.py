"""Every Mermaid emitter must sanitize names the same way.

There are three emitters (the HTML snapshot diagram, the architecture diagram,
and the CI drift report posted as a PR comment). They used to sanitize names
independently, so a name that was safe in one diagram broke another, and ids
minted one way did not match edges minted the other way.
"""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.exporters.html import build_snapshot_mermaid
from arcade_agent.exporters.mermaid import (
    build_mermaid_diagram,
    mermaid_label_text,
    mermaid_node_id,
)
from arcade_agent.parsers.graph import DependencyGraph


def _snapshot(*names: str) -> dict:
    return {
        "components": [
            {"name": n, "num_entities": 1, "class_count": 1, "method_count": 0}
            for n in names
        ],
        "component_dependencies": [
            {"source": names[0], "target": names[-1]}
        ]
        if len(names) > 1
        else [],
    }


def _architecture(*names: str) -> Architecture:
    return Architecture(
        components=[
            Component(name=n, responsibility="", entities=[f"{n}.E"]) for n in names
        ],
        rationale="",
        algorithm="test",
    )


class TestNodeIdSafety:
    def test_quote_in_name_is_escaped_not_emitted_raw(self) -> None:
        assert '"' not in mermaid_label_text('Auth "core"')
        assert "#quot;" in mermaid_label_text('Auth "core"')

    def test_hash_escaped_before_quote_so_entity_is_not_corrupted(self) -> None:
        # If `"` were escaped first, the later `#` pass would rewrite the `#`
        # of `#quot;` and produce `#35;quot;`.
        assert mermaid_label_text('a"b#c') == "a#quot;b#35;c"

    def test_symbol_only_names_do_not_collapse_to_one_node(self) -> None:
        assert mermaid_node_id("###") != mermaid_node_id("!!!")

    def test_leading_digit_is_prefixed(self) -> None:
        # Mermaid reads a leading digit as the start of a number, not an id.
        assert not mermaid_node_id("2fa")[0].isdigit()

    def test_long_names_sharing_a_prefix_stay_distinct(self) -> None:
        a, b = "A" * 60 + "_first", "A" * 60 + "_second"
        assert mermaid_node_id(a) != mermaid_node_id(b)

    def test_node_id_is_a_pure_function_so_edges_resolve(self) -> None:
        assert mermaid_node_id("auth.core") == mermaid_node_id("auth.core")


class TestEmittersAgree:
    """The real defect: three emitters, three different sanitizers."""

    def test_all_emitters_produce_the_same_id_for_one_name(self) -> None:
        name = 'weird "svc".v2'
        snapshot_out = build_snapshot_mermaid(_snapshot(name))
        arch_out = build_mermaid_diagram(_architecture(name), DependencyGraph())
        expected = mermaid_node_id(name)
        assert f"    {expected}[" in snapshot_out
        assert f"    {expected}[" in arch_out

    def test_architecture_diagram_escapes_quotes(self) -> None:
        out = build_mermaid_diagram(_architecture('Auth "core"'), DependencyGraph())
        body = out.split("\n", 1)[1]
        # Only the label delimiters may remain; the name's own quotes must not.
        assert body.count('"') == 2

    def test_architecture_diagram_symbol_names_do_not_collide(self) -> None:
        out = build_mermaid_diagram(_architecture("###", "!!!"), DependencyGraph())
        declared = [ln.strip().split("[")[0] for ln in out.split("\n")[1:] if ln.strip()]
        assert len(set(declared)) == 2

    def test_snapshot_edges_reference_declared_nodes(self) -> None:
        out = build_snapshot_mermaid(_snapshot("a.b-c", "x y"))
        declared = {
            ln.strip().split("[")[0] for ln in out.split("\n") if "[" in ln
        }
        for line in out.split("\n"):
            if "-->" in line:
                src, tgt = (p.strip() for p in line.split("-->"))
                assert src in declared and tgt in declared


class TestDriftReportDiagram:
    """The PR-comment path — previously the least sanitized of the three."""

    def _diagram(self, *names: str) -> str:
        from arcade_agent.ci.arch_diff import build_report

        return build_report(
            current=_architecture(*names),
            graph=DependencyGraph(),
            metrics=[],
            smells=[],
        )

    def test_quote_in_component_name_does_not_break_the_block(self) -> None:
        report = self._diagram('Auth "core"')
        inside = report.split("```mermaid", 1)[1].split("```", 1)[0]
        assert '"core"' not in inside
        assert "#quot;" in inside

    def test_punctuation_in_name_yields_a_valid_id(self) -> None:
        report = self._diagram("auth.core-v2")
        inside = report.split("```mermaid", 1)[1].split("```", 1)[0]
        assert mermaid_node_id("auth.core-v2") in inside
        assert "auth.core-v2[" not in inside
