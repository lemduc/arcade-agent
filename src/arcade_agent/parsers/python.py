"""Python parser using tree-sitter."""

from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from arcade_agent.parsers.base import LanguageParser, register_parser
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

PYTHON_LANGUAGE = Language(tspython.language())


def _get_text(node) -> str:
    if node is None:
        return ""
    return node.text.decode()


def _collect_nodes(node, type_name: str) -> list:
    """Recursively collect all descendant nodes of a given type."""
    results = []
    if node.type == type_name:
        results.append(node)
    for child in node.children:
        results.extend(_collect_nodes(child, type_name))
    return results


def _extract_module_name(file_path: Path, root: Path) -> str:
    """Convert a file path to a Python module name."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    # Remove .py extension from last part
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    # Remove __init__ from the end
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _extract_imports(root_node) -> list[dict]:
    """Extract import statements from a Python file.

    Returns list of dicts with 'module' and 'names' keys.
    """
    imports = []

    for child in root_node.children:
        if child.type == "import_statement":
            # import foo, import foo.bar
            for sub in child.children:
                if sub.type == "dotted_name":
                    imports.append({"module": _get_text(sub), "names": []})

        elif child.type == "import_from_statement":
            # from foo import bar, baz
            module = ""
            names = []
            for sub in child.children:
                if sub.type == "dotted_name" and not module:
                    module = _get_text(sub)
                elif sub.type == "dotted_name":
                    names.append(_get_text(sub))
                elif sub.type == "import_prefix":
                    # relative imports like "from . import"
                    module = _get_text(sub)
            imports.append({"module": module, "names": names})

    return imports


def _unwrap_decorated(node):
    """Unwrap a decorated_definition to get the inner class/function node."""
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("class_definition", "function_definition"):
                return child
    return node


def _extract_classes(root_node) -> list[dict]:
    """Extract class definitions with bases (including decorated classes)."""
    classes = []
    for node in root_node.children:
        actual = _unwrap_decorated(node)
        if actual.type != "class_definition":
            continue
        name_node = actual.child_by_field_name("name")
        if not name_node:
            continue

        bases = []
        superclass = None
        # Find argument_list (bases)
        for child in actual.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(_get_text(arg))
                    elif arg.type == "attribute":
                        bases.append(_get_text(arg))

        if bases:
            superclass = bases[0]

        # Use the outer node (with decorators) so _extract_referenced_names
        # captures decorator arguments too.
        classes.append({
            "name": _get_text(name_node),
            "kind": "class",
            "superclass": superclass,
            "interfaces": bases[1:] if len(bases) > 1 else [],
            "node": node,
        })
    return classes


def _extract_functions(root_node) -> list[dict]:
    """Extract top-level function definitions (including decorated functions)."""
    functions = []
    for node in root_node.children:
        actual = _unwrap_decorated(node)
        if actual.type != "function_definition":
            continue
        name_node = actual.child_by_field_name("name")
        if name_node:
            # Use the outer node (with decorators) so _extract_referenced_names
            # captures decorator arguments too.
            functions.append({
                "name": _get_text(name_node),
                "kind": "function",
                "superclass": None,
                "interfaces": [],
                "node": node,
            })
    return functions


def _extract_referenced_names(node) -> set[str]:
    """Collect identifier and attribute names *used at runtime* within a node.

    Walks the full AST subtree but skips type annotations (parameter types,
    return types) because they are not runtime dependencies. This ensures that
    edges reflect actual usage, not just structural typing.
    """
    # Node types that contain type annotations (not runtime references)
    _ANNOTATION_TYPES = frozenset({"type", "return_type"})

    names: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == "identifier":
            names.add(_get_text(n))
        elif n.type == "attribute":
            names.add(_get_text(n))
            for child in n.children:
                if child.type == "identifier":
                    names.add(_get_text(child))
                    break
        elif n.type == "decorator":
            for child in n.children:
                if child.type in ("identifier", "attribute", "call"):
                    names.update(_extract_referenced_names(child))
            continue
        for child in n.children:
            # Skip type annotation subtrees — they are not runtime deps
            if child.parent and child == child.parent.child_by_field_name("type"):
                continue
            if child.parent and child == child.parent.child_by_field_name("return_type"):
                continue
            stack.append(child)
    return names


@register_parser
class PythonParser(LanguageParser):
    """Python source code parser using tree-sitter."""

    @property
    def language(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> list[str]:
        return [".py"]

    def parse(self, files: list[Path], root: Path) -> DependencyGraph:
        """Parse Python source files and extract a dependency graph.

        Args:
            files: List of .py file paths.
            root: Root directory of the project.

        Returns:
            DependencyGraph with entities, edges, and package info.
        """
        parser = Parser(PYTHON_LANGUAGE)
        entities: dict[str, Entity] = {}
        edges: list[Edge] = []
        packages: dict[str, list[str]] = {}
        module_imports: dict[str, list[dict]] = {}  # fqn -> import info
        entity_refs: dict[str, set[str]] = {}  # fqn -> names referenced in body

        # First pass: collect all entities
        for py_file in files:
            try:
                source = py_file.read_bytes()
                tree = parser.parse(source)
            except Exception:
                continue

            root_node = tree.root_node
            module_name = _extract_module_name(py_file, root)
            package = ".".join(module_name.split(".")[:-1]) if "." in module_name else ""
            rel_path = str(py_file.relative_to(root))
            file_imports = _extract_imports(root_node)

            classes = _extract_classes(root_node)
            functions = _extract_functions(root_node)

            all_decls = classes + functions

            if not all_decls:
                # Register the module itself as an entity
                fqn = module_name
                entity = Entity(
                    fqn=fqn,
                    name=module_name.split(".")[-1],
                    package=package,
                    file_path=rel_path,
                    kind="module",
                    language="python",
                    imports=[imp["module"] for imp in file_imports],
                )
                entities[fqn] = entity
                packages.setdefault(package, []).append(fqn)
                module_imports[fqn] = file_imports
                # Module entities reference everything at file level
                entity_refs[fqn] = _extract_referenced_names(root_node)
            else:
                for decl in all_decls:
                    fqn = f"{module_name}.{decl['name']}" if module_name else decl["name"]
                    # Extract names actually referenced within this function/class body
                    refs = _extract_referenced_names(decl["node"]) if decl.get("node") else set()
                    entity = Entity(
                        fqn=fqn,
                        name=decl["name"],
                        package=package,
                        file_path=rel_path,
                        kind=decl["kind"],
                        language="python",
                        imports=[imp["module"] for imp in file_imports],
                        superclass=decl.get("superclass"),
                        interfaces=decl.get("interfaces", []),
                    )
                    entities[fqn] = entity
                    packages.setdefault(package, []).append(fqn)
                    module_imports[fqn] = file_imports
                    entity_refs[fqn] = refs

        # Build name -> fqn index
        fqn_index: dict[str, str] = {}
        for entity in entities.values():
            fqn_index[entity.name] = entity.fqn

        # Second pass: resolve import edges (only for actually-referenced names)
        for fqn, entity in entities.items():
            refs = entity_refs.get(fqn, set())
            for imp_info in module_imports.get(fqn, []):
                module = imp_info["module"]
                names = imp_info["names"]

                if names:
                    # from module import name1, name2
                    for name in names:
                        # Only create edge if the entity actually references this name
                        if refs and name not in refs:
                            continue
                        target = f"{module}.{name}"
                        if target in entities:
                            edges.append(Edge(source=fqn, target=target, relation="import"))
                        elif name in fqn_index:
                            edges.append(
                                Edge(source=fqn, target=fqn_index[name], relation="import")
                            )
                else:
                    # import module — only if the module name is referenced
                    if refs and module.split(".")[-1] not in refs:
                        continue
                    if module in entities:
                        edges.append(Edge(source=fqn, target=module, relation="import"))

            # Inheritance edges
            if entity.superclass and entity.superclass in fqn_index:
                edges.append(
                    Edge(source=fqn, target=fqn_index[entity.superclass], relation="extends")
                )

        # Deduplicate edges
        seen: set[tuple[str, str, str]] = set()
        unique_edges: list[Edge] = []
        for edge in edges:
            key = (edge.source, edge.target, edge.relation)
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)

        return DependencyGraph(entities=entities, edges=unique_edges, packages=packages)
