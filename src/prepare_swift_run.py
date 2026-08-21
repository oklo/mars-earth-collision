#!/usr/bin/env python3
"""Stage one archived SWIFT configuration in a self-contained run directory.

The committed YAML files preserve the paths used by the original calculation.
This helper copies a selected YAML, rewrites its ANEOS-table paths, and links
the corresponding compact IC and optional output-time list into a run directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
EOS_KEYS = (
    "planetary_ANEOS_forsterite_table_file",
    "planetary_ANEOS_Fe85Si15_table_file",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Archived YAML configuration")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--eos-dir",
        type=Path,
        required=True,
        help="Directory containing the SWIFT planetary ANEOS tables",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing staged configuration or links",
    )
    return parser.parse_args()


def setting_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(\S+)", text)
    return match.group(1) if match else None


def replace_setting(text: str, key: str, value: Path) -> str:
    pattern = rf"(?m)^(\s*{re.escape(key)}:\s*)\S+"
    updated, count = re.subn(pattern, rf"\g<1>{value}", text)
    if count != 1:
        raise SystemExit(f"Expected exactly one {key!r} setting; found {count}")
    return updated


def link_input(source: Path, destination: Path, force: bool) -> None:
    if destination.exists() or destination.is_symlink():
        if not force:
            raise SystemExit(f"Destination already exists: {destination}")
        destination.unlink()
    destination.symlink_to(source.resolve())


def main() -> None:
    args = parse_args()
    config = args.config.resolve()
    eos_dir = args.eos_dir.resolve()
    run_dir = args.run_dir.resolve()
    if not config.is_file():
        raise SystemExit(f"Configuration not found: {config}")
    if not eos_dir.is_dir():
        raise SystemExit(f"EOS directory not found: {eos_dir}")

    text = config.read_text()
    for key in EOS_KEYS:
        old_value = setting_value(text, key)
        if old_value is None:
            continue
        table = eos_dir / Path(old_value).name
        if not table.is_file():
            raise SystemExit(f"EOS table not found: {table}")
        text = replace_setting(text, key, table)

    run_dir.mkdir(parents=True, exist_ok=True)
    staged_config = run_dir / config.name
    if staged_config.exists() and not args.force:
        raise SystemExit(f"Staged configuration already exists: {staged_config}")
    staged_config.write_text(text)

    ic_name = setting_value(text, "file_name")
    if ic_name:
        ic_source = REPO_ROOT / "data" / Path(ic_name).name
        if not ic_source.is_file():
            raise SystemExit(f"Compact IC not found in data/: {ic_source.name}")
        link_input(ic_source, run_dir / Path(ic_name).name, args.force)

    output_list = setting_value(text, "output_list")
    if output_list:
        list_source = REPO_ROOT / "configs" / Path(output_list).name
        if not list_source.is_file():
            raise SystemExit(f"Output-time list not found in configs/: {list_source.name}")
        link_input(list_source, run_dir / Path(output_list).name, args.force)

    print(staged_config)


if __name__ == "__main__":
    main()
