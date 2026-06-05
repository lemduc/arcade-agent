"""Go parser using tree-sitter.

Maps each directory (a Go package) to a package in the dependency graph, and
extracts types (structs/interfaces), functions, and methods. Cross-package edges
come from qualified references (`pkg.Symbol`) resolved against imports; intra-
package edges come from bare references to sibling declarations.
"""

from pathlib import Path

import tree_sitter_go as tsgo
from tree_sitter import Language, Parser

from arcade_agent.parsers.base import LanguageParser, register_parser
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

GO_LANGUAGE = Language(tsgo.language())

# Skip very large files (generated/vendored), which dominate parse time.
_MAX_FILE_BYTES = 1_000_000


def _get_text(node) -> str:
    return "" if node is None else node.text.decode()


def _pkg_path(file_path: Path, root: Path) -> str:
    """Dotted path of the file's directory — the Go package, used for grouping."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts[:-1])  # drop the filename; Go packages are directories
    return ".".join(parts)


def _receiver_type(method_node) -> str | None:
    """Type name a method is declared on (the receiver)."""
    plist = next((c for c in method_node.children if c.type == "parameter_list"), None)
    if not plist:
        return None
    for pd in plist.children:
        if pd.type == "parameter_declaration":
            for n in pd.children:
                if n.type == "type_identifier":
                    return _get_text(n)
                if n.type == "pointer_type":
                    ti = next((x for x in n.children if x.type == "type_identifier"), None)
                    if ti:
                        return _get_text(ti)
    return None


def _imports(root_node) -> list[dict]:
    """List of {alias, path} for each import (alias defaults to the path's last segment)."""
    out = []
    for child in root_node.children:
        if child.type != "import_declaration":
            continue
        specs = []
        for sub in child.children:
            if sub.type == "import_spec":
                specs.append(sub)
            elif sub.type == "import_spec_list":
                specs.extend(s for s in sub.children if s.type == "import_spec")
        for spec in specs:
            path_node = next((c for c in spec.children
                              if c.type == "interpreted_string_literal"), None)
            alias_node = next((c for c in spec.children
                               if c.type == "package_identifier"), None)
            if not path_node:
                continue
            path = _get_text(path_node).strip('"')
            alias = _get_text(alias_node) if alias_node else path.rstrip("/").split("/")[-1]
            out.append({"alias": alias, "path": path})
    return out


def _qualified_refs(node) -> set[tuple[str, str]]:
    """(pkgAlias, Symbol) pairs from cross-package references. Covers both value
    refs (`store.Open()` → selector_expression) and type refs in signatures
    (`*store.DB` → qualified_type with package_identifier + type_identifier)."""
    refs: set[tuple[str, str]] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "selector_expression":
            operand = n.child_by_field_name("operand")
            field = n.child_by_field_name("field")
            if operand is not None and operand.type == "identifier" and field is not None:
                refs.add((_get_text(operand), _get_text(field)))
        elif n.type == "qualified_type":
            pkg = next((c for c in n.children if c.type == "package_identifier"), None)
            sym = next((c for c in n.children if c.type == "type_identifier"), None)
            if pkg is not None and sym is not None:
                refs.add((_get_text(pkg), _get_text(sym)))
        stack.extend(n.children)
    return refs


def _bare_names(node) -> set[str]:
    names: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in ("identifier", "type_identifier"):
            names.add(_get_text(n))
        stack.extend(n.children)
    return names


@register_parser
class GoParser(LanguageParser):
    """Go source code parser using tree-sitter."""

    @property
    def language(self) -> str:
        return "go"

    @property
    def file_extensions(self) -> list[str]:
        return [".go"]

    def parse(self, files: list[Path], root: Path) -> DependencyGraph:
        parser = Parser(GO_LANGUAGE)
        root = root.resolve()

        entities: dict[str, Entity] = {}
        edges: list[Edge] = []
        packages: dict[str, list[str]] = {}
        ent_imports: dict[str, list[dict]] = {}
        ent_qrefs: dict[str, set[tuple[str, str]]] = {}
        ent_bare: dict[str, set[str]] = {}
        # internal package import path suffix -> package module (dir-dotted)
        pkgpath_index: dict[str, str] = {}

        for f in files:
            f = f.resolve()
            try:
                f.relative_to(root)
            except ValueError:
                continue
            if f.name.endswith("_test.go"):
                continue
            try:
                if f.stat().st_size > _MAX_FILE_BYTES:
                    continue  # skip generated/vendored giant files
                tree = parser.parse(f.read_bytes())
            except Exception:
                continue
            rn = tree.root_node
            pkg = _pkg_path(f, root)  # dir-dotted; the component grouping key
            rel_path = str(f.relative_to(root))
            imps = _imports(rn)
            import_paths = [i["path"] for i in imps]
            # Record this directory so cross-package imports can resolve to it.
            pkgpath_index[pkg.replace(".", "/")] = pkg

            decls = []  # (name, kind, owner)
            for top in rn.children:
                if top.type == "type_declaration":
                    for spec in top.children:
                        if spec.type != "type_spec":
                            continue
                        nm = spec.child_by_field_name("name")
                        kind = "type"
                        if any(c.type == "interface_type" for c in spec.children):
                            kind = "interface"
                        elif any(c.type == "struct_type" for c in spec.children):
                            kind = "struct"
                        if nm:
                            decls.append((_get_text(nm), kind, None, spec))
                elif top.type == "function_declaration":
                    nm = top.child_by_field_name("name")
                    if nm:
                        decls.append((_get_text(nm), "function", None, top))
                elif top.type == "method_declaration":
                    nm = top.child_by_field_name("name")
                    recv = _receiver_type(top)
                    if nm:
                        decls.append((_get_text(nm), "method", recv, top))

            for name, kind, owner, node in decls:
                base = f"{pkg}.{owner}" if owner else pkg
                fqn = f"{base}.{name}" if base else name
                entities[fqn] = Entity(
                    fqn=fqn, name=name, package=pkg, file_path=rel_path,
                    kind=kind, language="go", imports=import_paths,
                    properties={"owner": f"{pkg}.{owner}"} if owner else {},
                )
                packages.setdefault(pkg, []).append(fqn)
                ent_imports[fqn] = imps
                ent_qrefs[fqn] = _qualified_refs(node)
                ent_bare[fqn] = _bare_names(node)

        # (package, name) -> fqn for precise intra/cross-package resolution.
        pkg_name_index: dict[tuple[str, str], str] = {}
        for e in entities.values():
            pkg_name_index[(e.package, e.name)] = e.fqn

        def resolve_import_to_pkg(import_path: str) -> str | None:
            """Match an import path to an internal package directory by suffix."""
            norm = import_path.strip("/")
            for dirpath, mod in pkgpath_index.items():
                if norm == dirpath or norm.endswith("/" + dirpath):
                    return mod
            return None

        for fqn, entity in entities.items():
            # Cross-package qualified refs: pkg.Symbol
            alias_to_pkg = {}
            for imp in ent_imports.get(fqn, []):
                mod = resolve_import_to_pkg(imp["path"])
                if mod:
                    alias_to_pkg[imp["alias"]] = mod
            for alias, symbol in ent_qrefs.get(fqn, set()):
                mod = alias_to_pkg.get(alias)
                if mod and (mod, symbol) in pkg_name_index:
                    edges.append(Edge(source=fqn, target=pkg_name_index[(mod, symbol)],
                                      relation="uses"))
            # Intra-package references to sibling declarations.
            for name in ent_bare.get(fqn, set()):
                tgt = pkg_name_index.get((entity.package, name))
                if tgt and tgt != fqn:
                    edges.append(Edge(source=fqn, target=tgt, relation="uses"))

        seen: set[tuple[str, str, str]] = set()
        unique: list[Edge] = []
        for e in edges:
            k = (e.source, e.target, e.relation)
            if k not in seen and e.source != e.target:
                seen.add(k)
                unique.append(e)

        return DependencyGraph(entities=entities, edges=unique, packages=packages)
