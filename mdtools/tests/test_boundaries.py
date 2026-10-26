"""Executable import policy plus CLI-free, standard-library-only host smoke test."""

import ast
import importlib.util
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
PACKAGES = ('mdtools', 'mdsplit', 'langfilter', 'glossary', 'mdhtml_rewrite')


def production_modules():
    modules = {}
    for package in PACKAGES:
        for path in (REPO / package).rglob('*.py'):
            if 'tests' in path.parts:
                continue
            parts = path.relative_to(REPO).with_suffix('').parts
            name = '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)
            modules[name] = path
    return modules


def imported_modules(name, path, known):
    """Resolve nested/TYPE_CHECKING imports too, including relative submodules."""
    package = name if path.name == '__init__.py' else name.rpartition('.')[0]
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module
            yield base
            for alias in node.names:
                candidate = f'{base}.{alias.name}'
                if candidate in known:
                    yield candidate
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            # Literal dynamic imports, including the existing __import__('sys').
            if (isinstance(node.func, ast.Name) and node.func.id == '__import__') or (
                isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'
            ):
                yield node.args[0].value
        elif name == 'mdtools.main' and isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == '_TOOLS':
            # The existing dispatch table is the one nonliteral dynamic route.
            yield from (value[0] for value in ast.literal_eval(node.value).values())


def allowed_import(source, target):
    root = target.split('.')[0]
    if root in sys.stdlib_module_names or root == '__future__':
        return True
    # YAML is the sole optional Python runtime dependency, loaded lazily by I/O.
    if root == 'yaml':
        return source == 'mdtools.core.io'
    if root not in PACKAGES:
        return False
    if target in PACKAGES:  # Package initializers are checked separately.
        return target == 'mdtools' or (target == source.split('.')[0] and target != 'mdtools')
    if source.startswith('mdtools.core'):
        return target.startswith('mdtools.core.')
    if source == 'mdtools.workspace':
        return target.startswith('mdtools.core.') or target == 'mdsplit.schema'
    if source == 'mdtools.diagnostics':
        return target.startswith('mdtools.core.') or target == 'mdtools.workspace'
    if source == 'mdtools.build':
        return target.startswith('mdtools.core.') or target in {
            'glossary.loader', 'glossary.resolver', 'langfilter.filter', 'mdsplit.compose',
        }
    if source.endswith(('.cli', '.__main__')) or source in {'mdtools.main', 'mdtools.build_cli'}:
        # Presentation/dispatch is outside the processing layers.
        return not target.startswith(('mdtools.spec', 'mdtools.backends'))
    if source.split('.')[0] in PACKAGES[1:]:
        return target.startswith('mdtools.core.') or (
            target.split('.')[0] == source.split('.')[0]
            and not target.endswith(('.cli', '.__main__'))
        )
    return False


def test_production_import_directions_and_no_cycles():
    modules = production_modules()
    graph = {name: set() for name in modules}
    for name, path in modules.items():
        for target in imported_modules(name, path, modules):
            assert allowed_import(name, target), f'{name} -> {target}'
            # Include implicit package initialization in the local import graph.
            parts = target.split('.')
            for index in range(1, len(parts) + 1):
                dep = '.'.join(parts[:index])
                if dep in modules and dep != name:
                    graph[name].add(dep)

    done = set()

    def visit(name, active):
        assert name not in active, ' -> '.join((*active, name))
        if name in done:
            return
        for dep in sorted(graph[name]):
            visit(dep, (*active, name))
        done.add(name)

    for name in sorted(graph):
        visit(name, ())


def test_boundary_policy_rejects_reverse_and_external_dependencies():
    for source in ('mdtools.core.source', 'mdsplit.compose', 'mdtools.build', 'mdtools.workspace', 'mdtools.diagnostics'):
        for target in ('mdtools.main', 'mdtools.build_cli', 'mdsplit.cli', 'mdtools.spec.index', 'mdtools.backends.z3', 'z3', 'pygls', 'jsonschema', 'pytest'):
            assert not allowed_import(source, target), (source, target)
    assert not allowed_import('mdtools.core.source', 'mdsplit.schema')
    assert not allowed_import('mdsplit.compose', 'mdtools.workspace')
    assert not allowed_import('mdsplit.compose', 'mdtools.diagnostics')
    assert not allowed_import('glossary.loader', 'mdtools.build')


def test_processing_apis_without_cli_or_optional_dependencies(tmp_path):
    script = r'''
import importlib.abc
import json
from pathlib import Path
import sys

class BlockImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.endswith(('.cli', '.__main__')) or fullname in ('mdtools.main', 'mdtools.build_cli') or fullname.split('.')[0] in ('yaml', 'jsonschema', 'pytest', 'z3', 'cue', 'quint', 'lean', 'pygls', 'lsprotocol'):
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, BlockImports())
from mdtools.build import build_document
from mdtools.core.diagnostics import render_json
from mdtools.diagnostics import inspect_workspace
from mdtools.workspace import load_workspace, snapshot_sources
from mdsplit.decompose import decompose
from mdsplit.compose import compose, compose_with_source_map
from mdsplit.verify import verify
from langfilter.filter import filter_lang
from glossary.loader import load
from glossary.resolver import resolve
from glossary.lister import filter_entries, format_json
from mdhtml_rewrite.inventory import build_inventory
from mdhtml_rewrite.rewrite import rewrite_file
from mdhtml_rewrite.convert import convert_single

root = Path(sys.argv[1])
source = root / 'input.md'
text = '# Title\n\n::: {lang=en}\nHello []{.term id=unit}\n:::\n\n::: {lang=ja}\n日本語\n:::\n'
source.write_text(text, encoding='utf-8')
defs = root / 'defs.json'
defs.write_text(json.dumps({'entries': [{'id': 'unit', 'kind': 'term', 'names': {'en': 'Unit'}}]}))
decompose(source, root / 'sections')
hierarchy = root / 'sections/hierarchy.json'
assert compose(hierarchy) == text
assert not verify(hierarchy).missing_files
assert compose_with_source_map(hierarchy, artifact_uri='memory:composed').artifact.text == text
expected = resolve(filter_lang(text, 'en'), load([defs]), 'en')
assert build_document(hierarchy, lang='en', defs=[defs]) == expected
assert build_document(input_text=text, lang='en', defs=[defs]) == expected
assert json.loads(format_json(filter_entries(load([defs]), None)))[0]['id'] == 'unit'
settings = root / 'mdtools.toml'
settings.write_text('version = 1\n[[documents]]\nkind = "markdown"\npath = "input.md"\n')
assert snapshot_sources(load_workspace(settings))[0].text == text
report = inspect_workspace(settings)
assert report.checks[0].status == 'passed'
assert json.loads(render_json(report))['schema_version'] == 1
assert inspect_workspace(root / 'missing.toml').checks[0].status == 'failed'
assert build_inventory(source)['counts'] is not None
rewrite_file(str(source), str(root / 'output.qmd'))
'''
    # -S removes all site packages, including editable-install and dev helpers.
    completed = subprocess.run([sys.executable, '-S', '-c', script, str(tmp_path)], cwd=REPO, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == completed.stderr == ''
