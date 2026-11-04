import pytest
from PyQt6.QtCore import QByteArray, QObject, QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.utils.environment import Environment
from settings import QML_IMPORT_PATH


def test_a_variable_is_read_and_an_unset_one_is_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YASB_TEST_TOKEN", "from-the-environment")
    monkeypatch.delenv("YASB_TEST_UNSET", raising=False)
    environment = Environment()
    assert environment.value("YASB_TEST_TOKEN") == "from-the-environment"
    assert environment.value("YASB_TEST_UNSET") == ""


def test_qml_reads_a_variable_by_the_singleton(qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YASB_TEST_TOKEN", "from-the-environment")
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine)
    component.setData(
        QByteArray(
            b'import QtQml\nimport Yasb\nQtObject { property string token: Environment.value("YASB_TEST_TOKEN") }'
        ),
        QUrl(),
    )
    item = component.create()
    assert isinstance(item, QObject), [error.toString() for error in component.errors()]
    assert item.property("token") == "from-the-environment"
