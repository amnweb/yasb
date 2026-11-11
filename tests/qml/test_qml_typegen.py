from enum import IntEnum
from pathlib import Path

import pytest
from PyQt6.QtCore import QObject, pyqtEnum, pyqtProperty, pyqtSignal, pyqtSlot

from core.qml_typegen import GenerationError, main, module_files, render_qmltypes
from core.qml_types import QML_SINGLETONS, QML_TYPES, QML_UNCREATABLE_TYPES


class HiddenBase(QObject):
    @pyqtProperty(str, constant=True)
    def inherited(self) -> str:
        raise AssertionError("Generation must not call property getters")


class Fixture(HiddenBase):
    class Mode(IntEnum):
        Idle = 0
        Ready = 3

    pyqtEnum(Mode)  # pyright: ignore[reportArgumentType]

    changed = pyqtSignal(int, arguments=["value"])  # pyright: ignore[reportCallIssue]

    def __init__(self, _parent: QObject | None = None) -> None:
        raise AssertionError("Generation must not instantiate exported types")

    @pyqtProperty(int, notify=changed)
    def count(self) -> int:
        raise AssertionError("Generation must not call property getters")

    @pyqtProperty("QVariantMap", constant=True)
    def options(self) -> dict[str, object]:
        raise AssertionError("Generation must not call property getters")

    @pyqtSlot(str, result="QString")
    def echo(self, _value: str) -> str:
        raise AssertionError("Generation must not call slots")


class OpaqueFixture(QObject):
    @pyqtProperty(object)
    def opaque(self) -> object:
        return None


def test_every_registered_type_is_exported():
    content = render_qmltypes()
    for cls in (*QML_TYPES, *QML_UNCREATABLE_TYPES, *QML_SINGLETONS):
        assert f'exports: ["Yasb/{cls.__name__} 1.0"]' in content


def test_a_model_property_is_typed_by_its_getter_annotation():
    content = render_qmltypes()
    assert 'name: "pinnedIcons"\n            type: "IconList"' in content


def test_metadata_describes_the_api_without_constructing_objects():
    content = render_qmltypes([Fixture], ())
    assert 'exports: ["Yasb/Fixture 1.0"]' in content
    assert 'prototype: "HiddenBase"' in content
    # The unexported Python base is described so its members resolve, but QML can't create it.
    assert 'name: "HiddenBase"' in content
    assert 'name: "inherited"' in content
    assert "isCreatable: false" in content
    assert 'notify: "changed"' in content
    assert 'name: "value"' in content
    assert 'type: "QVariantMap"' in content
    assert 'name: "echo"' in content
    assert 'values: {"Idle": 0, "Ready": 3}' in content


def test_opaque_python_objects_are_rejected():
    with pytest.raises(GenerationError, match="opaque Python object"):
        render_qmltypes([OpaqueFixture], ())


def test_qmldir_declares_the_module():
    files = module_files(Path("out"), [Fixture], ())
    assert files[Path("out/Yasb/qmldir")] == "module Yasb\ntypeinfo plugins.qmltypes\ndepends QtQml 2.0\n"


def test_check_reports_stale_output_without_writing(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    arguments = ["--output-dir", str(tmp_path)]
    qmltypes = tmp_path / "Yasb" / "plugins.qmltypes"
    assert main([*arguments, "--check"]) == 1
    assert not qmltypes.exists()
    assert main(arguments) == 0
    modified = qmltypes.stat().st_mtime_ns
    assert main(arguments) == 0
    assert qmltypes.stat().st_mtime_ns == modified
    assert main([*arguments, "--check"]) == 0
    qmltypes.write_text("stale\n", encoding="utf-8")
    assert main([*arguments, "--check"]) == 1
    assert qmltypes.read_text(encoding="utf-8") == "stale\n"
    capsys.readouterr()


class PrivateFixture(QObject):
    _internal = pyqtSignal(object)

    @pyqtSlot(object)
    def _on_internal(self, _value: object) -> None:
        pass


def test_private_members_are_left_out():
    content = render_qmltypes([PrivateFixture], ())
    assert "_internal" not in content
    assert "_on_internal" not in content


class Handed(QObject):
    pass


class Owner(QObject):
    @pyqtProperty(QObject, constant=True)
    def handed(self) -> Handed:
        raise AssertionError("Generation must not call property getters")

    @pyqtProperty(QObject, constant=True)
    def other(self) -> QObject:
        raise AssertionError("Generation must not call property getters")


def test_uncreatable_types_are_exported_but_not_creatable():
    content = render_qmltypes([Owner], [Handed])
    handed = content[content.index('name: "Handed"') : content.index('name: "Owner"')]
    assert 'exports: ["Yasb/Handed 1.0"]' in handed
    assert "isCreatable: false" in handed
    assert 'name: "handed"\n            type: "Handed"' in content
    # A getter annotated with a class this file doesn't describe stays a plain QObject
    assert 'name: "other"\n            type: "QObject"' in content


def test_a_class_cannot_be_both_creatable_and_uncreatable():
    with pytest.raises(GenerationError, match="only one of creatable, uncreatable and singleton"):
        render_qmltypes([Handed], [Handed])


def test_singletons_are_exported_as_singletons():
    content = render_qmltypes([Owner], [], [Handed])
    handed = content[content.index('name: "Handed"') : content.index('name: "Owner"')]
    assert 'exports: ["Yasb/Handed 1.0"]' in handed
    assert "isCreatable: false" in handed and "isSingleton: true" in handed
    assert "isSingleton" not in content[content.index('name: "Owner"') :]
