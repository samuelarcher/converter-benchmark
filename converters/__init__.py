"""Auto-discovers and registers all ConverterPlugin subclasses in this directory."""
from __future__ import annotations
import importlib
import pkgutil
from pathlib import Path
from .base import ConverterPlugin

_registry: dict[str, ConverterPlugin] = {}


def _discover():
    pkg_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        if module_name in ("base",):
            continue
        mod = importlib.import_module(f"converters.{module_name}")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, ConverterPlugin)
                and obj is not ConverterPlugin
                and obj.name
            ):
                instance = obj()
                _registry[obj.name] = instance


_discover()


def get_registry() -> dict[str, ConverterPlugin]:
    return _registry


def get_converter(name: str) -> ConverterPlugin | None:
    return _registry.get(name)


def list_converters() -> list[ConverterPlugin]:
    return list(_registry.values())
