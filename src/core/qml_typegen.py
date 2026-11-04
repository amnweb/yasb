"""Generate qmlls/qmllint type metadata from core.qml_types.

python -m core.qml_typegen
python -m core.qml_typegen --check
"""

import argparse
import inspect
import json
import sys
from collections.abc import Collection, Iterable
from enum import Enum
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QByteArray, QMetaMethod, QMetaObject, QMetaProperty, QObject

from core.qml_types import QML_SINGLETONS, QML_TYPES, QML_UNCREATABLE_TYPES, QML_URI, QML_VERSION

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "qmltypes"
DEPENDENCIES = ("QtQml 2.0",)


class GenerationError(ValueError):
    """Unsupported Qt metadata."""


def _text(value: QByteArray | bytes | str) -> str:
    return value if isinstance(value, str) else bytes(value).decode("utf-8")


def _literal(value: object) -> str:
    # JSON strings, arrays, and booleans are valid QML script literals.
    return json.dumps(value, ensure_ascii=True)


class _Writer:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.depth: int = 0

    def line(self, value: str) -> None:
        self.lines.append("    " * self.depth + value)

    def begin(self, name: str) -> None:
        self.line(f"{name} {{")
        self.depth += 1

    def end(self) -> None:
        self.depth -= 1
        self.line("}")

    def field(self, name: str, value: object) -> None:
        self.line(f"{name}: {_literal(value)}")

    def flag(self, name: str, value: bool) -> None:
        if value:
            self.field(name, True)


def _write_type(writer: _Writer, raw: str | None, location: str) -> None:
    if not raw:
        raise GenerationError(f"{location}: missing Qt type information")
    raw = raw.strip()
    if "PyQt_PyObject" in raw:
        raise GenerationError(
            f"{location}: {raw!r} is an opaque Python object, not a QML value type; "
            + "use an explicit Qt type such as 'QVariant', 'QVariantMap', or QObject"
        )
    is_const = raw.startswith("const ")
    if is_const:
        raw = raw[6:].strip()
    raw = raw.rstrip("& ")
    is_list = False
    for container in ("QQmlListProperty", "QList", "QVector"):
        prefix = container + "<"
        if raw.startswith(prefix) and raw.endswith(">"):
            raw = raw[len(prefix) : -1].strip()
            is_list = True
            break
    is_pointer = raw.endswith("*")
    if is_pointer:
        raw = raw[:-1].strip()
    if any(char in raw for char in "<>,*&"):
        raise GenerationError(f"{location}: unsupported compound Qt type {raw!r}")
    writer.field("type", raw)
    writer.flag("isList", is_list)
    writer.flag("isPointer", is_pointer)
    writer.flag("isTypeConstant", is_const)


def _check_revision(revision: int, location: str) -> None:
    if revision:
        raise GenerationError(f"{location}: revisioned members are not registered by register_qml_types()")


def _annotated_class(cls: type[QObject], name: str, described: Collection[type[QObject]]) -> type[QObject] | None:
    """Return the getter's annotated QObject type if included in the output."""
    for base in cls.__mro__:
        if name not in vars(base):
            continue
        getter: object = getattr(vars(base)[name], "fget", None)
        if not callable(getter):
            return None
        try:
            annotation: object = inspect.get_annotations(getter).get("return")
        except NameError:
            return None
        if isinstance(annotation, type) and issubclass(annotation, QObject) and annotation in described:
            return annotation
        return None
    return None


def _write_property(
    writer: _Writer, prop: QMetaProperty, index: int, cls: type[QObject], described: Collection[type[QObject]]
) -> None:
    owner = cls.staticMetaObject.className()
    location = f"{owner}.{prop.name()}"
    _check_revision(prop.revision(), location)
    type_name = prop.typeName()
    # PyQt reports QObject*. The getter annotation gives the concrete type.
    if type_name == "QObject*" and (annotated := _annotated_class(cls, prop.name() or "", described)):
        type_name = f"{annotated.staticMetaObject.className()}*"
    writer.begin("Property")
    writer.field("name", prop.name())
    _write_type(writer, type_name, location)
    writer.field("index", index)
    writer.flag("isReadonly", not prop.isWritable())
    writer.flag("isPropertyConstant", prop.isConstant())
    writer.flag("isFinal", prop.isFinal())
    writer.flag("isRequired", prop.isRequired())
    if prop.hasNotifySignal():
        writer.field("notify", _text(prop.notifySignal().name()))
    # QMetaProperty omits accessor names.
    writer.end()


def _is_private(name: str) -> bool:
    # Internal signals and slots may carry Python objects.
    return name.startswith("_")


def _write_method(writer: _Writer, method: QMetaMethod, owner: str) -> None:
    kind = method.methodType()
    if kind == QMetaMethod.MethodType.Constructor or _is_private(_text(method.name())):
        return
    if kind != QMetaMethod.MethodType.Signal and method.access() != QMetaMethod.Access.Public:
        return
    location = f"{owner}.{_text(method.methodSignature())}"
    _check_revision(method.revision(), location)
    writer.begin("Signal" if kind == QMetaMethod.MethodType.Signal else "Method")
    writer.field("name", _text(method.name()))
    result = method.typeName()
    if result and result != "void":
        _write_type(writer, result, location + " return value")
    writer.flag("isMethodConstant", method.isConst())
    names = method.parameterNames()
    for index, parameter_type in enumerate(method.parameterTypes()):
        writer.begin("Parameter")
        name = _text(names[index]) if index < len(names) else ""
        writer.field("name", name or f"arg{index + 1}")
        _write_type(writer, _text(parameter_type), location + f" parameter {index + 1}")
        writer.end()
    writer.end()


def _write_enums(writer: _Writer, cls: type[QObject], meta: QMetaObject) -> None:
    for index in range(meta.enumeratorOffset(), meta.enumeratorCount()):
        entry = meta.enumerator(index)
        name = entry.name()
        enum_name = entry.enumName()
        if not name or not enum_name:
            raise GenerationError(f"{meta.className()}: enum is missing its name")
        if entry.is64Bit():
            raise GenerationError(
                f"{meta.className()}.{name}: 64-bit enums are unsupported; PyQt6 does not expose QMetaEnum.value64()"
            )
        writer.begin("Enum")
        writer.field("name", name)
        if enum_name != name:
            writer.field("alias", enum_name)
        writer.flag("isFlag", entry.isFlag())
        writer.flag("isScoped", entry.isScoped())
        python_enum: object = vars(cls).get(enum_name)
        values: dict[str, object] = {}
        for key_index in range(entry.keyCount()):
            key = entry.key(key_index)
            if not key:
                raise GenerationError(f"{meta.className()}.{name}: enum key is missing")
            if isinstance(python_enum, type) and issubclass(python_enum, Enum):
                values[key] = cast(object, python_enum.__members__[key].value)
            else:
                values[key] = entry.value(key_index)
        writer.field("values", values)
        writer.end()


def _python_bases(cls: type[QObject]) -> Iterable[type[QObject]]:
    """Yield Python QObject bases. Dependencies describe the Qt bases."""
    for base in cls.__mro__:
        if issubclass(base, QObject) and (base is cls or not base.__module__.startswith("PyQt6.")):
            yield base


def _source_file(cls: type[QObject]) -> str | None:
    try:
        source = inspect.getsourcefile(cls)
    except TypeError, OSError:
        return None
    return Path(source).resolve().as_posix() if source else None


def render_qmltypes(
    types: Iterable[type[QObject]] = QML_TYPES,
    uncreatable: Iterable[type[QObject]] = QML_UNCREATABLE_TYPES,
    singletons: Iterable[type[QObject]] = QML_SINGLETONS,
) -> str:
    """Return a deterministic plugins.qmltypes document for the exported types."""
    creatable = set(types)
    single = set(singletons)
    exported = creatable | set(uncreatable) | single
    if len(exported) != len(creatable) + len(set(uncreatable)) + len(single):
        raise GenerationError("a class can be only one of creatable, uncreatable and singleton")
    classes: dict[str, type[QObject]] = {}
    for exported_cls in exported:
        for cls in _python_bases(exported_cls):
            name = cls.staticMetaObject.className()
            if not name:
                raise GenerationError(f"{cls.__name__} has no Qt class name")
            previous = classes.get(name)
            if previous is not None and previous is not cls:
                raise GenerationError(
                    f"multiple Python classes have Qt name {name!r}; give QObject classes distinct names"
                )
            classes[name] = cls

    described = set(classes.values())
    major, minor = QML_VERSION
    writer = _Writer()
    writer.line("import QtQuick.tooling 1.2")
    writer.line("")
    writer.line("// Generated by core.qml_typegen from core.qml_types. Tooling metadata only; do not edit.")
    writer.begin("Module")
    for name, cls in sorted(classes.items()):
        meta = cls.staticMetaObject
        writer.begin("Component")
        writer.field("name", name)
        source_file = _source_file(cls)
        if source_file is not None:
            writer.field("file", source_file)
        writer.field("accessSemantics", "reference")
        parent = meta.superClass()
        if parent is not None:
            writer.field("prototype", parent.className())
        if cls in exported:
            writer.field("exports", [f"{QML_URI}/{cls.__name__} {major}.{minor}"])
            writer.field("exportMetaObjectRevisions", [(major << 8) | minor])
        writer.field("isCreatable", cls in creatable)
        writer.flag("isSingleton", cls in single)
        for index in range(meta.classInfoOffset(), meta.classInfoCount()):
            info = meta.classInfo(index)
            info_name = info.name()
            if not info_name:
                raise GenerationError(f"{name}: class info is missing its name")
            field = {"DefaultProperty": "defaultProperty", "ParentProperty": "parentProperty"}.get(info_name)
            if field:
                writer.field(field, info.value())
            elif info_name.startswith("QML."):
                raise GenerationError(f"{name}: QML class info {info_name!r} is not supported by this generator")
        _write_enums(writer, cls, meta)
        for index in range(meta.propertyOffset(), meta.propertyCount()):
            prop = meta.property(index)
            if prop.isScriptable() and not _is_private(prop.name() or ""):
                _write_property(writer, prop, index - meta.propertyOffset(), cls, described)
        for index in range(meta.methodOffset(), meta.methodCount()):
            _write_method(writer, meta.method(index), name)
        writer.end()
    writer.end()
    return "\n".join(writer.lines) + "\n"


def module_files(
    output_dir: Path,
    types: Iterable[type[QObject]] = QML_TYPES,
    uncreatable: Iterable[type[QObject]] = QML_UNCREATABLE_TYPES,
    singletons: Iterable[type[QObject]] = QML_SINGLETONS,
) -> dict[Path, str]:
    directory = output_dir.joinpath(*QML_URI.split("."))
    qmldir = [f"module {QML_URI}", "typeinfo plugins.qmltypes", *(f"depends {dep}" for dep in DEPENDENCIES)]
    return {
        directory / "plugins.qmltypes": render_qmltypes(types, uncreatable, singletons),
        directory / "qmldir": "\n".join(qmldir) + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    class Arguments(argparse.Namespace):
        def __init__(self) -> None:
            super().__init__()
            self.output_dir: Path = DEFAULT_OUTPUT_DIR
            self.check: bool = False

    parser = argparse.ArgumentParser(description="Generate QML type information for core.qml_types.")
    _ = parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    _ = parser.add_argument("--check", action="store_true", help="Fail if output is missing or stale; do not write")
    args = parser.parse_args(argv, namespace=Arguments())
    try:
        # Render first so unsupported types leave existing output intact.
        files = module_files(args.output_dir)
        stale = False
        for path, content in sorted(files.items()):
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current == content:
                continue
            if args.check:
                print(f"Out of date: {path}", file=sys.stderr)
                stale = True
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                _ = path.write_text(content, encoding="utf-8", newline="\n")
                print(f"Generated {path}")
        return 1 if stale else 0
    except (ValueError, OSError) as error:
        parser.exit(2, f"qml_typegen: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
