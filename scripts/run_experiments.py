"""Run the experiment for a release: three forks per dependent, then triage and fix the breaks.

The implementation lives in floodplain/runner.py so the installed `floodplain` command can use
it; this script keeps the documented invocation working.

    uv run python scripts/run_experiments.py --target openai --release 3.0.0 --stage all
"""

from floodplain.runner import cli

if __name__ == "__main__":
    cli()
