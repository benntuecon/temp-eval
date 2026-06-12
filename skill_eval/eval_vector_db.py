"""Vector DB integration for PR/Jira-backed skill eval cases.

Architecture:

    PR/Jira task description
        -> embedding
        -> Chroma vector DB
        -> metadata stores repo_path, before_hash, after_hash, skill paths
        -> retrieved case becomes RunConfig
        -> run_eval / run_batch can execute it

CLI examples:

    uv run python -m skill_eval.eval_vector_db init-template cases.json

    uv run python -m skill_eval.eval_vector_db build-json cases.json --reset

    uv run python -m skill_eval.eval_vector_db query "fix max function"

    uv run python -m skill_eval.eval_vector_db run-query "fix max function" --top-k 1 --simulated
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from skill_eval.contracts import RunConfig

DEFAULT_DB_DIR = ".vectordb/chroma"
DEFAULT_COLLECTION = "skill_eval_cases"
DEFAULT_MODELS = ("claude-haiku-4-5",)


@dataclass(frozen=True)
class EvalCase:
    """One searchable PR/Jira eval case.

    The description is embedded.
    Everything else is metadata used to reconstruct RunConfig.
    """

    case_id: str
    description: str
    repo_path: str
    before_hash: str
    after_hash: str
    baseline_skill_path: str
    challenger_skill_path: str
    jira_key: str = ""
    models: tuple[str, ...] = DEFAULT_MODELS
    max_turns: int = 30
    max_tokens: int | None = None
    wall_clock_seconds: int | None = None
    thinking_budget: int | None = None

    def to_run_config(self) -> RunConfig:
        return RunConfig(
            before_hash=self.before_hash,
            after_hash=self.after_hash,
            repo_path=self.repo_path,
            task_brief=self.description,
            baseline_skill_path=self.baseline_skill_path,
            challenger_skill_path=self.challenger_skill_path,
            models=self.models,
            max_turns=self.max_turns,
            max_tokens=self.max_tokens,
            wall_clock_seconds=self.wall_clock_seconds,
            thinking_budget=self.thinking_budget,
        )


def _client(db_dir: str = DEFAULT_DB_DIR):
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=db_dir)


def _collection(
    db_dir: str = DEFAULT_DB_DIR,
    collection_name: str = DEFAULT_COLLECTION,
):
    client = _client(db_dir)
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "Skill eval PR/Jira cases"},
    )


def _reset_db(db_dir: str) -> None:
    path = Path(db_dir)
    if path.exists():
        shutil.rmtree(path)


def _metadata_from_case(case: EvalCase) -> dict[str, Any]:
    """Chroma metadata supports only scalar values, so tuples become JSON strings."""
    return {
        "case_id": case.case_id,
        "jira_key": case.jira_key,
        "description": case.description,
        "repo_path": case.repo_path,
        "before_hash": case.before_hash,
        "after_hash": case.after_hash,
        "baseline_skill_path": case.baseline_skill_path,
        "challenger_skill_path": case.challenger_skill_path,
        "models_json": json.dumps(list(case.models)),
        "max_turns": case.max_turns,
        "max_tokens_json": json.dumps(case.max_tokens),
        "wall_clock_seconds_json": json.dumps(case.wall_clock_seconds),
        "thinking_budget_json": json.dumps(case.thinking_budget),
    }


def _case_from_metadata(metadata: dict[str, Any]) -> EvalCase:
    return EvalCase(
        case_id=str(metadata["case_id"]),
        jira_key=str(metadata.get("jira_key") or ""),
        description=str(metadata["description"]),
        repo_path=str(metadata["repo_path"]),
        before_hash=str(metadata["before_hash"]),
        after_hash=str(metadata["after_hash"]),
        baseline_skill_path=str(metadata["baseline_skill_path"]),
        challenger_skill_path=str(metadata["challenger_skill_path"]),
        models=tuple(json.loads(str(metadata.get("models_json") or '["claude-haiku-4-5"]'))),
        max_turns=int(metadata.get("max_turns") or 30),
        max_tokens=json.loads(str(metadata.get("max_tokens_json") or "null")),
        wall_clock_seconds=json.loads(str(metadata.get("wall_clock_seconds_json") or "null")),
        thinking_budget=json.loads(str(metadata.get("thinking_budget_json") or "null")),
    )


def load_cases_from_json(path: str) -> list[EvalCase]:
    raw = json.loads(Path(path).read_text())

    if not isinstance(raw, list):
        raise ValueError("cases.json must contain a JSON list of case objects")

    cases: list[EvalCase] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each item in cases.json must be an object")

        models_raw = item.get("models", list(DEFAULT_MODELS))
        if isinstance(models_raw, str):
            models = (models_raw,)
        else:
            models = tuple(models_raw)

        cases.append(
            EvalCase(
                case_id=str(item["case_id"]),
                jira_key=str(item.get("jira_key") or ""),
                description=str(item["description"]),
                repo_path=str(item["repo_path"]),
                before_hash=str(item["before_hash"]),
                after_hash=str(item["after_hash"]),
                baseline_skill_path=str(item["baseline_skill_path"]),
                challenger_skill_path=str(item["challenger_skill_path"]),
                models=models,
                max_turns=int(item.get("max_turns") or 30),
                max_tokens=item.get("max_tokens"),
                wall_clock_seconds=item.get("wall_clock_seconds"),
                thinking_budget=item.get("thinking_budget"),
            )
        )

    return cases


def write_template(path: str) -> None:
    template = [
        {
            "case_id": "PR_123",
            "jira_key": "AI-123",
            "description": (
                "Information about git PR_123 and the corresponding Jira story. "
                "The change fixes validation logic for skill evaluation results."
            ),
            "repo_path": "/Users/prajwal/path/to/repo",
            "before_hash": "PUT_BEFORE_COMMIT_HASH_HERE",
            "after_hash": "PUT_AFTER_COMMIT_HASH_HERE",
            "baseline_skill_path": "/Users/prajwal/path/to/baseline/skill",
            "challenger_skill_path": "/Users/prajwal/path/to/challenger/skill",
            "models": ["claude-haiku-4-5"],
            "max_turns": 30,
            "max_tokens": None,
            "wall_clock_seconds": None,
            "thinking_budget": None,
        }
    ]
    Path(path).write_text(json.dumps(template, indent=2) + "\n")


def index_cases(
    cases: list[EvalCase],
    *,
    db_dir: str = DEFAULT_DB_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    reset: bool = False,
) -> None:
    if reset:
        _reset_db(db_dir)

    collection = _collection(db_dir, collection_name)

    if not cases:
        print("No cases to index.")
        return

    ids = [case.case_id for case in cases]
    documents = [case.description for case in cases]
    metadatas = [_metadata_from_case(case) for case in cases]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"Indexed {len(cases)} case(s) into {db_dir}/{collection_name}")


def query_cases(
    query: str,
    *,
    top_k: int = 5,
    db_dir: str = DEFAULT_DB_DIR,
    collection_name: str = DEFAULT_COLLECTION,
) -> list[tuple[EvalCase, float | None]]:
    collection = _collection(db_dir, collection_name)

    result = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    # ``or [[]]`` guards a key present with value None (chroma version drift);
    # strict zip makes a parallel-array length mismatch loud instead of
    # silently pairing cases with the wrong distances.
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    matches: list[tuple[EvalCase, float | None]] = []
    for metadata, distance in zip(metadatas, distances, strict=True):
        matches.append((_case_from_metadata(metadata), distance))

    return matches


def build_sample_vector_db(
    *,
    base_dir: str = ".skill-eval-cases",
    db_dir: str = DEFAULT_DB_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    reset: bool = False,
) -> None:
    """Build the existing sample repos, then index them into the vector DB."""
    from skill_eval.sample_cases import build_sample_cases

    base = Path(base_dir)
    if reset and base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    cfgs = build_sample_cases(str(base))

    cases = []
    for i, cfg in enumerate(cfgs, start=1):
        case_id = f"sample_case_{i:02d}"
        cases.append(
            EvalCase(
                case_id=case_id,
                jira_key=f"SAMPLE-{i:03d}",
                description=cfg.task_brief,
                repo_path=cfg.repo_path,
                before_hash=cfg.before_hash,
                after_hash=cfg.after_hash,
                baseline_skill_path=cfg.baseline_skill_path,
                challenger_skill_path=cfg.challenger_skill_path,
                models=cfg.models,
                max_turns=cfg.max_turns,
                max_tokens=cfg.max_tokens,
                wall_clock_seconds=cfg.wall_clock_seconds,
                thinking_budget=cfg.thinking_budget,
            )
        )

    index_cases(cases, db_dir=db_dir, collection_name=collection_name, reset=reset)


def _print_matches(matches: list[tuple[EvalCase, float | None]]) -> None:
    if not matches:
        print("No matches found.")
        return

    for i, (case, distance) in enumerate(matches, start=1):
        print("=" * 88)
        print(f"{i}. {case.case_id}")
        if case.jira_key:
            print(f"jira_key: {case.jira_key}")
        print(f"distance: {distance}")
        print(f"description: {case.description}")
        print(f"repo_path: {case.repo_path}")
        print(f"before_hash: {case.before_hash}")
        print(f"after_hash: {case.after_hash}")
        print(f"baseline_skill_path: {case.baseline_skill_path}")
        print(f"challenger_skill_path: {case.challenger_skill_path}")


def _run_retrieved_cases(
    matches: list[tuple[EvalCase, float | None]],
    *,
    simulated: bool,
    max_cases: int,
) -> None:
    from skill_eval.batch import run_batch
    from skill_eval.reporting import verdict_line

    if simulated:
        from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker

        taker_fn = sim_run_taker
        simulator_factory = sim_make_simulator
        judge_fn = sim_run_judge
    else:
        taker_fn = None
        simulator_factory = None
        judge_fn = None

    cfgs = [case.to_run_config() for case, _distance in matches]

    reports = run_batch(
        cfgs,
        taker_fn=taker_fn,
        simulator_factory=simulator_factory,
        judge_fn=judge_fn,
        max_cases=max_cases,
    )

    for case_number, (case, _distance) in enumerate(matches, start=1):
        print("=" * 88)
        print(f"CASE {case_number}: {case.case_id}")
        print(f"TASK: {case.description}")
        print(verdict_line(reports[case_number - 1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill eval vector DB CLI")
    parser.add_argument("--db-dir", default=DEFAULT_DB_DIR)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)

    sub = parser.add_subparsers(dest="command", required=True)

    init_template = sub.add_parser("init-template", help="Create a starter cases.json")
    init_template.add_argument("path", help="Output path, usually cases.json")

    build_json = sub.add_parser("build-json", help="Index eval cases from cases.json")
    build_json.add_argument("path", help="Path to cases.json")
    build_json.add_argument("--reset", action="store_true")

    build_samples = sub.add_parser("build-samples", help="Build and index sample eval cases")
    build_samples.add_argument("--base-dir", default=".skill-eval-cases")
    build_samples.add_argument("--reset", action="store_true")

    query = sub.add_parser("query", help="Search vector DB")
    query.add_argument("text")
    query.add_argument("--top-k", type=int, default=5)

    run_query = sub.add_parser("run-query", help="Search vector DB, then run eval on matches")
    run_query.add_argument("text")
    run_query.add_argument("--top-k", type=int, default=1)
    run_query.add_argument("--max-cases", type=int, default=1)
    run_query.add_argument(
        "--simulated",
        action="store_true",
        help="Use simulated taker/judge/simulator instead of real agents",
    )

    args = parser.parse_args()

    if args.command == "init-template":
        write_template(args.path)
        print(f"Wrote template to {args.path}")
        return

    if args.command == "build-json":
        cases = load_cases_from_json(args.path)
        index_cases(
            cases,
            db_dir=args.db_dir,
            collection_name=args.collection,
            reset=args.reset,
        )
        return

    if args.command == "build-samples":
        build_sample_vector_db(
            base_dir=args.base_dir,
            db_dir=args.db_dir,
            collection_name=args.collection,
            reset=args.reset,
        )
        return

    if args.command == "query":
        matches = query_cases(
            args.text,
            top_k=args.top_k,
            db_dir=args.db_dir,
            collection_name=args.collection,
        )
        _print_matches(matches)
        return

    if args.command == "run-query":
        matches = query_cases(
            args.text,
            top_k=args.top_k,
            db_dir=args.db_dir,
            collection_name=args.collection,
        )
        _print_matches(matches)
        _run_retrieved_cases(
            matches,
            simulated=args.simulated,
            max_cases=args.max_cases,
        )
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()