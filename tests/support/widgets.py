from pathlib import Path


def write_widget(folder: Path, name: str, source: str) -> Path:
    path = folder / name / f"{name}.qml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path
