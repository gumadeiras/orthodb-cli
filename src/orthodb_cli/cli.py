from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .cache import (
    cache_status,
    default_cache_dir,
    download_entry,
    fetch_manifest,
    load_manifest,
    resolve_dataset,
    save_manifest,
)
from .client import API_BASE, OrthoDBClient
from .db import db_status, index_cache
from .errors import OrthoDBError
from .identify import identify
from .local import export_ndjson, gene_search, og_search, ortholog_gene_ids, species_search

SYNC_PROFILES = {
    "minimal": ("species", "levels", "level2species"),
    "annotations": ("species", "levels", "ogs", "og_xrefs"),
    "orthologs": ("species", "levels", "ogs", "og2genes"),
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = OrthoDBClient(base_url=args.api_base, timeout=args.timeout)
    cache_dir = Path(args.cache_dir).expanduser()
    try:
        result = args.handler(args, client, cache_dir)
    except OrthoDBError as exc:
        print(f"orthodb: error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("orthodb: interrupted", file=sys.stderr)
        return 130

    if result is not None:
        emit(result, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orthodb", description="Query and cache OrthoDB data.")
    parser.add_argument("--version", action="version", version=f"orthodb-cli {__version__}")
    parser.add_argument("--api-base", default=API_BASE, help=f"OrthoDB API base URL. Default: {API_BASE}")
    parser.add_argument("--cache-dir", default=str(default_cache_dir()), help="Cache directory.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    parser.add_argument("--output", choices=["json", "text"], default="json", help="Output format.")

    subcommands = parser.add_subparsers(dest="command", required=True)
    add_api_commands(subcommands)
    add_cache_commands(subcommands)
    add_local_commands(subcommands)
    add_export_commands(subcommands)
    add_resolve_commands(subcommands)
    return parser


def add_api_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    version = subcommands.add_parser("version", help="Print the OrthoDB API release id.")
    version.set_defaults(handler=cmd_version)

    search = subcommands.add_parser("search", help="Search orthologous groups.")
    search.add_argument("query", nargs="?", help="Text query.")
    search.add_argument("--gid")
    search.add_argument("--ncbi")
    search.add_argument("--species")
    search.add_argument("--level")
    search.add_argument("--universal")
    search.add_argument("--singlecopy")
    search.add_argument("--skip", type=int)
    search.add_argument("--take", type=int)
    search.add_argument("--counts-only", action="store_true")
    search.set_defaults(handler=cmd_search)

    genesearch = subcommands.add_parser("genesearch", help="Search genes.")
    genesearch.add_argument("query", nargs="?")
    genesearch.add_argument("--gid")
    genesearch.add_argument("--ncbi")
    genesearch.add_argument("--skip", type=int)
    genesearch.add_argument("--take", type=int)
    genesearch.set_defaults(handler=cmd_genesearch)

    group = subcommands.add_parser("group", help="Fetch OG annotation.")
    group.add_argument("id")
    group.set_defaults(handler=cmd_group)

    orthologs = subcommands.add_parser("orthologs", help="Fetch orthologs for an OG/gene or species pair.")
    orthologs.add_argument("id", nargs="?")
    orthologs.add_argument("--species")
    orthologs.add_argument("--species2")
    orthologs.add_argument("--clade")
    orthologs.set_defaults(handler=cmd_orthologs)

    details = subcommands.add_parser("details", help="Fetch gene details.")
    details.add_argument("id")
    details.set_defaults(handler=cmd_details)

    siblings = subcommands.add_parser("siblings", help="Fetch sibling OGs.")
    siblings.add_argument("id")
    siblings.add_argument("--take", type=int)
    siblings.set_defaults(handler=cmd_siblings)

    species = subcommands.add_parser("species", help="Fetch OrthoDB organisms.")
    species.add_argument("--clade")
    species.add_argument("--level")
    species.set_defaults(handler=cmd_species)

    tree = subcommands.add_parser("tree", help="Fetch the OrthoDB taxonomy tree.")
    tree.set_defaults(handler=lambda args, client, cache_dir: client.request("tree"))

    blast = subcommands.add_parser("blast", help="Find best gene match for a protein sequence.")
    blast.add_argument("seq", help="Protein sequence, no FASTA header.")
    blast.set_defaults(handler=lambda args, client, cache_dir: client.request("blast", {"seq": args.seq}))

    fasta = subcommands.add_parser("fasta", help="Fetch FASTA for a gene, OG, or species.")
    fasta.add_argument("id", nargs="?")
    fasta.add_argument("--species")
    fasta.add_argument("--seqtype", choices=["protein", "cds"])
    fasta.add_argument("--output", dest="file_output")
    fasta.set_defaults(handler=cmd_fasta)

    tab = subcommands.add_parser("tab", help="Fetch tab-delimited gene annotation for an OG.")
    tab.add_argument("id")
    tab.add_argument("--species")
    tab.add_argument("--output", dest="file_output")
    tab.set_defaults(handler=cmd_tab)

    api = subcommands.add_parser("api", help="Call a raw OrthoDB API command.")
    api.add_argument("api_command")
    api.add_argument("params", nargs="*", help="key=value parameters.")
    api.set_defaults(handler=cmd_api)


def add_cache_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    cache = subcommands.add_parser("cache", help="Manage the flat-file cache.")
    cache_sub = cache.add_subparsers(dest="cache_command", required=True)

    manifest = cache_sub.add_parser("manifest", help="Fetch and print the flat-file manifest.")
    manifest.add_argument("--refresh", action="store_true")
    manifest.set_defaults(handler=cmd_cache_manifest)

    status = cache_sub.add_parser("status", help="Show downloaded cache files.")
    status.add_argument("--refresh", action="store_true")
    status.set_defaults(handler=cmd_cache_status)

    plan = cache_sub.add_parser("plan", help="Show what a sync profile would download.")
    plan.add_argument("profile", choices=sorted(SYNC_PROFILES))
    plan.add_argument("--include-large", action="store_true", help="Include downloads larger than 1 GB in the plan.")
    plan.set_defaults(handler=cmd_cache_plan)

    download = cache_sub.add_parser("download", help="Download one manifest dataset by alias or filename.")
    download.add_argument("dataset")
    download.add_argument("--no-verify", action="store_true")
    download.set_defaults(handler=cmd_cache_download)

    sync = cache_sub.add_parser("sync", help="Download a curated dataset profile.")
    sync.add_argument("profile", choices=sorted(SYNC_PROFILES))
    sync.add_argument("--include-large", action="store_true", help="Allow downloads larger than 1 GB.")
    sync.add_argument("--index", action="store_true", help="Index downloaded supported tables into SQLite.")
    sync.set_defaults(handler=cmd_cache_sync)

    index = cache_sub.add_parser("index", help="Index downloaded flat files into SQLite.")
    index.add_argument("datasets", nargs="*", choices=sorted({"all", *SYNC_PROFILES["orthologs"], "genes"}))
    index.set_defaults(handler=cmd_cache_index)

    db = cache_sub.add_parser("db", help="Show SQLite index status.")
    db.set_defaults(handler=lambda args, client, cache_dir: db_status(cache_dir))

    where = cache_sub.add_parser("dir", help="Print the cache directory.")
    where.set_defaults(handler=lambda args, client, cache_dir: str(cache_dir))


def add_local_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    local = subcommands.add_parser("local", help="Query downloaded flat files.")
    local_sub = local.add_subparsers(dest="local_command", required=True)

    species = local_sub.add_parser("species", help="Search cached species records.")
    species.add_argument("query")
    species.add_argument("--limit", type=int, default=20)
    species.set_defaults(handler=lambda args, client, cache_dir: species_search(cache_dir, args.query, args.limit))

    og = local_sub.add_parser("og", help="Search indexed orthologous groups.")
    og.add_argument("query")
    og.add_argument("--limit", type=int, default=20)
    og.set_defaults(handler=lambda args, client, cache_dir: og_search(cache_dir, args.query, args.limit))

    gene = local_sub.add_parser("gene", help="Search indexed genes.")
    gene.add_argument("query")
    gene.add_argument("--limit", type=int, default=20)
    gene.set_defaults(handler=lambda args, client, cache_dir: gene_search(cache_dir, args.query, args.limit))

    orthologs = local_sub.add_parser("orthologs", help="List indexed genes in an OG.")
    orthologs.add_argument("og_id")
    orthologs.add_argument("--limit", type=int, default=10_000)
    orthologs.set_defaults(handler=lambda args, client, cache_dir: ortholog_gene_ids(cache_dir, args.og_id, args.limit))


def add_export_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    export = subcommands.add_parser("export", help="Export indexed local data.")
    export.add_argument("table", choices=["species", "levels", "ogs", "og2genes", "genes"])
    export.add_argument("--query", help="Optional full-text/substring filter.")
    export.add_argument("--limit", type=int, default=1_000)
    export.add_argument("--output", dest="file_output")
    export.set_defaults(handler=cmd_export)


def add_resolve_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    resolve = subcommands.add_parser("resolve", help="Classify an OrthoDB id or query string.")
    resolve.add_argument("value")
    resolve.set_defaults(handler=lambda args, client, cache_dir: identify(args.value, cache_dir))


def cmd_version(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> str:
    return client.request("orthodb_release_id").strip().strip('"')


def cmd_search(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request(
        "search",
        {
            "query": args.query,
            "gid": args.gid,
            "ncbi": args.ncbi,
            "species": args.species,
            "level": args.level,
            "universal": args.universal,
            "singlecopy": args.singlecopy,
            "skip": args.skip,
            "take": args.take,
            "counts_only": args.counts_only or None,
        },
    )


def cmd_genesearch(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request(
        "genesearch",
        {"query": args.query, "gid": args.gid, "ncbi": args.ncbi, "skip": args.skip, "take": args.take},
    )


def cmd_group(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request("group", {"id": args.id})


def cmd_orthologs(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request(
        "orthologs",
        {"id": args.id, "species": args.species, "species2": args.species2, "clade": args.clade},
    )


def cmd_details(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request("ogdetails", {"id": args.id})


def cmd_siblings(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request("siblings", {"id": args.id, "take": args.take})


def cmd_species(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    return client.request("species", {"clade": args.clade, "level": args.level})


def cmd_fasta(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    text = client.request("fasta", {"id": args.id, "species": args.species, "seqtype": args.seqtype})
    return write_or_return_text(text, args.file_output)


def cmd_tab(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    text = client.request("tab", {"id": args.id, "species": args.species})
    return write_or_return_text(text, args.file_output)


def cmd_api(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    params: dict[str, str] = {}
    for item in args.params:
        if "=" not in item:
            raise OrthoDBError(f"raw API params must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        params[key] = value
    return client.request(args.api_command, params)


def cmd_cache_manifest(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    entries = fetch_manifest() if args.refresh else load_manifest(cache_dir)
    save_manifest(entries, cache_dir)
    return [entry.__dict__ for entry in entries]


def cmd_cache_status(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    entries = fetch_manifest() if args.refresh else load_manifest(cache_dir)
    if args.refresh:
        save_manifest(entries, cache_dir)
    return cache_status(cache_dir, entries)


def cmd_cache_plan(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    entries = load_manifest(cache_dir)
    plan = []
    for dataset in SYNC_PROFILES[args.profile]:
        entry = resolve_dataset(entries, dataset)
        path = cache_dir / entry.name
        large = is_large(entry.size)
        plan.append(
            {
                "dataset": dataset,
                "name": entry.name,
                "size": entry.size,
                "description": entry.description,
                "downloaded": path.exists(),
                "path": str(path),
                "will_download": (not path.exists()) and (args.include_large or not large),
                "requires_include_large": large and not args.include_large,
            }
        )
    return {"profile": args.profile, "datasets": plan}


def cmd_cache_download(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    entries = load_manifest(cache_dir)
    entry = resolve_dataset(entries, args.dataset)
    path = download_entry(entry, cache_dir, verify=not args.no_verify)
    return {"name": entry.name, "path": str(path), "md5": entry.md5}


def cmd_cache_sync(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    entries = load_manifest(cache_dir)
    downloaded = []
    skipped = []
    for dataset in SYNC_PROFILES[args.profile]:
        entry = resolve_dataset(entries, dataset)
        if is_large(entry.size) and not args.include_large:
            skipped.append({"dataset": dataset, "name": entry.name, "size": entry.size, "reason": "requires --include-large"})
            continue
        path = download_entry(entry, cache_dir)
        downloaded.append({"dataset": dataset, "name": entry.name, "size": entry.size, "path": str(path)})

    indexed = index_cache(cache_dir, indexable_aliases(item["dataset"] for item in downloaded)) if args.index else []
    return {"profile": args.profile, "downloaded": downloaded, "skipped": skipped, "indexed": indexed}


def cmd_cache_index(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    datasets = None if not args.datasets or args.datasets == ["all"] else args.datasets
    results = index_cache(cache_dir, datasets)
    if not results:
        raise OrthoDBError("no supported downloaded datasets found to index")
    return results


def cmd_export(args: argparse.Namespace, client: OrthoDBClient, cache_dir: Path) -> Any:
    text = export_ndjson(cache_dir, args.table, args.query, args.limit)
    return write_or_return_text(text, args.file_output)


def indexable_aliases(datasets: Iterable[str]) -> list[str]:
    supported = {"species", "levels", "ogs", "og2genes", "genes"}
    return [dataset for dataset in datasets if dataset in supported]


def is_large(size: str) -> bool:
    value, _, unit = size.partition(" ")
    try:
        number = float(value)
    except ValueError:
        return False
    unit = unit.upper()
    return unit.startswith("GB") and number >= 1.0


def write_or_return_text(text: str, output: str | None) -> Any:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        return {"path": output, "bytes": len(text.encode("utf-8"))}
    return text


def emit(value: Any, output: str) -> None:
    if output == "json" and not isinstance(value, str):
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if output == "json" and isinstance(value, str) and "\n" not in value:
        print(json.dumps(value))
        return
    print(value, end="" if isinstance(value, str) and value.endswith("\n") else "\n")


if __name__ == "__main__":
    raise SystemExit(main())
