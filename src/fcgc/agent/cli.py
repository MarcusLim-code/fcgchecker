"""Typed shell bridge used by native skills; no model or MCP server is launched."""

import json
from pathlib import Path
from typing import Annotated

import typer

from fcgc.agent.commands import invoke
from fcgc.agent.session import load_session, read_json, submit_result, summary
from fcgc.schemas.agent import HostContext

app = typer.Typer(help="Backend for Devin FCG skills and validated agent-mediated tool handoffs.")


@app.command("invoke")
def invoke_command(
    command: Annotated[
        str, typer.Option(help="Slash command with quoted arguments; parsed without a shell.")
    ],
    output: Annotated[Path, typer.Option(help="Fresh audit directory.")],
    host: Annotated[
        Path | None, typer.Option(help="Active host-observed tool capabilities; no credentials.")
    ] = None,
    allow_synthetic_handoff: Annotated[
        bool, typer.Option(help="Contract testing only, never live WD verification.")
    ] = False,
):
    try:
        context = HostContext.model_validate(read_json(host)) if host else None
        result = invoke(
            command, output, host=context, allow_synthetic_handoff=allow_synthetic_handoff
        )
        typer.echo(json.dumps(result, indent=2))
        if result.get("status") == "error":
            raise typer.Exit(1)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("submit")
def submit(
    session: Annotated[Path, typer.Option(help="Session audit directory.")],
    response: Annotated[Path, typer.Option(help="Bounded JSON tool-result or checker judgment.")],
):
    try:
        result = submit_result(session, response)
        typer.echo(json.dumps(result, indent=2))
        if result.get("status") == "error":
            raise typer.Exit(1)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("status")
def status(session: Annotated[Path, typer.Option()]):
    try:
        typer.echo(json.dumps(summary(load_session(session), session), indent=2))
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("schemas")
def schemas():
    from fcgc.schemas.agent import AgentJudgment, AgentToolResult

    typer.echo(
        json.dumps(
            {
                "tool_result": AgentToolResult.model_json_schema(),
                "judgment": AgentJudgment.model_json_schema(),
                "host": HostContext.model_json_schema(),
            },
            indent=2,
        )
    )
