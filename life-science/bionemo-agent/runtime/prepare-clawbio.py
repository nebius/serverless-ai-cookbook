#!/usr/bin/env python3
"""Validate and sanitize the pinned ClawBio runtime for redistribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import yaml


EXPECTED_SOURCE_COMMIT = "794dd1f5aacc1af308694c9b2f7966d0e396916e"
EXPECTED_UPSTREAM_SKILLS = 97
EXPECTED_UPSTREAM_CATALOG = 96
EXPECTED_DISTRIBUTED_SKILLS = 95
PROPRIETARY_SKILLS = frozenset({"wes-clinical-report-en", "wes-clinical-report-es"})
REMOVED_DATA = (
    "genome-compare/data/manuel_ancestry.json",
)
REMOVED_DIRECTORY_NAMES = frozenset({
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "evals",
    "tests",
})
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def frontmatter(skill_file: Path) -> dict:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing YAML frontmatter: {skill_file}")
    try:
        raw = text.split("\n---\n", 1)[0][4:]
    except IndexError as exc:
        raise ValueError(f"unterminated YAML frontmatter: {skill_file}") from exc
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"frontmatter is not a mapping: {skill_file}")
    return parsed


def skill_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file())


def reject_links(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed in the distributed skill tree: {path}")


def prune_runtime_tree(root: Path) -> None:
    for skill in PROPRIETARY_SKILLS:
        shutil.rmtree(root / skill, ignore_errors=True)
    for relative in REMOVED_DATA:
        (root / relative).unlink(missing_ok=True)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir() and path.name in REMOVED_DIRECTORY_NAMES:
            shutil.rmtree(path)
        elif path.is_file() and (path.suffix == ".pyc" or path.name == ".env" or path.name.startswith(".env.")):
            path.unlink()


def sanitize_catalog(root: Path) -> dict:
    catalog_path = root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = catalog.get("skills")
    if not isinstance(entries, list) or catalog.get("skill_count") != EXPECTED_UPSTREAM_CATALOG:
        raise ValueError("unexpected upstream ClawBio catalog shape or count")
    if len(entries) != EXPECTED_UPSTREAM_CATALOG:
        raise ValueError("upstream ClawBio catalog entry count drifted")
    catalog["skills"] = [entry for entry in entries if entry.get("name") not in PROPRIETARY_SKILLS]
    catalog["skill_count"] = len(catalog["skills"])
    catalog["distribution"] = {
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "excluded_skills": sorted(PROPRIETARY_SKILLS),
        "policy": "public-image-redistributable-only",
    }
    catalog_path.write_text(f"{json.dumps(catalog, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    return catalog


def validate_skills(root: Path) -> tuple[list[str], dict[str, str]]:
    reject_links(root)
    names: list[str] = []
    hashes: dict[str, str] = {}
    for directory in skill_dirs(root):
        spec = directory / "SKILL.md"
        metadata = frontmatter(spec)
        name = metadata.get("name")
        description = metadata.get("description")
        if name != directory.name or not NAME_PATTERN.fullmatch(str(name)):
            raise ValueError(f"invalid or mismatched skill name: {directory}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"missing skill description: {directory}")
        if spec.stat().st_size > 65_536:
            raise ValueError(f"skill contract exceeds 65,536 bytes: {directory}")
        if str(metadata.get("license", "")).upper() == "PROPRIETARY" or metadata.get("private") is True:
            raise ValueError(f"proprietary skill survived redistribution filter: {directory}")
        names.append(name)
        hashes[name] = hashlib.sha256(spec.read_bytes()).hexdigest()
    if len(names) != EXPECTED_DISTRIBUTED_SKILLS or len(set(names)) != len(names):
        raise ValueError(f"expected {EXPECTED_DISTRIBUTED_SKILLS} unique distributed skills, found {len(names)}")
    return names, hashes


def find_clawbio_package(venv: Path) -> Path:
    matches = sorted(venv.glob("lib/python*/site-packages/clawbio"))
    if len(matches) != 1:
        raise ValueError(f"expected one installed clawbio package, found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    if args.commit != EXPECTED_SOURCE_COMMIT:
        raise SystemExit(f"refusing unexpected ClawBio source commit: {args.commit}")

    package = find_clawbio_package(args.venv)
    root = package / "skills"
    upstream_names = [path.name for path in skill_dirs(root)]
    if len(upstream_names) != EXPECTED_UPSTREAM_SKILLS:
        raise SystemExit(f"expected {EXPECTED_UPSTREAM_SKILLS} upstream skills, found {len(upstream_names)}")
    if not PROPRIETARY_SKILLS.issubset(upstream_names):
        raise SystemExit("upstream proprietary-skill inventory drifted")

    prune_runtime_tree(root)
    catalog = sanitize_catalog(root)
    names, hashes = validate_skills(root)
    if {entry["name"] for entry in catalog["skills"]} != set(names):
        raise SystemExit("sanitized ClawBio catalog and skill directories differ")

    share = args.venv / "share" / "clawbio"
    share.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.source / "LICENSE", share / "LICENSE")
    shutil.copy2("/usr/share/common-licenses/Apache-2.0", share / "Apache-2.0")
    shutil.copy2("/usr/share/common-licenses/GPL-3", share / "GPL-3.0")
    manifest = {
        "source": "https://github.com/ClawBio/ClawBio",
        "sourceCommit": args.commit,
        "upstreamSkillCount": EXPECTED_UPSTREAM_SKILLS,
        "upstreamCatalogCount": EXPECTED_UPSTREAM_CATALOG,
        "distributedSkillCount": len(names),
        "distributedCatalogCount": len(catalog["skills"]),
        "excludedSkills": sorted(PROPRIETARY_SKILLS),
        "removedData": list(REMOVED_DATA),
        "skillNames": names,
        "skillContractSha256": hashes,
    }
    (share / "image-manifest.json").write_text(
        f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n",
        encoding="utf-8",
    )

    for path in args.venv.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path)
    for path in args.venv.rglob("*.pyc"):
        path.unlink(missing_ok=True)
    for path in args.venv.rglob("*"):
        if path.is_symlink() and path.is_relative_to(root):
            raise SystemExit(f"unexpected skill-tree symlink after sanitization: {path}")
    os.chmod(root / "catalog.json", 0o444)


if __name__ == "__main__":
    main()
