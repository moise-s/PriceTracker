"""PriceTracker command-line interface.

Stable automation contract for ``pricetracker run``:

* stdout carries exactly one JSON document (the run summary); logs go to stderr;
* exit codes: 0 success · 1 unexpected error · 2 invalid usage · 3 invalid input or
  configuration (unknown site/store/product/list/user, empty list) · 4 partial ·
  5 failed · 6 cancelled.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import select

from pricetracker import settings as settings_module
from pricetracker.db.session import init_engine, session_factory
from pricetracker.logs import configure_logging
from pricetracker.models.enums import Role, RunStatus, RunTrigger, TargetStatus

app = typer.Typer(help="PriceTracker: comparação de preços de supermercado.", no_args_is_help=True)
user_app = typer.Typer(help="Gerenciar usuários.", no_args_is_help=True)
db_app = typer.Typer(help="Banco de dados.", no_args_is_help=True)
llm_app = typer.Typer(help="Provedores de IA (fallback opcional).", no_args_is_help=True)
app.add_typer(user_app, name="user")
app.add_typer(db_app, name="db")
app.add_typer(llm_app, name="llm")

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_INPUT, EXIT_PARTIAL, EXIT_FAILED, EXIT_CANCELLED = (
    0,
    1,
    2,
    3,
    4,
    5,
    6,
)
STATUS_EXIT = {
    RunStatus.SUCCESS: EXIT_OK,
    RunStatus.PARTIAL: EXIT_PARTIAL,
    RunStatus.FAILED: EXIT_FAILED,
    RunStatus.CANCELLED: EXIT_CANCELLED,
}


class InputError(Exception):
    pass


def _bootstrap(config: Path | None, debug: bool = False) -> settings_module.Settings:
    if config is not None:
        if not config.is_file():
            raise InputError(f"arquivo de configuração não encontrado: {config}")
        settings = settings_module.Settings(_env_file=str(config))
    else:
        settings = settings_module.Settings()
    settings_module.configure_settings(settings)
    level = "DEBUG" if debug else settings.log_level
    configure_logging(level, json_output=settings.log_json and not debug, stream=sys.stderr)
    init_engine(settings)
    return settings


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _emit(data: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, default=_json_default, indent=2) + "\n")
    sys.stdout.flush()


def _fail(message: str, code: int) -> None:
    _emit({"error": message, "exit_code": code})
    raise typer.Exit(code)


# --- run ------------------------------------------------------------------------------


@app.command()
def run(
    site: Annotated[
        list[str] | None,
        typer.Option(
            "--site", help="Mercado (slug): angeloni, bistek, fort, imperatriz. Repetível."
        ),
    ] = None,
    store: Annotated[
        list[str] | None,
        typer.Option(
            "--store", help="Filial como mercado:slug (ex.: angeloni:beira-mar). Repetível."
        ),
    ] = None,
    product: Annotated[
        list[str] | None,
        typer.Option("--product", help="Filtra produtos pelo nome (contém). Repetível."),
    ] = None,
    list_: Annotated[
        str | None, typer.Option("--list", help="Nome ou id da lista (padrão: lista principal).")
    ] = None,
    user: Annotated[
        str | None,
        typer.Option("--user", help="Usuário dono da busca (padrão: primeiro administrador)."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Arquivo .env com configurações (sobrepõe o ambiente)."),
    ] = None,
    headless: Annotated[
        bool,
        typer.Option(
            "--headless/--headed", help="Modo de navegador; os adaptadores atuais usam só HTTP."
        ),
    ] = True,
    debug: Annotated[
        bool, typer.Option("--debug", help="Logs detalhados em texto no stderr.")
    ] = False,
    enqueue: Annotated[
        bool, typer.Option("--enqueue", help="Apenas enfileira para o worker e sai.")
    ] = False,
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Desativa o fallback por IA nesta busca.")
    ] = False,
) -> None:
    """Busca preços agora e imprime um resumo JSON (exit code reflete o resultado)."""
    try:
        settings = _bootstrap(config, debug)
        summary = asyncio.run(
            _run(
                settings,
                site or [],
                store or [],
                product or [],
                list_,
                user,
                headless,
                debug,
                enqueue,
                no_llm,
            )
        )
    except InputError as exc:
        _fail(str(exc), EXIT_INPUT)
        return
    except typer.Exit:
        raise
    except Exception as exc:
        first_line = str(exc).splitlines()[0][:300] if str(exc) else ""
        _fail(f"erro inesperado: {type(exc).__name__}: {first_line}", EXIT_ERROR)
        return
    _emit(summary)
    raise typer.Exit(summary["exit_code"])


async def _run(
    settings: settings_module.Settings,
    sites: list[str],
    stores: list[str],
    products: list[str],
    list_ref: str | None,
    username: str | None,
    headless: bool,
    debug: bool,
    enqueue: bool,
    no_llm: bool,
) -> dict[str, Any]:
    from pricetracker.models import Market, Product, Run, RunTarget, ShoppingList, Store, User
    from pricetracker.services import catalog, profile
    from pricetracker.services import runs as run_service
    from pricetracker.services.errors import ServiceError
    from pricetracker.worker.executor import RunExecutor

    factory = session_factory()
    with factory() as db:
        if username:
            owner = db.scalar(select(User).where(User.username == username.lower()))
        else:
            owner = db.scalar(
                select(User).where(User.role == Role.ADMIN.value).order_by(User.created_at)
            )
        if owner is None:
            raise InputError("usuário não encontrado (use --user ou crie um administrador)")
        shopping_list = None
        if list_ref:
            try:
                shopping_list = catalog.get_list(db, owner, uuid.UUID(list_ref))
            except (ValueError, ServiceError):
                shopping_list = db.scalar(
                    select(ShoppingList).where(
                        ShoppingList.user_id == owner.id, ShoppingList.name.ilike(list_ref)
                    )
                )
            if shopping_list is None:
                raise InputError(f"lista '{list_ref}' não encontrada")
        else:
            shopping_list = catalog.default_list(db, owner)
        list_products = [item.product for item in shopping_list.items if item.product.is_active]
        if products:
            wanted = [p.lower() for p in products]
            list_products = [p for p in list_products if any(w in p.name.lower() for w in wanted)]
            if not list_products:
                raise InputError("nenhum produto da lista corresponde a --product")
        if not list_products:
            raise InputError("a lista não tem produtos ativos")
        market_rows = {m.slug: m for m in db.scalars(select(Market))}
        for slug in sites:
            if slug not in market_rows:
                raise InputError(f"mercado desconhecido: {slug}")
        chosen_stores: list[Store] = []
        if stores:
            for ref in stores:
                if ":" not in ref:
                    raise InputError(f"use mercado:filial em --store (recebido '{ref}')")
                market_slug, store_slug = ref.split(":", 1)
                market = market_rows.get(market_slug)
                found = market and db.scalar(
                    select(Store).where(Store.market_id == market.id, Store.slug == store_slug)
                )
                if not found:
                    raise InputError(f"filial desconhecida: {ref}")
                chosen_stores.append(found)
        else:
            selected = profile.selections(db, owner.id)
            chosen_stores = [db.get(Store, sid) for sid in selected]  # type: ignore[misc]
            if sites:
                site_ids = {market_rows[s].id for s in sites}
                chosen_stores = [s for s in chosen_stores if s and s.market_id in site_ids]
            if not chosen_stores:
                raise InputError(
                    "nenhuma filial selecionada; use --store mercado:filial ou selecione filiais no app"
                )
        try:
            run_row = run_service.create_run(
                db,
                owner,
                list_id=shopping_list.id,
                store_ids=[s.id for s in chosen_stores],
                product_ids=[p.id for p in list_products],
                trigger=RunTrigger.CLI,
                options={
                    "headless": headless,
                    "debug": debug,
                    "allow_llm": not no_llm,
                    "browser_used": False,
                },
                allow_concurrent=True,
            )
        except ServiceError as exc:
            raise InputError(exc.message) from exc
        run_id = run_row.id
    if enqueue:
        return {
            "run_id": str(run_id),
            "status": RunStatus.QUEUED.value,
            "exit_code": EXIT_OK,
            "enqueued": True,
        }
    with factory() as db:
        claimed = db.get(Run, run_id)
        assert claimed is not None
        claimed.status = RunStatus.RUNNING.value
        claimed.worker_id = "cli"
        db.commit()
    executor = RunExecutor(factory=factory, settings=settings, worker_id="cli")
    status = await executor.execute(run_id)
    with factory() as db:
        finished = db.get(Run, run_id)
        assert finished is not None
        targets = list(db.scalars(select(RunTarget).where(RunTarget.run_id == run_id)))
        names = {
            p.id: p.name
            for p in db.scalars(
                select(Product).where(Product.id.in_({t.product_id for t in targets}))
            )
        }
        store_rows = {
            s.id: s
            for s in db.scalars(select(Store).where(Store.id.in_({t.store_id for t in targets})))
        }
        markets_by_id = {m.id: m.slug for m in db.scalars(select(Market))}
        from pricetracker.models import Observation

        observations = {
            o.target_id: o
            for o in db.scalars(select(Observation).where(Observation.run_id == run_id))
        }
        items = []
        for target in targets:
            obs = observations.get(target.id)
            store_row = store_rows[target.store_id]
            items.append(
                {
                    "market": markets_by_id.get(target.market_id),
                    "store": store_row.slug,
                    "product": names.get(target.product_id),
                    "status": target.status,
                    "method": target.method,
                    "title": obs.title if obs else None,
                    "price": (obs.promo_price or obs.regular_price) if obs else None,
                    "regular_price": obs.regular_price if obs else None,
                    "club_price": obs.club_price if obs else None,
                    "unit_price": obs.unit_price if obs else None,
                    "unit": obs.unit_price_unit if obs else None,
                    "url": obs.url if obs else None,
                    "flagged": bool(obs and obs.is_outlier),
                    "error_type": target.error_type,
                    "error": target.error_detail,
                    "duration_ms": target.duration_ms,
                }
            )
        return {
            "run_id": str(run_id),
            "status": status.value,
            "exit_code": STATUS_EXIT.get(status, EXIT_ERROR),
            "started_at": finished.started_at,
            "finished_at": finished.finished_at,
            "counts": finished.counts,
            "llm_calls": finished.llm_calls,
            "targets": items,
            "failures": [i for i in items if TargetStatus(str(i["status"])).is_failure],
        }


# --- operations -----------------------------------------------------------------------------


@db_app.command("upgrade")
def db_upgrade(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Aplica as migrations (alembic upgrade head)."""
    settings = _bootstrap(config)
    from alembic import command
    from alembic.config import Config

    ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.attributes["database_url"] = settings.resolved_database_url
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    typer.echo("migrations aplicadas", err=True)


@app.command()
def seed(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Cria/atualiza mercados, filiais, catálogo inicial e provedores (idempotente)."""
    _bootstrap(config)
    from pricetracker.seed import seed_all

    with session_factory()() as db:
        result = seed_all(db)
    _emit({"seeded": result})


@app.command("setup-code")
def setup_code(
    config: Annotated[Path | None, typer.Option("--config")] = None,
    minutes: Annotated[int, typer.Option(help="Validade em minutos.")] = 30,
) -> None:
    """Gera um código de uso único para criar o primeiro administrador pela web."""
    _bootstrap(config)
    from pricetracker.services import accounts
    from pricetracker.services.errors import ServiceError

    with session_factory()() as db:
        try:
            code = accounts.generate_setup_code(db, ttl_minutes=minutes)
        except ServiceError as exc:
            _fail(exc.message, EXIT_INPUT)
            return
    typer.echo(f"Código de configuração (válido por {minutes} min): {code}")


@user_app.command("create")
def user_create(
    username: Annotated[str, typer.Option(prompt=True)],
    display_name: Annotated[str, typer.Option(prompt="Nome de exibição")],
    admin: Annotated[bool, typer.Option("--admin/--user")] = False,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Cria um usuário (a senha é pedida sem eco; o usuário troca no primeiro acesso)."""
    _bootstrap(config)
    from pricetracker.services import accounts
    from pricetracker.services.errors import ServiceError

    password = getpass.getpass("Senha temporária: ")
    with session_factory()() as db:
        try:
            if accounts.user_count(db) == 0:
                # Trusted local path (requires server access): first account is an administrator.
                account = accounts.create_first_admin_trusted(
                    db, username=username, display_name=display_name, password=password
                )
            else:
                account = accounts.admin_create_user(
                    db, username=username, display_name=display_name, temporary_password=password,
                    role=Role.ADMIN if admin else Role.USER,
                )  # fmt: skip
        except ServiceError as exc:
            _fail(exc.message, EXIT_INPUT)
            return
    typer.echo(
        "Usuário criado. Códigos de recuperação (guarde agora; não serão mostrados de novo):"
    )
    for code in account.recovery_codes:
        typer.echo(f"  {code}")


@user_app.command("reset-password")
def user_reset_password(
    username: Annotated[str, typer.Option(prompt=True)],
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Define uma senha temporária (o usuário troca no próximo acesso) e encerra as sessões."""
    _bootstrap(config)
    from pricetracker.models import User
    from pricetracker.services import accounts
    from pricetracker.services.errors import ServiceError

    password = getpass.getpass("Nova senha temporária: ")
    with session_factory()() as db:
        found = db.scalar(select(User).where(User.username == username.lower()))
        if found is None:
            _fail("usuário não encontrado", EXIT_INPUT)
            return
        try:
            accounts.admin_reset_password(db, user_id=found.id, temporary_password=password)
        except ServiceError as exc:
            _fail(exc.message, EXIT_INPUT)
            return
    typer.echo("Senha redefinida; sessões encerradas.")


@llm_app.command("check")
def llm_check(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Verifica o provedor de IA ativo (autenticação e modelo) sem exibir a chave."""
    _bootstrap(config)
    from pricetracker.services.llm_admin import check_active_provider

    with session_factory()() as db:
        result = check_active_provider(db)
    _emit(result)
    raise typer.Exit(EXIT_OK if result.get("ok") else EXIT_FAILED)


@app.command()
def worker(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Executa o worker de coletas (fila durável no banco)."""
    _bootstrap(config)
    from pricetracker.worker.main import main as worker_main

    worker_main()


@app.command()
def scheduler(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Executa o agendador de buscas recorrentes."""
    _bootstrap(config)
    from pricetracker.scheduler.main import main as scheduler_main

    scheduler_main()


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Sobe a API HTTP (uvicorn)."""
    _bootstrap(config)
    import uvicorn

    uvicorn.run(
        "pricetracker.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        proxy_headers=True,
        log_config=None,
    )


@app.command()
def health(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Checagem de saúde para containers (banco acessível e migrations aplicadas)."""
    _bootstrap(config)
    from sqlalchemy import text

    try:
        with session_factory()() as db:
            db.execute(text("SELECT 1"))
            version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:
        _fail(f"banco indisponível: {type(exc).__name__}", EXIT_FAILED)
        return
    _emit({"ok": True, "schema": version})


@app.command()
def openapi(
    output: Annotated[Path, typer.Option(help="Arquivo de saída.")] = Path("var/openapi.json"),
) -> None:
    """Exporta o contrato OpenAPI (usado para gerar o cliente tipado do frontend)."""
    import os

    os.environ.setdefault("PRICETRACKER_DATABASE_URL", "sqlite://")
    settings_module.configure_settings(settings_module.Settings(_env_file=None, log_level="ERROR"))
    from pricetracker.api.app import create_app

    output.parent.mkdir(parents=True, exist_ok=True)
    spec = create_app().openapi()
    output.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    typer.echo(f"OpenAPI salvo em {output} ({len(spec['paths'])} rotas)", err=True)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
