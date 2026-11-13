"""CLI do Lipidence-NIR Modular.

Comando sem implementação não existe aqui (protocolo, regra 8). A CLI usa os mesmos
serviços de ``application/`` que a API e a interface.
"""

from __future__ import annotations

import argparse
import getpass
import json
import platform
import sys
from collections.abc import Sequence

from lipidence_modular import __version__
from lipidence_modular.core.errors import LipidenceError


def _cmd_version(args: argparse.Namespace) -> int:
    info = {"lipidence_modular": __version__, "python": platform.python_version()}
    if args.json:
        print(json.dumps(info, sort_keys=True))
    else:
        for key, value in info.items():
            print(f"{key}: {value}")
    return 0


def _cmd_db_upgrade(args: argparse.Namespace) -> int:
    from lipidence_modular.core.config import load_settings
    from lipidence_modular.repositories import migrate

    settings = load_settings()
    migrate.upgrade(settings.database_url)
    print(f"banco migrado para {migrate.head_revision(settings.database_url)}")
    return 0


def _cmd_db_current(args: argparse.Namespace) -> int:
    from lipidence_modular.core.config import load_settings
    from lipidence_modular.repositories import migrate
    from lipidence_modular.repositories.database import make_engine

    settings = load_settings()
    engine = make_engine(settings.database_url)
    try:
        print(f"atual: {migrate.current_revision(engine)}")
        print(f"mais recente: {migrate.head_revision(settings.database_url)}")
    finally:
        engine.dispose()
    return 0


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Senha: ")
    if first != getpass.getpass("Repita a senha: "):
        raise LipidenceError("as senhas não conferem")
    return first


def _cmd_user_create(args: argparse.Namespace) -> int:
    from lipidence_modular.application.context import build_context
    from lipidence_modular.application.contracts import CreateUserInput
    from lipidence_modular.auth.passwords import WeakPasswordError
    from lipidence_modular.auth.roles import Role

    password = _read_password(args.password_stdin)
    context = build_context()
    try:
        user = context.auth.create_user(
            CreateUserInput(username=args.username, password=password, role=Role(args.role))
        )
    except WeakPasswordError as exc:
        raise LipidenceError(str(exc)) from exc
    finally:
        context.close()
    print(f"usuário criado: {user.username} ({user.role.value})")
    return 0


def _cmd_import_run(args: argparse.Namespace) -> int:
    """Importa um arquivo. Sem ``--confirm`` só mostra o preview; nada é gravado."""
    from pathlib import Path

    import yaml

    from lipidence_modular.application.context import build_context
    from lipidence_modular.application.errors import describe_error
    from lipidence_modular.data.ingestion.plan import ImportKind, ImportPlan

    plan_data = yaml.safe_load(Path(args.plan).read_text(encoding="utf-8")) if args.plan else {}
    plan = ImportPlan(**(plan_data or {}))
    path = Path(args.file)
    context = build_context()
    try:
        user = context.auth.get_user(args.as_user)
        staged = context.imports.stage(
            content=path.read_bytes(), filename=path.name, kind=ImportKind(args.kind),
            study_id=args.study, user=user,
        )
        print(f"lote: {staged.import_batch_id}   sha256: {staged.file_hash}")
        d = staged.detection
        print(f"detectado: formato={d.file_format} delimitador={d.delimiter!r} "
              f"decimal={d.decimal!r} cabeçalho={d.has_header}")
        if staged.duplicate_of:
            print(f"AVISO: arquivo já importado neste estudo (lote {staged.duplicate_of})")
        if not args.confirm:
            preview = context.imports.preview(staged.import_batch_id, plan, user)
            if preview.blocking_error:
                print(f"BLOQUEADO: {preview.blocking_error}")
                return 2
            print(f"layout: {preview.layout}   colunas ignoradas: {preview.ignored_columns}")
            print(preview.report.as_text())
            print("\nPREVIEW: nada foi gravado. Repita com --confirm para importar.")
            return 0
        report = context.imports.confirm(staged.import_batch_id, plan, user)
        print(report.as_text())
        return 0
    except Exception as exc:
        info = describe_error(exc)
        if info is None:
            raise
        print(f"erro: {info.message}", file=sys.stderr)
        return 2
    finally:
        context.close()


def _cmd_base_summary(args: argparse.Namespace) -> int:
    from lipidence_modular.application.context import build_context

    context = build_context()
    try:
        summary = context.base.summary(args.study)
    finally:
        context.close()
    print(json.dumps(summary.model_dump(), indent=2))
    return 0


def _cmd_base_samples(args: argparse.Namespace) -> int:
    from lipidence_modular.application.context import build_context
    from lipidence_modular.application.experimental_contracts import SampleFilters

    context = build_context()
    try:
        result = context.base.list_samples(SampleFilters(
            study_id=args.study, genotype=args.genotype, batch=args.batch, lot=args.lot,
            completeness=args.completeness, limit=args.limit,
        ))
    finally:
        context.close()
    print(f"total: {result.total}")
    for s in result.samples:
        print(f"{s.study_id}\t{s.sample_id}\tgenótipo={s.genotype}\tespectros={s.n_spectra}"
              f"\treferências={','.join(s.parameters) or '-'}\tcompleta={s.complete}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    factory = "create_api_only" if args.no_ui else "create_app"
    uvicorn.run(
        f"lipidence_modular.server:{factory}", factory=True, host=args.host, port=args.port
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m lipidence_modular",
        description="Lipidence-NIR Modular: predição NIR auditável.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="mostra a versão do pacote e do Python")
    p_version.add_argument("--json", action="store_true", help="saída em JSON")
    p_version.set_defaults(func=_cmd_version)

    p_db = sub.add_parser("db", help="migrações do banco").add_subparsers(
        dest="db_command", required=True
    )
    p_db.add_parser("upgrade", help="aplica todas as migrações").set_defaults(
        func=_cmd_db_upgrade
    )
    p_db.add_parser("current", help="mostra a revisão atual").set_defaults(func=_cmd_db_current)

    p_user = sub.add_parser("user", help="usuários").add_subparsers(
        dest="user_command", required=True
    )
    p_create = p_user.add_parser("create", help="cria um usuário (não há cadastro aberto)")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--role", required=True, choices=["ADMIN", "USER"])
    p_create.add_argument(
        "--password-stdin", action="store_true", help="lê a senha da entrada padrão"
    )
    p_create.set_defaults(func=_cmd_user_create)

    p_import = sub.add_parser("import", help="importação assistida").add_subparsers(
        dest="import_command", required=True
    )
    p_run = p_import.add_parser("run", help="preview (padrão) ou importação (--confirm)")
    p_run.add_argument("--file", required=True)
    p_run.add_argument("--kind", required=True, choices=["spectra", "reference", "combined"])
    p_run.add_argument("--study", required=True, help="study_id do ensaio experimental")
    p_run.add_argument("--as-user", required=True, help="usuário registrado como importador")
    p_run.add_argument("--plan", help="YAML com o plano de importação (mapeamento, unidades)")
    p_run.add_argument("--confirm", action="store_true", help="grava a importação")
    p_run.set_defaults(func=_cmd_import_run)

    p_base = sub.add_parser("base", help="consulta da base experimental").add_subparsers(
        dest="base_command", required=True
    )
    p_summary = p_base.add_parser("summary", help="contagens da base")
    p_summary.add_argument("--study")
    p_summary.set_defaults(func=_cmd_base_summary)
    p_samples = p_base.add_parser("samples", help="lista amostras")
    for name in ("study", "genotype", "batch", "lot"):
        p_samples.add_argument(f"--{name}")
    p_samples.add_argument(
        "--completeness", choices=["complete", "incomplete", "no_spectrum", "no_reference"]
    )
    p_samples.add_argument("--limit", type=int, default=200)
    p_samples.set_defaults(func=_cmd_base_samples)

    p_serve = sub.add_parser("serve", help="sobe a API e a interface")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--no-ui", action="store_true", help="sobe só a API, sem o Dash")
    p_serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    try:
        return int(args.func(args))
    except LipidenceError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
