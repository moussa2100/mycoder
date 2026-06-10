"""CLI entry point for pgimcode."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pgimcode import __app_name__, __version__
from pgimcode.approval import ApprovalConfig, ApprovalGate
from pgimcode.config import Settings
from pgimcode.events import Event, EventBus, EventLogWriter, EventType
from pgimcode.context import ContextManager
from pgimcode.mock_agent import MockAgent
from pgimcode.observability import MetricsCollector, TraceRecorder, FailureSnapshot
from pgimcode.planner import TaskPlanner
from pgimcode.session import SessionStore
from pgimcode.terminal import RichTerminalRenderer
from pgimcode.tools.snapshot import SnapshotManager
from pgimcode.tools.diff import DiffResult
from pgimcode.tools.test_runner import run_tests
from pgimcode.models import AVAILABLE_MODELS, ModelProvider, get_models_by_provider, resolve_model_info
from pgimcode.chat import ChatSession
from pgimcode.input_handler import SlashCommandListener, ModelSelector
from pgimcode.skills import SkillManager

app = typer.Typer(no_args_is_help=False, add_completion=False, invoke_without_command=True)


@app.callback(invoke_without_command=True)
def default_callback(
    ctx: typer.Context,
    model: str | None = typer.Option(None, "--model", "-M", help="Select AI model"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Auto-approve caution-level actions"),
    real: bool = typer.Option(False, "--real", help="Use real LLM agent (requires API key)"),
) -> None:
    """pgimcode — Terminal AI Coding Assistant. Default: interactive chat."""
    if ctx.invoked_subcommand is not None:
        return

    import asyncio

    settings = Settings()

    if model:
        ModelSelector.apply_model_selection(settings, model)

    console = Console()

    approval_config = ApprovalConfig(auto_approve_caution=auto_approve)
    gate = ApprovalGate(config=approval_config, session_id="", bus=None, console=console)

    if not auto_approve:
        def prompt_user(action: str, details: str) -> bool:
            console.print(f"\n[yellow]🛑 Approval required:[/] {action}")
            console.print(f"[dim]{details}[/dim]")
            answer = console.input("Approve? [y/N]: ").strip().lower()
            return answer in ("y", "yes")
        gate.prompt_fn = prompt_user

    chat = ChatSession(
        console=console,
        settings=settings,
        approval_gate=gate,
        use_real=real,
    )

    try:
        asyncio.run(chat.start())
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"{__app_name__} {__version__}")


@app.command()
def list_sessions() -> None:
    """List all sessions."""
    store = SessionStore()
    sessions = store.list_sessions()

    if not sessions:
        typer.echo("No sessions found.")
        return

    table = Table(title="Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Task", style="white")
    table.add_column("Mode", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Created", style="dim")

    for s in sessions:
        created = s.created_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(s.id, s.task, s.mode, s.status, created)

    console = Console()
    console.print(table)


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description"),
    mode: str = typer.Option("build", "--mode", "-m", help="Agent mode (build, plan, review)"),
    resume: str | None = typer.Option(None, "--resume", "-r", help="Resume from existing session ID"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color output"),
    plan_only: bool = typer.Option(False, "--plan-only", help="Only show the plan, don't run the agent"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without modifying files"),
    execute_tests: bool = typer.Option(False, "--execute-tests", help="Run actual tests instead of mocking test execution"),
    verify: bool = typer.Option(False, "--verify", "-v", help="Run post-edit verification checks"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Auto-approve caution-level actions"),
    metrics: bool = typer.Option(False, "--metrics", help="Print session metrics at completion"),
    trace_export: str | None = typer.Option(None, "--trace-export", help="Export trace to JSONL file path"),
    failure_snapshot: bool = typer.Option(False, "--failure-snapshot", help="Write failure snapshot on FAILED events"),
    real: bool = typer.Option(False, "--real", help="Use real LLM agent instead of mock"),
    model: str | None = typer.Option(None, "--model", "-M", help="Select AI model (e.g. deepseek-chat, gemini-3.5-flash). Use 'models' subcommand to list all."),
) -> None:
    """Run a coding task with the agent."""
    # Handle dry-run mode early
    if dry_run:
        typer.echo("Dry run mode — no files modified")
        return

    settings = Settings()

    if model:
        ModelSelector.apply_model_selection(settings, model)

    # Disable color if requested
    if no_color:
        settings.color_enabled = False

    console = Console()

    try:
        # Create session store and session
        store = SessionStore()

        if resume:
            # Resume existing session
            session = store.get(resume)
            if not session:
                typer.echo(f"Error: Session '{resume}' not found.", err=True)
                raise typer.Exit(code=1)
        else:
            # Create new session
            session = store.create(task=task, mode=mode)
            store.save(session)

            # Note: Snapshot of files to be edited would be created here
            # (snapshot functionality wired in Phase 6+)

        session_id = session.id

        # Create trace recorder before event bus so it's ready for first event
        trace_recorder: TraceRecorder | None = None
        if trace_export:
            trace_path = Path(trace_export)
            trace_recorder = TraceRecorder(session_id=session_id, output_path=trace_path)

        # Create event bus with optional metrics collector and trace recorder
        metrics_collector: MetricsCollector | None = None
        if metrics:
            metrics_collector = MetricsCollector(session_id=session_id, task=task)
            metrics_collector.start()
        bus = EventBus(metrics_collector=metrics_collector, trace_recorder=trace_recorder)

        # Create event log writer
        jsonl_path = store.jsonl_path(session_id)
        log_writer = EventLogWriter(jsonl_path)

        # Create terminal renderer
        renderer = RichTerminalRenderer(
            console=console,
            session_id=session_id,
            task=task,
            mode=mode
        )

        # Wire bus to renderer and log writer
        def handle_event(event: Event) -> None:
            renderer.add_event(event)
            renderer.refresh()

        async def log_event(event: Event) -> None:
            await log_writer.write(event)

        bus.subscribe(handle_event)
        bus.subscribe(log_event)

        # Run the agent inside the renderer context
        with renderer:
            # Create plan at the start (before agent runs)
            from pgimcode.discovery.repo_scanner import RepoScanner
            from pgimcode.discovery.language_detector import annotate_languages
            from pgimcode.discovery.repo_map import build_repo_map
            from pgimcode.tools.ranker import rank_files_by_relevance

            # Scan repo and rank files
            scanner = RepoScanner(root=Path("."))
            files = annotate_languages(scanner.scan())
            ranked = rank_files_by_relevance(task, files, Path("."), max_results=20)
            repo_map = build_repo_map(scanner)

            # Generate plan
            planner = TaskPlanner(repo_map=repo_map, ranked_files=ranked)
            plan = planner.plan(task)

            # Print plan
            console.print(plan.to_markdown())

            # Emit PLAN_GENERATED event
            asyncio.run(bus.publish(Event(
                session_id=session_id,
                type=EventType.PLAN_GENERATED,
                step=0,
                status="done",
                details=f"Plan generated with {len(plan.steps)} steps, {plan.confidence:.0%} confidence",
            )))

            # If --plan-only, exit early
            if plan_only:
                session.status = "completed"
                session.step_count = 1
                session.completed_at = datetime.now(timezone.utc)
                store.save(session)
                return

            # Create approval gate
            approval_config = ApprovalConfig(auto_approve_caution=auto_approve)
            gate = ApprovalGate(config=approval_config, session_id=session_id, bus=bus, console=console)

            # Set up interactive prompt if not auto-approve
            if not auto_approve:
                def prompt_user(action: str, details: str) -> bool:
                    session_console = Console(no_color=no_color)
                    session_console.print(f"\n[yellow]🛑 Approval required:[/] {action}")
                    session_console.print(f"[dim]{details}[/dim]")
                    answer = session_console.input("Approve? [y/N]: ").strip().lower()
                    return answer in ("y", "yes")
                gate.prompt_fn = prompt_user

            # Create context manager
            context_manager = ContextManager(session_id=session_id)
            context_manager.pin(f"Task: {task}", "goal", 0)

            slash_listener: SlashCommandListener | None = None
            if real:
                slash_listener = SlashCommandListener(
                    settings=settings,
                    bus=bus,
                    console=console,
                    session_id=session_id,
                )
                slash_listener.start()

            if real:
                from pgimcode.agent import RealAgent
                agent = RealAgent(
                    bus, session_id, task,
                    approval_gate=gate,
                    context_manager=context_manager,
                    mode=mode,
                    settings=settings,
                    slash_listener=slash_listener,
                    renderer=renderer,
                )
            else:
                agent = MockAgent(
                    bus, session_id, task,
                    approval_gate=gate,
                    context_manager=context_manager,
                    slash_listener=slash_listener,
                    renderer=renderer,
                )

            # Retry policy available for future integration
            # retry_policy = RetryPolicy(
            #     max_retries=2,
            #     backoff_factor=0.0,
            #     log_fn=lambda msg: console.print(f"[dim]{msg}[/dim]"),
            # )

            try:
                asyncio.run(agent.run())

                if slash_listener:
                    slash_listener.stop()

                # Handle --execute-tests: run actual tests instead of mock
                if execute_tests and renderer._events:
                    # Find TESTS_RUNNING event in the events
                    tests_running_idx = None
                    for i, evt in enumerate(renderer._events):
                        if evt.type == EventType.TESTS_RUNNING:
                            tests_running_idx = i
                            break
                    
                    if tests_running_idx is not None:
                        # Remove mock tests_running and subsequent events
                        renderer._events = renderer._events[:tests_running_idx]
                        
                        # Run actual tests
                        console.print("\n[bold]Running actual tests...[/]")
                        test_result = run_tests(Path("."), timeout=120)
                        
                        # Print results
                        if test_result.success:
                            console.print(f"[green]Tests passed:[/] {test_result.pass_count} passed, {test_result.skip_count} skipped")
                            # Emit COMPLETED event
                            asyncio.run(bus.publish(Event(
                                session_id=session_id,
                                type=EventType.COMPLETED,
                                step=len(renderer._events) + 1,
                                status="done",
                                details=f"Tests passed ({test_result.pass_count} passed)",
                            )))
                        else:
                            console.print(f"[red]Tests failed:[/] {test_result.fail_count} failed, {test_result.pass_count} passed")
                            if test_result.stdout:
                                console.print(test_result.stdout[:500])
                            # Emit FAILED event
                            asyncio.run(bus.publish(Event(
                                session_id=session_id,
                                type=EventType.FAILED,
                                step=len(renderer._events) + 1,
                                status="done",
                                details=f"Tests failed ({test_result.fail_count} failed)",
                            )))

                # Handle --verify: run post-edit verification
                if verify:
                    console.print("\n[bold]Running verification...[/]")
                    from pgimcode.verification import Verifier

                    verifier = Verifier(Path("."))
                    # Determine changed files (for mock agent, use known paths)
                    changed = []
                    for evt in renderer._events:
                        if evt.type == EventType.PATCH_APPLYING and evt.details:
                            # simplistic: extract file path from details
                            import re
                            m = re.search(r"Edit:\s+(\S+)", evt.details)
                            if m:
                                changed.append(Path(".") / m.group(1))

                    report = verifier.verify(changed)
                    console.print(report.to_markdown())

                    if report.verdict == "fail":
                        console.print("[red]Verification failed. Task not completed.[/]")
                        session.status = "failed"
                        session.completed_at = datetime.now(timezone.utc)
                        store.update(session)
                        raise typer.Exit(code=1)
                    elif report.verdict == "warn":
                        console.print("[yellow]Verification passed with warnings.[/]")
                    else:
                        console.print("[green]Verification passed.[/]")

                # Get the last event to determine final status
                if renderer._events:
                    last_event = renderer._events[-1]

                    if last_event.type == EventType.COMPLETED:
                        session.status = "completed"
                        session.completed_at = datetime.now(timezone.utc)
                        session.step_count = last_event.step
                    elif last_event.type == EventType.FAILED:
                        session.status = "failed"
                        session.completed_at = datetime.now(timezone.utc)
                        session.step_count = last_event.step
                    else:
                        session.step_count = len(renderer._events)

                    store.update(session)

                # Print session metrics if requested
                if metrics and metrics_collector:
                    failure_reason = None
                    if renderer._events:
                        last_ev = renderer._events[-1]
                        if last_ev.type == EventType.FAILED:
                            failure_reason = last_ev.details
                    session_metrics = metrics_collector.finish(failure_reason=failure_reason)
                    console.print(session_metrics.to_markdown())

                # Write failure snapshot if requested
                if failure_snapshot and renderer._events:
                    last_ev = renderer._events[-1]
                    if last_ev.type == EventType.FAILED:
                        snapshot = FailureSnapshot.capture(session, context_manager, last_ev)
                        snapshot_path = Path(store.jsonl_path(session_id)).parent / f"{session_id}.failure.json"
                        with snapshot_path.open("w") as f:
                            json.dump(snapshot, f, indent=2)
                        console.print(f"[dim]Failure snapshot written to {snapshot_path}[/]")

            except KeyboardInterrupt:
                console.print("\nInterrupted")
                session.status = "failed"
                store.update(session)
                raise typer.Exit(code=1)

    except KeyboardInterrupt:
        console.print("\nInterrupted")
        raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def analyze(
    path: str = typer.Argument(".", help="Path to repository to analyze"),
    output: str = typer.Option("markdown", "--output", "-o", help="Output format: markdown or json"),
    include_symbols: bool = typer.Option(False, "--include-symbols", help="Include symbol extraction for top files"),
    max_symbol_files: int = typer.Option(10, "--max-symbol-files", help="Max files to parse symbols for"),
) -> None:
    """Analyze a repository and print its map."""
    from pgimcode.discovery.repo_scanner import RepoScanner
    from pgimcode.discovery.repo_map import build_repo_map, RepoMap
    from pgimcode.discovery.symbol_parser import SymbolParser

    root = Path(path).resolve()
    if not root.exists():
        typer.echo(f"Error: path does not exist: {root}", err=True)
        raise typer.Exit(code=1)

    # Create session
    bus = EventBus()
    store = SessionStore()
    session = store.create(task=f"Analyze repo: {root}", mode="plan")
    store.save(session)

    log_writer = EventLogWriter(store.jsonl_path(session.id))

    console = Console()
    renderer = RichTerminalRenderer(
        console=console,
        session_id=session.id,
        task=f"Analyze repo: {root}",
        mode="plan",
    )

    def _on_event(event: Event) -> None:
        renderer.add_event(event)
        renderer.refresh()

    bus.subscribe(_on_event)

    async def _analyze():
        with renderer:
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.REPO_SCANNING,
                step=1,
                status="in_progress",
                details=f"Scanning {root}",
            ))

            scanner = RepoScanner(root)
            repo_map = build_repo_map(scanner)

            await bus.publish(Event(
                session_id=session.id,
                type=EventType.FILE_READING,
                step=2,
                status="in_progress",
                details=f"Indexed {repo_map.total_files} files",
            ))

            if include_symbols:
                await bus.publish(Event(
                    session_id=session.id,
                    type=EventType.VERIFICATION_STARTED,
                    step=3,
                    status="in_progress",
                    details=f"Parsing symbols in top {max_symbol_files} files",
                ))

                sym_parser = SymbolParser()
                symbol_results = []
                # Get top python/files by size, non-binary
                files = sorted(
                    [f for f in scanner.scan() if not f.is_binary],
                    key=lambda f: f.size, reverse=True,
                )[:max_symbol_files]

                for f in files:
                    sym = sym_parser.parse_file(f.abs_path)
                    if sym.functions or sym.classes:
                        symbol_results.append(sym)

                # Add symbols to repo_map as a new field for display
                repo_map.symbol_results = symbol_results  # type: ignore

            await bus.publish(Event(
                session_id=session.id,
                type=EventType.COMPLETED,
                step=4,
                status="done",
                details="Analysis complete",
            ))

        # Print output
        if output == "json":
            import json as _json
            data = {
                "root": str(repo_map.root),
                "languages": repo_map.languages,
                "frameworks": repo_map.frameworks,
                "entry_points": repo_map.entry_points,
                "test_locations": repo_map.test_locations,
                "dependency_files": repo_map.dependency_files,
                "build_commands": repo_map.build_commands,
                "total_files": repo_map.total_files,
                "total_lines": repo_map.total_lines,
                "total_size": repo_map.total_size,
                "top_dirs": repo_map.top_dirs,
            }
            typer.echo(_json.dumps(data, indent=2))
        else:
            typer.echo(repo_map.to_markdown())

        session.status = "completed"
        session.step_count = 4
        session.completed_at = datetime.now(timezone.utc)
        store.save(session)

    try:
        asyncio.run(_analyze())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        raise typer.Exit(1)


@app.command()
def plan(
    task: str = typer.Argument(..., help="Task description to investigate"),
    path: str = typer.Option(".", "--path", "-p", help="Repo root path"),
    max_files: int = typer.Option(5, "--max-files", "-n", help="Max files to read"),
    include_symbols: bool = typer.Option(True, "--include-symbols/--no-symbols", help="Extract symbols from files"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colors"),
) -> None:
    """Plan/analysis mode: scan repo, rank files, read top matches, show symbols, produce plan."""
    from pgimcode.discovery.repo_scanner import RepoScanner
    from pgimcode.discovery.language_detector import annotate_languages
    from pgimcode.tools.ranker import rank_files_by_relevance
    from pgimcode.tools.read import read_file
    from pgimcode.tools.symbols import find_symbol
    from pgimcode.discovery.symbol_parser import SymbolParser

    root = Path(path).resolve()
    if not root.exists():
        typer.echo(f"Error: path does not exist: {root}", err=True)
        raise typer.Exit(code=1)

    # Create session
    bus = EventBus()
    store = SessionStore()
    session = store.create(task=f"Plan: {task}", mode="plan")
    store.save(session)

    log_writer = EventLogWriter(store.jsonl_path(session.id))

    console = Console(no_color=no_color)
    renderer = RichTerminalRenderer(
        console=console,
        session_id=session.id,
        task=task,
        mode="plan",
    )

    async def _on_event(event: Event) -> None:
        renderer.add_event(event)
        renderer.refresh()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(log_writer.write(event))
        except RuntimeError:
            pass

    bus.subscribe(_on_event)

    async def _plan():
        with renderer:
            # Step 1: Scan repo
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.REPO_SCANNING,
                step=1,
                status="in_progress",
                details=f"Scanning {root}",
            ))
            scanner = RepoScanner(root)
            files = annotate_languages(scanner.scan())

            await bus.publish(Event(
                session_id=session.id,
                type=EventType.FILE_READING,
                step=2,
                status="in_progress",
                details=f"Indexed {len(files)} files",
            ))

            # Step 2: Rank files
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.PLANNING_STARTED,
                step=3,
                status="in_progress",
                details=f"Ranking files by relevance to: '{task}'",
            ))
            ranked = rank_files_by_relevance(task, files, root, max_results=max_files * 3)

            # Generate plan using TaskPlanner
            from pgimcode.discovery.repo_map import build_repo_map
            repo_map = build_repo_map(scanner)
            planner = TaskPlanner(repo_map=repo_map, ranked_files=ranked)
            plan = planner.plan(task)

            # Emit PLAN_GENERATED event
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.PLAN_GENERATED,
                step=3,
                status="done",
                details=f"Plan generated: {plan.summarize()}",
            ))

            # Step 3: Read top files
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.FILE_READING,
                step=4,
                status="in_progress",
                details=f"Reading top {max_files} relevant files",
            ))
            read_results = []
            for rf in ranked[:max_files]:
                result = read_file(rf.file.abs_path, max_lines=100)
                read_results.append((rf, result))

            # Step 4: Extract symbols if requested
            symbols = []
            if include_symbols:
                await bus.publish(Event(
                    session_id=session.id,
                    type=EventType.VERIFICATION_STARTED,
                    step=5,
                    status="in_progress",
                    details="Extracting symbols",
                ))
                parser = SymbolParser()
                for rf in ranked[:max_files]:
                    sym = parser.parse_file(rf.file.abs_path)
                    if sym.functions or sym.classes:
                        symbols.append(sym)

            # Step 5: Complete
            await bus.publish(Event(
                session_id=session.id,
                type=EventType.COMPLETED,
                step=6,
                status="done",
                details=f"Analysis complete. Top {len(read_results)} files identified.",
                data={
                    "files_read": [str(r[0].file.path) for r in read_results],
                    "scores": [r[0].score for r in read_results],
                    "reasons": [r[0].reasons for r in read_results],
                },
            ))

        # Print results (static, after Live stops)
        console.print()

        # Print the generated plan
        console.print(plan.to_markdown())
        console.print()

        console.print(f"[bold cyan]Plan for:[/] {task}")
        console.print(f"[bold cyan]Repo:[/] {root}")
        console.print()

        # Top ranked
        table = Table(title="Top Relevant Files")
        table.add_column("#", justify="right", style="dim")
        table.add_column("File", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Why", style="dim")
        for i, (rf, r) in enumerate(read_results, 1):
            why = "; ".join(rf.reasons[:2])
            lines = r.total_lines
            table.add_row(str(i), str(rf.file.path), f"{rf.score:.1f}", f"{why} ({lines} lines)")
        console.print(table)

        # Keywords found
        from pgimcode.tools.ranker import extract_keywords
        keywords = extract_keywords(task)
        console.print(f"\n[bold]Keywords:[/] {', '.join(keywords)}")

        # Quick preview of top file
        if read_results:
            console.print(f"\n[bold]Top file preview:[/] {read_results[0][0].file.path}")
            content = read_results[0][1].content
            preview_lines = content.splitlines()[:20]
            for line in preview_lines:
                console.print(f"  {line}")
            if len(preview_lines) >= 20:
                console.print("  ...")

        # Symbols
        if symbols:
            console.print("\n[bold]Key Symbols:[/]")
            for sym in symbols:
                console.print(f"\n[cyan]{sym.path}[/] ({sym.language})")
                for fn in sym.functions[:5]:
                    console.print(f"  [green]fn[/] {fn.name} {fn.signature}")
                for cls in sym.classes[:5]:
                    console.print(f"  [blue]class[/] {cls.name}")

        session.status = "completed"
        session.step_count = 6
        session.completed_at = datetime.now(timezone.utc)
        store.save(session)

    try:
        asyncio.run(_plan())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        raise typer.Exit(1)


@app.command(name="models")
def list_models(
    provider: str = typer.Option("all", "--provider", "-p", help="Filter by provider: deepseek, gemini, or all"),
) -> None:
    """List all available AI models."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    settings = Settings()
    current_model = settings.model_name

    table = Table(
        title="[bold cyan]Available Models[/]",
        border_style="cyan",
        show_lines=False,
    )
    table.add_column("#", style="dim", justify="right", width=3)
    table.add_column("Provider", style="bold")
    table.add_column("Model ID", style="cyan")
    table.add_column("Name")
    table.add_column("Context", justify="right")
    table.add_column("Pricing", style="dim")
    table.add_column("Description")

    models = list(AVAILABLE_MODELS.values())

    if provider != "all":
        try:
            prov = ModelProvider(provider)
            models = get_models_by_provider(prov)
        except ValueError:
            console.print(f"[red]Unknown provider: {provider}[/]")
            console.print(f"[dim]Available: deepseek, gemini, all[/]")
            raise typer.Exit(code=1)

    current_prov = None
    for i, model in enumerate(models, 1):
        prov_label = ""
        if model.provider != current_prov:
            prov_label = model.provider.value.upper()
            current_prov = model.provider

        ctx = f"{model.context_window // 1000}K"
        cursor = "→" if model.id == current_model else " "
        table.add_row(
            f"{cursor}{i}",
            prov_label,
            model.id,
            model.name,
            ctx,
            model.pricing_note,
            model.description,
        )

    console.print(table)
    console.print()
    console.print(f"[dim]Current model:[/] [bold cyan]{current_model}[/]")
    console.print("[dim]Set via --model flag, /model during session, or PGIMCODE_MODEL_NAME env var[/]")


@app.command(name="skills")
def skills_command(
    action: str = typer.Argument("list", help="Action: list, view, use, deactivate"),
    name: str | None = typer.Argument(None, help="Skill name (required for view/use/deactivate)"),
) -> None:
    """List, view, or activate coding skills."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown

    console = Console()
    manager = SkillManager()

    if action == "list":
        skills = manager.list_skills()
        if not skills:
            console.print("[dim]No skills found in /skills/ directory.[/]")
            return

        table = Table(title="[bold cyan]Available Skills[/]", border_style="cyan")
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Name", style="bold")
        table.add_column("Category", style="dim")
        table.add_column("Description")

        for i, skill in enumerate(skills, 1):
            table.add_row(str(i), skill.name, skill.category, skill.description)

        console.print()
        console.print(table)
        console.print()
        console.print(
            "[dim]Use [bold]pgimcode skills use <name>[/] to activate a skill, "
            "[bold]pgimcode skills view <name>[/] to see its content.[/]"
        )

    elif action == "view":
        if not name:
            console.print("[red]Error:[/] skill name required. Usage: pgimcode skills view <name>")
            raise typer.Exit(code=1)
        content = manager.load_skill(name)
        if content is None:
            console.print(f"[red]Skill not found:[/] {name}")
            raise typer.Exit(code=1)
        console.print()
        console.print(Panel(
            Markdown(content),
            title=f"[bold cyan]Skill: {name}[/]",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        ))

    elif action == "use":
        if not name:
            console.print("[red]Error:[/] skill name required. Usage: pgimcode skills use <name>")
            raise typer.Exit(code=1)
        info = manager.get_skill(name)
        if info is None:
            console.print(f"[red]Skill not found:[/] {name}")
            raise typer.Exit(code=1)
        console.print(f"[green]Skill '{info.name}' is available.[/]")
        console.print(f"[dim]Activate it during a chat session with /skills use {info.name}[/]")

    elif action == "deactivate":
        if not name:
            console.print("[yellow]Use /skills deactivate <name> during a chat session.[/]")
        else:
            info = manager.get_skill(name)
            if info is None:
                console.print(f"[red]Skill not found:[/] {name}")
                raise typer.Exit(code=1)
            console.print(f"[yellow]Use /skills deactivate {info.name} during a chat session.[/]")

    else:
        console.print(f"[red]Unknown action: {action}[/]")
        console.print("[dim]Usage: pgimcode skills [list|view|use|deactivate] [name][/]")
        raise typer.Exit(code=1)


@app.command(name="chat")
def chat_command(
    model: str | None = typer.Option(None, "--model", "-M", help="Select AI model"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color output"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Auto-approve caution-level actions"),
    real: bool = typer.Option(False, "--real", help="Use real LLM agent (requires API key)"),
) -> None:
    """Start an interactive chat session (Claude Code-style UI)."""
    import asyncio

    settings = Settings()

    if model:
        ModelSelector.apply_model_selection(settings, model)

    if no_color:
        settings.color_enabled = False

    console = Console()

    approval_config = ApprovalConfig(auto_approve_caution=auto_approve)
    gate = ApprovalGate(config=approval_config, session_id="", bus=None, console=console)

    if not auto_approve:
        def prompt_user(action: str, details: str) -> bool:
            console.print(f"\n[yellow]🛑 Approval required:[/] {action}")
            console.print(f"[dim]{details}[/dim]")
            answer = console.input("Approve? [y/N]: ").strip().lower()
            return answer in ("y", "yes")
        gate.prompt_fn = prompt_user

    chat = ChatSession(
        console=console,
        settings=settings,
        approval_gate=gate,
        use_real=real,
    )

    try:
        asyncio.run(chat.start())
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/]")


# Entry point for CLI (used by poetry scripts)
def main() -> None:
    app()


if __name__ == "__main__":
    main()