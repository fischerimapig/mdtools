"""Shared name rules for the resolver and supplied-result validation.

Only collected nodes participate. No syntax, diagnostics, or I/O live here.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from .model import Declaration, NAMESPACES, Namespace, NodeKey, Reference, REFERENCE_NAMESPACES

Registries = Mapping[Namespace, Mapping[str, tuple[NodeKey, ...]]]


class ResolutionIndex:
    def __init__(self, nodes: Iterable[NodeKey], declarations: Iterable[Declaration] = ()):
        spaces = {namespace: {} for namespace in NAMESPACES}
        names = {}
        for key in nodes:
            spaces[key.namespace].setdefault(key.name, []).append(key)
            names.setdefault(key.name, []).append(key)
        self.registries: Registries = MappingProxyType({
            namespace: MappingProxyType({name: tuple(keys) for name, keys in entries.items()})
            for namespace, entries in spaces.items()
        })
        self.names = {name: tuple(keys) for name, keys in names.items()}
        self.declarations = {declaration.key: declaration for declaration in declarations}

    def classify(self, reference: Reference) -> tuple[str, tuple[NodeKey, ...], str | None]:
        name, kind = reference.name, reference.kind
        if kind in ('type', 'uses') and name in ('bool', 'int'):
            return ('resolved' if kind == 'type' else 'wrong-kind', (), name)
        matches = self.registries[REFERENCE_NAMESPACES[kind]].get(name, ())
        if len(matches) > 1:
            return 'ambiguous', matches, None
        if matches:
            if kind in ('type', 'uses'):
                target = self.declarations[matches[0]]
                allowed = ('type',) if kind == 'type' else ('variable', 'constant')
                if target.kind not in allowed:
                    return 'wrong-kind', matches, None
            return 'resolved', matches, None
        elsewhere = self.names.get(name, ())
        return ('wrong-kind' if elsewhere else 'undefined', elsewhere, None)

    @property
    def collisions(self) -> tuple[tuple[NodeKey, ...], ...]:
        return tuple(keys for space in self.registries.values() for keys in space.values() if len(keys) > 1)
