#!/usr/bin/env python3
"""Construye notebook_alumno.ipynb y notebook_solucion.ipynb a partir de lab.py.

Uso:
    python tools/build_nb.py M2-reflection/01-ensayo-reflexion/lab.py
    python tools/build_nb.py --all          # recorre todos los lab.py del repo

Formato de lab.py: percent de Jupytext (ver CONVENCIONES.md §3).
  - Celdas `# %% [markdown] solo-profesor` o `# %% solo-profesor` se eliminan
    del notebook del alumno.
  - Bloques `### BEGIN SOLUTION` / `### END SOLUTION` dentro de una celda de
    código se reemplazan en el notebook del alumno por un placeholder. Las
    líneas `### STUDENT: ...` dentro del bloque definen un placeholder propio.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import jupytext
import nbformat

BEGIN = "### BEGIN SOLUTION"
END = "### END SOLUTION"
STUDENT = "### STUDENT:"
DEFAULT_PLACEHOLDER = [
    "# ======== TU CÓDIGO ACÁ ========",
    'raise NotImplementedError("Completá esta función")',
]

REPO_ROOT = Path(__file__).resolve().parent.parent


class BuildError(Exception):
    pass


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def student_source(code: str, where: str) -> str:
    """Devuelve el código con los bloques de solución reemplazados."""
    out: list[str] = []
    in_block = False
    student_lines: list[str] = []
    block_indent = ""
    for n, line in enumerate(code.splitlines(), start=1):
        stripped = line.strip()
        if stripped == BEGIN:
            if in_block:
                raise BuildError(f"{where}:{n}: BEGIN SOLUTION anidado")
            in_block = True
            student_lines = []
            block_indent = _indent_of(line)
            continue
        if stripped == END:
            if not in_block:
                raise BuildError(f"{where}:{n}: END SOLUTION sin BEGIN")
            in_block = False
            if student_lines:
                out.extend(student_lines)
            else:
                out.extend(block_indent + p for p in DEFAULT_PLACEHOLDER)
            continue
        if in_block:
            if stripped.startswith(STUDENT):
                payload = stripped[len(STUDENT):]
                if payload.startswith(" "):
                    payload = payload[1:]
                student_lines.append(block_indent + payload)
            continue
        out.append(line)
    if in_block:
        raise BuildError(f"{where}: falta END SOLUTION")
    return "\n".join(out)


def solution_source(code: str) -> str:
    """Quita los marcadores y las líneas STUDENT; deja la solución."""
    out = []
    for line in code.splitlines():
        s = line.strip()
        if s in (BEGIN, END) or s.startswith(STUDENT):
            continue
        out.append(line)
    return "\n".join(out)


def _is_teacher_only(cell) -> bool:
    tags = cell.get("metadata", {}).get("tags", []) or []
    if "solo-profesor" in tags:
        return True
    # jupytext guarda `# %% [markdown] solo-profesor` como título de celda
    title = cell.get("metadata", {}).get("title", "")
    return "solo-profesor" in str(title)


def build(lab_py: Path) -> tuple[Path, Path]:
    text = lab_py.read_text(encoding="utf-8")
    nb = jupytext.reads(text, fmt="py:percent")
    where = str(lab_py.relative_to(REPO_ROOT)) if lab_py.is_relative_to(REPO_ROOT) else str(lab_py)

    n_gaps = text.count(BEGIN)
    if n_gaps != text.count(END):
        raise BuildError(f"{where}: BEGIN/END SOLUTION desbalanceados")

    sol = nbformat.v4.new_notebook()
    alu = nbformat.v4.new_notebook()
    kernel = {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"},
    }
    sol.metadata.update(kernel)
    alu.metadata.update(kernel)

    for cell in nb.cells:
        meta = {k: v for k, v in cell.get("metadata", {}).items() if k not in ("title",)}
        if cell.cell_type == "markdown":
            c_sol = nbformat.v4.new_markdown_cell(cell.source, metadata=meta)
            sol.cells.append(c_sol)
            if not _is_teacher_only(cell):
                alu.cells.append(nbformat.v4.new_markdown_cell(cell.source, metadata=meta))
        elif cell.cell_type == "code":
            sol.cells.append(nbformat.v4.new_code_cell(solution_source(cell.source), metadata=meta))
            if not _is_teacher_only(cell):
                alu.cells.append(
                    nbformat.v4.new_code_cell(student_source(cell.source, where), metadata=meta)
                )
        else:  # raw
            sol.cells.append(cell)
            if not _is_teacher_only(cell):
                alu.cells.append(cell)

    for notebook in (sol, alu):
        nbformat.validate(notebook)

    out_sol = lab_py.with_name("notebook_solucion.ipynb")
    out_alu = lab_py.with_name("notebook_alumno.ipynb")
    nbformat.write(sol, out_sol)
    nbformat.write(alu, out_alu)
    return out_alu, out_sol


def check_compiles(nb_path: Path) -> list[str]:
    """Compila cada celda de código (sin ejecutarla). Devuelve errores."""
    nb = nbformat.read(nb_path, as_version=4)
    errors = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        src = cell.source
        # ignorar magics y shell
        src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!")))
        try:
            compile(src, f"{nb_path.name}[celda {i}]", "exec")
        except SyntaxError as e:
            errors.append(f"{nb_path.name} celda {i}: {e}")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="rutas a lab.py")
    ap.add_argument("--all", action="store_true", help="todos los lab.py del repo")
    args = ap.parse_args(argv)

    paths = [Path(p).resolve() for p in args.paths]
    if args.all:
        paths += sorted(p for p in REPO_ROOT.rglob("lab.py") if "tools" not in p.parts)
    if not paths:
        ap.error("indicá rutas o --all")

    failures = 0
    for lab in paths:
        try:
            alu, sol = build(lab)
        except BuildError as e:
            print(f"ERROR  {e}")
            failures += 1
            continue
        errs = check_compiles(sol) + check_compiles(alu)
        gaps = lab.read_text(encoding="utf-8").count(BEGIN)
        status = "OK   " if not errs else "FALLA"
        print(f"{status}  {lab.relative_to(REPO_ROOT)}  ({gaps} huecos)")
        for e in errs:
            print(f"        {e}")
        failures += bool(errs)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
