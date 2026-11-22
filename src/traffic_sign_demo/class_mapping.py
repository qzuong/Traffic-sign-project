from __future__ import annotations

import ast
from pathlib import Path


class ClassMappingError(Exception):
    """Raised when the project training script has no usable class mapping."""


def load_class_mapping(source_path: str | Path) -> dict[int, str]:
    path = Path(source_path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        raise ClassMappingError(f"Could not read class mapping from {path}.") from exc

    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "classes"
            for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "classes":
                value = node.value

        if value is None:
            continue
        try:
            mapping = ast.literal_eval(value)
        except (ValueError, TypeError) as exc:
            raise ClassMappingError(
                f"The classes mapping in {path} is not a literal dictionary."
            ) from exc

        if (
            not isinstance(mapping, dict)
            or not mapping
            or any(
                not isinstance(key, int) or not isinstance(label, str)
                for key, label in mapping.items()
            )
            or set(mapping) != set(range(len(mapping)))
        ):
            raise ClassMappingError(f"The classes mapping in {path} is invalid.")
        return mapping

    raise ClassMappingError(f"No classes mapping was found in {path}.")
