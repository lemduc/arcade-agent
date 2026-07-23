"""Tests for the Rust parser."""

import pytest

pytest.importorskip("tree_sitter_rust")
import arcade_agent.parsers.rust as rust_parser  # noqa: E402
from arcade_agent.parsers.rust import RustParser  # noqa: E402
from arcade_agent.tools.ingest import ingest  # noqa: E402
from arcade_agent.tools.parse import parse  # noqa: E402


def _project(tmp_path):
    (tmp_path / "models.rs").write_text(
        "pub struct User { pub id: u64 }\n"
        "pub enum Role { Admin, Member }\n"
        "pub struct Error;\n"
        "pub struct T;\n"
        "pub type UserId = u64;\n"
    )
    (tmp_path / "repository.rs").write_text(
        "use crate::models::User;\n"
        "pub trait Resource {}\n"
        "pub trait Repository: Resource {\n"
        "    fn find(&self, id: u64) -> Option<User>;\n"
        "}\n"
        "pub struct Store;\n"
        "impl Repository for Store {\n"
        "    fn find(&self, id: u64) -> Option<User> { None }\n"
        "}\n"
    )
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "mod.rs").write_text(
        "use crate::models::{Role, User};\n"
        "use crate::repository::Repository as Repo;\n"
        "pub struct UserService<R: Repo> { repo: R }\n"
        "pub struct MemoryRepository;\n"
        "impl Repo for MemoryRepository {\n"
        "    fn find(&self, id: u64) -> Option<User> { None }\n"
        "}\n"
        "impl<R: Repo> UserService<R> {\n"
        "    pub fn get(&self, id: u64) -> Option<User> { self.repo.find(id) }\n"
        "    pub fn role(&self) -> Role { Role::Member }\n"
        "}\n"
    )
    (tmp_path / "lib.rs").write_text(
        "pub mod models;\n"
        "pub mod repository;\n"
        "pub mod service;\n"
        "pub mod impls;\n"
        "pub use service::UserService;\n"
    )
    (tmp_path / "impls.rs").write_text(
        "use crate::models::User as Account;\n"
        "pub trait DisplayAccount { fn display(&self); }\n"
        "impl DisplayAccount for Account { fn display(&self) {} }\n"
        "pub trait ExternalOwnerHook { fn hook(&self); }\n"
        "impl ExternalOwnerHook for std::io::Error { fn hook(&self) {} }\n"
        "pub trait Forward { fn forward(&self); }\n"
        "impl<'a, T> Forward for &'a mut T { fn forward(&self) {} }\n"
        "#[cfg(unix)] impl Account { fn platform(&self) {} }\n"
        "#[cfg(windows)] impl Account { fn platform(&self) {} }\n"
    )
    return sorted(tmp_path.rglob("*.rs"))


def test_rust_parser_properties():
    parser = RustParser()
    assert parser.language == "rust"
    assert parser.file_extensions == [".rs"]


def test_rust_parser_extracts_types_functions_and_methods(tmp_path):
    graph = RustParser().parse(_project(tmp_path), tmp_path)

    assert graph.entities["models.User"].kind == "struct"
    assert graph.entities["models.Role"].kind == "enum"
    assert graph.entities["models.UserId"].kind == "type"
    assert graph.entities["repository.Repository"].kind == "trait"
    assert graph.entities["repository.Repository.find"].kind == "method"
    assert graph.entities["repository.Store.find"].properties["owner"] == "repository.Store"
    assert graph.entities["service.UserService.get"].kind == "method"
    assert graph.entities["service.UserService.get"].language == "rust"


def test_rust_parser_uses_rust_file_module_conventions(tmp_path):
    graph = RustParser().parse(_project(tmp_path), tmp_path)

    assert "models" in graph.packages
    assert "repository" in graph.packages
    assert "service" in graph.packages
    assert graph.entities["service.UserService"].file_path == "service/mod.rs"
    assert "lib" in graph.entities  # module-only crate root remains visible


def test_rust_parser_resolves_imports_references_and_trait_impls(tmp_path):
    graph = RustParser().parse(_project(tmp_path), tmp_path)
    edges = {(edge.source, edge.target, edge.relation) for edge in graph.edges}

    assert ("service.UserService.get", "models.User", "import") in edges
    assert ("service.UserService.role", "models.Role", "import") in edges
    assert ("repository.Store", "repository.Repository", "implements") in edges
    assert ("service.MemoryRepository", "repository.Repository", "implements") in edges
    assert ("repository.Repository", "repository.Resource", "extends") in edges
    assert ("repository.Repository.find", "models.User", "import") in edges


def test_rust_parser_handles_inline_modules_and_empty_input(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text(
        "mod internal {\n"
        "    pub struct Config;\n"
        "    impl Config { pub fn load() -> Self { Self } }\n"
        "}\n"
    )

    graph = RustParser().parse([source], tmp_path)
    assert "internal.Config" in graph.entities
    assert "internal.Config.load" in graph.entities

    empty = RustParser().parse([], tmp_path)
    assert empty.num_entities == 0
    assert empty.num_edges == 0


@pytest.mark.parametrize(
    "poisoned_source",
    [
        "pub type Poison = " + "::".join(["a"] * 1_200 + ["T"]) + ";",
        "use " + "a::{" * 1_200 + "T" + "}" * 1_200 + ";",
        "mod nested {" * 1_200 + "pub struct Deep;" + "}" * 1_200,
        "struct R; trait Marker {} impl Marker for " + "&" * 1_200 + "R {}",
        "struct R; trait Marker {} impl Marker for "
        + "(" * 1_200
        + "R"
        + ")" * 1_200
        + " {}",
    ],
    ids=[
        "qualified-path",
        "nested-use",
        "inline-modules",
        "wrapped-type",
        "parenthesized-type",
    ],
)
def test_rust_parser_handles_deep_ast_without_losing_sibling_files(tmp_path, poisoned_source):
    """Machine-generated nesting in one file must not abort full analysis."""
    poisoned = tmp_path / "poisoned.rs"
    poisoned.write_text(poisoned_source)
    valid = tmp_path / "valid.rs"
    valid.write_text("pub struct Survives;\n")

    graph = RustParser().parse([poisoned, valid], tmp_path)
    assert "valid.Survives" in graph.entities


def test_rust_parser_discards_partial_state_when_one_file_fails(tmp_path, monkeypatch):
    poisoned = tmp_path / "poisoned.rs"
    poisoned.write_text("pub struct Poisoned;\n")
    valid = tmp_path / "valid.rs"
    valid.write_text("pub struct Survives;\n")
    original_extract_imports = rust_parser._extract_imports

    def fail_for_poisoned_file(container):
        if b"Poisoned" in container.text:
            raise RuntimeError("synthetic extraction failure")
        return original_extract_imports(container)

    monkeypatch.setattr(rust_parser, "_extract_imports", fail_for_poisoned_file)
    graph = RustParser().parse([poisoned, valid], tmp_path)

    assert "poisoned.Poisoned" not in graph.entities
    assert "valid.Survives" in graph.entities


_CFG_TEST_SOURCE = (
    "pub struct Production;\n"
    "#[cfg(test)]\n"
    "mod tests {\n"
    "    struct Fixture;\n"
    "    fn helper() {}\n"
    "}\n"
    "#[cfg(not(test))]\n"
    "mod runtime { pub struct Included; }\n"
)


def test_rust_parser_skips_cfg_test_inline_modules(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text(_CFG_TEST_SOURCE)

    graph = RustParser().parse([source], tmp_path)
    assert "Production" in graph.entities
    assert "runtime.Included" in graph.entities
    assert all(not fqn.startswith("tests") for fqn in graph.entities)
    assert "tests" not in graph.packages


def test_rust_parser_keeps_cfg_test_modules_when_tests_are_not_excluded(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text(_CFG_TEST_SOURCE)

    graph = RustParser(exclude_tests=False).parse([source], tmp_path)
    assert "Production" in graph.entities
    assert "runtime.Included" in graph.entities
    assert "tests.Fixture" in graph.entities
    assert "tests.helper" in graph.entities


def test_rust_parser_skips_nested_items_under_cfg_test_module(tmp_path):
    """Everything below a #[cfg(test)] module is dropped, not just its head."""
    source = tmp_path / "lib.rs"
    source.write_text(
        "pub struct Production;\n"
        "#[cfg(test)]\n"
        "mod tests {\n"
        "    mod inner {\n"
        "        pub struct DeepFixture;\n"
        "    }\n"
        "    impl super::Production {\n"
        "        fn only_for_tests(&self) {}\n"
        "    }\n"
        "}\n"
    )

    graph = RustParser().parse([source], tmp_path)
    assert "Production" in graph.entities
    assert all("Fixture" not in fqn for fqn in graph.entities)
    assert "Production.only_for_tests" not in graph.entities


def test_parse_tool_threads_exclude_tests_to_the_rust_parser(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text(_CFG_TEST_SOURCE)

    excluded = parse(str(tmp_path), language="rust", use_cache=False)
    included = parse(str(tmp_path), language="rust", use_cache=False, exclude_tests=False)

    assert "tests.Fixture" not in excluded.entities
    assert "tests.Fixture" in included.entities


def test_rust_parser_does_not_silently_drop_large_files(tmp_path):
    """No parser caps input size; a >1 MB crate file must still be extracted."""
    # Bulk is comments so the file crosses 1 MB without a huge entity count.
    filler = "// {}\n".format("padding " * 12) * 12_000
    source = tmp_path / "lib.rs"
    source.write_text(f"pub struct Head;\n{filler}pub struct Tail;\n")
    assert source.stat().st_size > 1_000_000

    graph = RustParser().parse([source], tmp_path)
    assert "Head" in graph.entities
    assert "Tail" in graph.entities


def test_rust_parser_skips_cfg_test_with_comment_between_attribute_and_item(tmp_path):
    """A comment between #[cfg(test)] and the item must not break exclusion."""
    source = tmp_path / "lib.rs"
    source.write_text(
        "pub struct Production;\n"
        "#[cfg(test)]\n"
        "// unit tests for this module\n"
        "mod tests {\n"
        "    struct Fixture;\n"
        "    fn helper() {}\n"
        "}\n"
        "#[cfg(test)]\n"
        "/// Doc comment should also not break exclusion\n"
        "mod doc_tests {\n"
        "    struct DocFixture;\n"
        "}\n"
    )

    graph = RustParser().parse([source], tmp_path)
    assert "Production" in graph.entities
    assert all(not fqn.startswith("tests") for fqn in graph.entities)
    assert all(not fqn.startswith("doc_tests") for fqn in graph.entities)


def test_rust_parser_skips_cfg_test_on_non_mod_items(tmp_path):
    """#[cfg(test)] on functions, structs, and impls must also be excluded."""
    source = tmp_path / "lib.rs"
    source.write_text(
        "pub struct Production;\n"
        "#[cfg(test)]\n"
        "fn test_only_helper() {}\n"
        "#[cfg(test)]\n"
        "struct TestFixture { x: u64 }\n"
        "#[cfg(test)]\n"
        "impl TestFixture { fn setup(&self) {} }\n"
        "pub fn real_function() {}\n"
    )

    graph = RustParser().parse([source], tmp_path)
    assert "Production" in graph.entities
    assert "real_function" in graph.entities
    assert "test_only_helper" not in graph.entities
    assert all("TestFixture" not in fqn for fqn in graph.entities)


def test_rust_parser_handles_large_files_without_cap(tmp_path):
    """Files larger than 1MB must still be parsed (no silent cap)."""
    source = tmp_path / "large.rs"
    # Generate a file > 1MB with valid Rust content
    padding = "// padding\n" * 100_000  # ~1.1MB of comments
    source.write_text(padding + "pub struct LargeFile;\n")

    graph = RustParser().parse([source], tmp_path)
    assert "large.LargeFile" in graph.entities


def test_rust_parser_tolerates_invalid_cargo_manifest_encoding(tmp_path):
    (tmp_path / "Cargo.toml").write_bytes(b"\xff\xfe")
    source = tmp_path / "lib.rs"
    source.write_text("pub struct StillParsed;\n")

    repo = ingest(str(tmp_path), language="rust")
    graph = RustParser().parse([source], tmp_path)

    assert repo.source_files == [source]
    assert "StillParsed" in graph.entities


def test_rust_parser_handles_ripgrep_impl_owner_regressions(tmp_path):
    # Reduced from ripgrep 227381d: sibling impls from globset/serde_impl.rs,
    # external owners from matcher/src/lib.rs, and reference blanket impls from
    # ignore/src/walk.rs and searcher/src/sink.rs.
    graph = RustParser().parse(_project(tmp_path), tmp_path)
    edges = {(edge.source, edge.target, edge.relation) for edge in graph.edges}

    display = graph.entities["models.User.display"]
    assert display.properties["owner"] == "models.User"
    assert display.file_path == "impls.rs"
    assert ("models.User", "impls.DisplayAccount", "implements") in edges

    # External and generic blanket impls must not manufacture local owners.
    assert "std.io.Error.hook" not in graph.entities
    assert "models.Error.hook" not in graph.entities
    assert "impls.a.forward" not in graph.entities
    assert "impls.T.forward" not in graph.entities
    assert "models.T.forward" not in graph.entities
    assert all(
        entity.properties["owner"] in graph.entities
        for entity in graph.entities.values()
        if entity.kind == "method"
    )

    # Mutually exclusive cfg impls collapse to one graph method without
    # duplicating package membership.
    assert "models.User.platform" in graph.entities
    assert all(len(fqns) == len(set(fqns)) for fqns in graph.packages.values())


def test_rust_parser_handles_union_raw_identifiers_and_function_modifiers(tmp_path):
    source = tmp_path / "advanced.rs"
    source.write_text(
        "pub union Payload { integer: u64, float: f64 }\n"
        "pub struct r#type;\n"
        "pub async fn fetch() {}\n"
        "pub unsafe fn unchecked() {}\n"
        'pub extern "C" fn exported() {}\n'
    )

    graph = RustParser().parse([source], tmp_path)
    assert graph.entities["advanced.Payload"].kind == "union"
    assert graph.entities["advanced.type"].kind == "struct"
    assert graph.entities["advanced.fetch"].kind == "function"
    assert graph.entities["advanced.unchecked"].kind == "function"
    assert graph.entities["advanced.exported"].kind == "function"


def test_rust_parser_resolves_super_glob_imports_in_inline_modules(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text(
        "mod models { pub struct Config; }\n"
        "mod service {\n"
        "    use super::models::*;\n"
        "    pub fn load(_: Config) {}\n"
        "}\n"
    )

    graph = RustParser().parse([source], tmp_path)
    edges = {(edge.source, edge.target, edge.relation) for edge in graph.edges}
    assert ("service.load", "models.Config", "import") in edges


def test_rust_is_auto_detected_by_ingest_and_parse(tmp_path):
    files = _project(tmp_path)

    repo = ingest(str(tmp_path))
    assert repo.language == "rust"
    assert repo.source_files == files

    graph = parse(str(tmp_path), use_cache=False)
    assert "models.User" in graph.entities


def test_rust_cargo_workspace_keeps_member_crates_and_crate_paths(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[workspace]\nmembers = ["app", "worker"]\n')
    for crate in ("app", "worker"):
        source = tmp_path / crate / "src"
        source.mkdir(parents=True)
        (tmp_path / crate / "Cargo.toml").write_text(
            f'[package]\nname = "{crate}"\nversion = "0.1.0"\n'
        )
    (tmp_path / "worker" / "src" / "lib.rs").write_text("pub struct Worker;\n")
    (tmp_path / "app" / "src" / "lib.rs").write_text(
        "use worker::Worker;\npub struct App { worker: Worker }\n"
    )

    repo = ingest(str(tmp_path), language="rust")
    assert repo.path == tmp_path
    assert len(repo.source_files) == 2

    graph = parse(
        str(repo.path),
        language="rust",
        files=[str(path) for path in repo.source_files],
        use_cache=False,
    )
    assert "app.App" in graph.entities
    assert "worker.Worker" in graph.entities
    assert ("app.App", "worker.Worker", "import") in {
        (edge.source, edge.target, edge.relation) for edge in graph.edges
    }


def test_rust_direct_parse_uses_single_crate_src_as_module_root(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "single-crate"\nversion = "0.1.0"\n')
    source = tmp_path / "src"
    source.mkdir()
    (source / "lib.rs").write_text("pub struct RootType;\n")
    (source / "service.rs").write_text("pub struct Service;\n")

    graph = parse(str(tmp_path), language="rust", use_cache=False)
    assert "RootType" in graph.entities
    assert "service.Service" in graph.entities
    assert "src.RootType" not in graph.entities
