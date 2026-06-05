"""TypeScript / JavaScript parser using tree-sitter.

Extracts classes, interfaces, enums, top-level functions (including arrow
functions bound to a const), and class methods, plus import/extends/implements
edges. TypeScript imports reference file *paths* ("./models/foo") rather than
module FQNs, so we resolve relative specifiers to the target file's module name
to build cross-file edges.
"""

from pathlib import Path

import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser

from arcade_agent.parsers.base import LanguageParser, register_parser
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

TS_LANGUAGE = Language(ts_ts.language_typescript())
TSX_LANGUAGE = Language(ts_ts.language_tsx())

_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

# Skip very large files: these are almost always minified/bundled vendor output
# (e.g. a 3 MB terminal.js), not human-authored source. Walking one flat
# multi-thousand-node file per entity is O(n^2) and dominates parse time.
_MAX_FILE_BYTES = 1_000_000


def _get_text(node) -> str:
    return "" if node is None else node.text.decode()


def _strip_ext(name: str) -> str:
    for ext in _EXTENSIONS:
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    if name.endswith(".d"):  # foo.d.ts -> foo
        name = name[:-2]
    return name


def _module_name(file_path: Path, root: Path) -> str:
    """Dotted module name from a file path; trailing 'index' is dropped."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    parts[-1] = _strip_ext(parts[-1])
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    return ".".join(parts)


def _path_key(file_path: Path, root: Path) -> str:
    """Posix rel path without extension, for resolving relative imports."""
    rel = file_path.relative_to(root)
    parts = list(rel.parts)
    parts[-1] = _strip_ext(parts[-1])
    return "/".join(parts)


def _unwrap_export(node):
    """export <decl> wraps the real declaration; return the inner node."""
    if node.type == "export_statement":
        for child in node.children:
            if child.type in ("class_declaration", "abstract_class_declaration",
                              "interface_declaration", "enum_declaration",
                              "function_declaration", "lexical_declaration",
                              "variable_declaration"):
                return child
    return node


def _heritage(class_node):
    """Return (superclass, interfaces) from a class_heritage node."""
    superclass, interfaces = None, []
    for child in class_node.children:
        if child.type != "class_heritage":
            continue
        for clause in child.children:
            names = [_get_text(n) for n in clause.children
                     if n.type in ("identifier", "type_identifier",
                                   "generic_type", "member_expression")]
            if clause.type == "extends_clause" and names:
                superclass = names[0].split("<")[0]
            elif clause.type == "implements_clause":
                interfaces.extend(n.split("<")[0] for n in names)
    return superclass, interfaces


def _arrow_or_func_name(lexical_node):
    """For `const foo = () => {}` / `const foo = function(){}`, return (name, body_node)."""
    for declr in lexical_node.children:
        if declr.type != "variable_declarator":
            continue
        name_node = declr.child_by_field_name("name")
        value = declr.child_by_field_name("value")
        if name_node and value and value.type in ("arrow_function", "function_expression",
                                                   "function"):
            return _get_text(name_node), declr
    return None, None


def _referenced_names(node) -> set[str]:
    """Identifiers / type names used within a node (for edge filtering)."""
    names: set[str] = set()
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in ("identifier", "type_identifier", "property_identifier",
                     "shorthand_property_identifier"):
            names.add(_get_text(n))
        stack.extend(n.children)
    return names


def _extract_imports(root_node) -> list[dict]:
    """Each import: {source, names:[(orig, local)], namespace:[local], default:local|None}."""
    imports = []
    for child in root_node.children:
        if child.type != "import_statement":
            continue
        source = ""
        for s in child.children:
            if s.type == "string":
                frag = next((c for c in s.children if c.type == "string_fragment"), None)
                source = _get_text(frag)
        names, namespace, default = [], [], None
        clause = next((c for c in child.children if c.type == "import_clause"), None)
        if clause:
            for c in clause.children:
                if c.type == "identifier":  # default import
                    default = _get_text(c)
                elif c.type == "namespace_import":
                    ident = next((x for x in c.children if x.type == "identifier"), None)
                    if ident:
                        namespace.append(_get_text(ident))
                elif c.type == "named_imports":
                    for spec in c.children:
                        if spec.type != "import_specifier":
                            continue
                        nm = spec.child_by_field_name("name")
                        alias = spec.child_by_field_name("alias")
                        orig = _get_text(nm)
                        local = _get_text(alias) if alias else orig
                        if orig:
                            names.append((orig, local))
        imports.append({"source": source, "names": names,
                       "namespace": namespace, "default": default})
    return imports


@register_parser
class TypeScriptParser(LanguageParser):
    """TypeScript / JavaScript parser using tree-sitter."""

    @property
    def language(self) -> str:
        return "typescript"

    @property
    def file_extensions(self) -> list[str]:
        return _EXTENSIONS

    def parse(self, files: list[Path], root: Path) -> DependencyGraph:
        ts_parser = Parser(TS_LANGUAGE)
        tsx_parser = Parser(TSX_LANGUAGE)
        root = root.resolve()

        entities: dict[str, Entity] = {}
        edges: list[Edge] = []
        packages: dict[str, list[str]] = {}
        module_by_pathkey: dict[str, str] = {}
        # fqn -> (imports, refs) for the second pass
        file_imports: dict[str, list[dict]] = {}
        entity_refs: dict[str, set[str]] = {}
        entity_file: dict[str, Path] = {}

        # First pass: entities + a path-key -> module index for import resolution.
        for f in files:
            # Resolve to the same form as root (handles macOS /tmp -> /private/tmp).
            f = f.resolve()
            try:
                f.relative_to(root)
            except ValueError:
                continue
            try:
                if f.stat().st_size > _MAX_FILE_BYTES:
                    continue  # skip minified/bundled vendor files
                source = f.read_bytes()
                parser = tsx_parser if f.suffix == ".tsx" else ts_parser
                tree = parser.parse(source)
            except Exception:
                continue
            rn = tree.root_node
            module = _module_name(f, root)
            package = ".".join(module.split(".")[:-1]) if "." in module else ""
            rel_path = str(f.relative_to(root))
            pk = _path_key(f, root)
            module_by_pathkey[pk] = module
            if pk.endswith("/index"):
                module_by_pathkey[pk[: -len("/index")]] = module

            imports = _extract_imports(rn)
            import_sources = [imp["source"] for imp in imports]
            decls = []  # (name, kind, superclass, interfaces, node, owner_fqn)

            for top in rn.children:
                node = _unwrap_export(top)
                t = node.type
                if t in ("class_declaration", "abstract_class_declaration"):
                    nm = node.child_by_field_name("name")
                    if not nm:
                        continue
                    sup, ifaces = _heritage(node)
                    decls.append((_get_text(nm), "class", sup, ifaces, node, None))
                    cls_fqn = f"{module}.{_get_text(nm)}" if module else _get_text(nm)
                    body = node.child_by_field_name("body")
                    if body:
                        for m in body.children:
                            if m.type == "method_definition":
                                mn = m.child_by_field_name("name")
                                if mn:
                                    decls.append((_get_text(mn), "method", None, [], m, cls_fqn))
                elif t == "interface_declaration":
                    nm = node.child_by_field_name("name")
                    if nm:
                        decls.append((_get_text(nm), "interface", None, [], node, None))
                elif t == "enum_declaration":
                    nm = node.child_by_field_name("name")
                    if nm:
                        decls.append((_get_text(nm), "enum", None, [], node, None))
                elif t == "function_declaration":
                    nm = node.child_by_field_name("name")
                    if nm:
                        decls.append((_get_text(nm), "function", None, [], node, None))
                elif t in ("lexical_declaration", "variable_declaration"):
                    nm, dnode = _arrow_or_func_name(node)
                    if nm:
                        decls.append((nm, "function", None, [], dnode, None))

            if not decls:
                if module:  # register module-level entity (e.g. a barrel of consts)
                    fqn = module
                    entities[fqn] = Entity(fqn=fqn, name=module.split(".")[-1], package=package,
                                           file_path=rel_path, kind="module", language="typescript",
                                           imports=import_sources)
                    packages.setdefault(package, []).append(fqn)
                    file_imports[fqn] = imports
                    entity_refs[fqn] = _referenced_names(rn)
                    entity_file[fqn] = f
                continue

            for name, kind, sup, ifaces, node, owner in decls:
                fqn = f"{owner}.{name}" if owner else (f"{module}.{name}" if module else name)
                entities[fqn] = Entity(
                    fqn=fqn, name=name, package=package, file_path=rel_path,
                    kind=kind, language="typescript", imports=import_sources,
                    superclass=sup, interfaces=ifaces,
                    properties={"owner": owner} if owner else {},
                )
                packages.setdefault(package, []).append(fqn)
                file_imports[fqn] = imports
                entity_refs[fqn] = _referenced_names(node) if node else set()
                entity_file[fqn] = f

        # Name -> fqn index for heritage and same-name resolution.
        fqn_index: dict[str, str] = {e.name: e.fqn for e in entities.values()}

        def resolve_module(spec: str, importing: Path) -> str | None:
            if not spec.startswith("."):
                return None  # external package
            target = (importing.parent / spec).resolve()
            try:
                rel = target.relative_to(root)
            except ValueError:
                return None
            key = rel.as_posix()
            for k in (key, f"{key}/index"):
                if k in module_by_pathkey:
                    return module_by_pathkey[k]
            return None

        # Resolve each file's import specifiers ONCE (imports are file-level, so
        # resolving per entity would repeat filesystem .resolve() calls — the
        # difference between seconds and minutes on a few-thousand-file repo).
        specs_by_file: dict[Path, set[str]] = {}
        for fqn2, f2 in entity_file.items():
            bucket = specs_by_file.setdefault(f2, set())
            for imp in file_imports.get(fqn2, []):
                bucket.add(imp["source"])
        resolved_by_file: dict[Path, dict[str, str | None]] = {
            f: {s: resolve_module(s, f) for s in specs}
            for f, specs in specs_by_file.items()
        }

        # Second pass: edges.
        for fqn, entity in entities.items():
            refs = entity_refs.get(fqn, set())
            f = entity_file.get(fqn)
            file_resolution = resolved_by_file.get(f, {})
            for imp in file_imports.get(fqn, []):
                tgt_module = file_resolution.get(imp["source"]) if f else None
                if not tgt_module:
                    continue
                for orig, local in imp["names"]:
                    if refs and local not in refs:
                        continue
                    target = f"{tgt_module}.{orig}"
                    if target in entities:
                        edges.append(Edge(source=fqn, target=target, relation="import"))
                    elif orig in fqn_index:
                        edges.append(Edge(source=fqn, target=fqn_index[orig], relation="import"))
            # extends / implements
            if entity.superclass and entity.superclass in fqn_index:
                edges.append(Edge(source=fqn, target=fqn_index[entity.superclass],
                                  relation="extends"))
            for iface in entity.interfaces or []:
                if iface in fqn_index:
                    edges.append(Edge(source=fqn, target=fqn_index[iface], relation="implements"))

        seen: set[tuple[str, str, str]] = set()
        unique: list[Edge] = []
        for e in edges:
            k = (e.source, e.target, e.relation)
            if k not in seen and e.source != e.target:
                seen.add(k)
                unique.append(e)

        return DependencyGraph(entities=entities, edges=unique, packages=packages)
