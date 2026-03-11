# The management command python manage.py ingest_carbon_data serves as the entry point for cron jobs to trigger automated carbon data ingestion. When invoked (either by human CLI or cron scheduler), it orchestrates service layer functions that handle API requests and database writes.
import logging
import time
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from carbon.services.ingestion_service import (
    IngestionResult,
    ingest_national_actual,
    ingest_national_forecast,
    ingest_regional_forecast,
)

logger = logging.getLogger(__name__)


def _log(level: int, message: str, event: str, **context) -> None:
    logger.log(level, message, extra={"event": event, "context": context})


# Defines one CLI command, the name of this file, ingest_carbon_data. It will be launched when the command: python manage.py ingest_carbon_data is entered into the CLI
class Command(BaseCommand):
    # Shown in python manage.py help ingest_carbon_data
    help = "Ingest NESO Carbon Intensity Data"

    # A function which defines the optional CLI flags which can be appended to the core CLI command, python manage.py ingest_carbon_data
    # self refers to the instance of the Command class in question - one self per command execution of python manage.py ingest_carbon_data
    # parser is an argparse parser object. The argparse module makes it easy to write user-friendly CLIs
    def add_arguments(self, parser):
        # Enforce that at most one "only" mode can be selected per command run.
        only_group = parser.add_mutually_exclusive_group()

        only_group.add_argument(
            "--national-only",
            # Boolean flag: present => True, absent => False
            action="store_true",
            help="Ingest national forecast only",
        )
        only_group.add_argument(
            "--regional-only",
            action="store_true",
            help="Ingest regional forecast only",
        )
        only_group.add_argument(
            "--actual-only",
            action="store_true",
            help="Ingest national actual data only",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run ingestion without writing to the database",
        )

    # A function which orchestrates service layer functions in relation to each of the flags defined in def add_arguments() above.
    # Ran when python manage.py ingest_carbon_data is executed, but after def add_arguments() has completed.
    # *args ensures that an unknown number of arbitrary arguments, of data type tuple, can be passed into def handle(). In this case, *args is often empty and is preserved for positional arguments (if defined).
    # **options ensures that an unknown number of keyword arguments can be collected into a dict to then be passed into def handle(). The data associated with each keyword, in this case the --national-only etc. flags, can be accessed via dict index, options["national_only"] (option keys do not include leading dashes)
    def handle(self, *args, **options):
        run_id = uuid.uuid4().hex
        started_at = time.monotonic()

        # Access the parsed option keys from add_arguments(). Each is a bool (True if flag present, False if absent)
        national_only = options["national_only"]
        regional_only = options["regional_only"]
        actual_only = options["actual_only"]
        dry_run = options["dry_run"]

        # Derive which ingestion jobs should run based on flag combinations
        run_national = national_only or not (regional_only or actual_only)
        run_regional = regional_only or not (national_only or actual_only)
        run_actual = actual_only or not (national_only or regional_only)

        _log(
            logging.INFO,
            "Starting carbon data ingestion command",
            "ingestion_command_started",
            run_id=run_id,
            dry_run=dry_run,
            run_national=run_national,
            run_regional=run_regional,
            run_actual=run_actual,
        )

        self.stdout.write(self.style.NOTICE("Starting carbon data ingestion..."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY RUN mode..."))

        total = IngestionResult()

        try:
            if run_national:
                self._run_step(
                    run_id=run_id,
                    dry_run=dry_run,
                    step_name="national_forecast",
                    cli_message="Ingesting national forecast...",
                    ingest_fn=ingest_national_forecast,
                    total=total,
                )

            if run_regional:
                self._run_step(
                    run_id=run_id,
                    dry_run=dry_run,
                    step_name="regional_forecast",
                    cli_message="Ingesting regional forecast...",
                    ingest_fn=ingest_regional_forecast,
                    total=total,
                )

            if run_actual:
                self._run_step(
                    run_id=run_id,
                    dry_run=dry_run,
                    step_name="national_actual",
                    cli_message="Ingesting national actual...",
                    ingest_fn=ingest_national_actual,
                    total=total,
                )

            self._print_summary(total)

            _log(
                logging.INFO,
                "Completed carbon data ingestion command",
                "ingestion_command_completed",
                run_id=run_id,
                dry_run=dry_run,
                records_created=total.records_created,
                records_updated=total.records_updated,
                records_skipped=total.records_skipped,
                records_failed=total.records_failed,
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )

            if total.records_failed > 0:
                raise CommandError(
                    f"Carbon data ingestion completed with {total.records_failed} failed record(s)."
                )

        except CommandError as exc:
            _log(
                logging.ERROR,
                "Carbon data ingestion command failed",
                "ingestion_command_error",
                run_id=run_id,
                error_message=str(exc),
                records_created=total.records_created,
                records_updated=total.records_updated,
                records_skipped=total.records_skipped,
                records_failed=total.records_failed,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Carbon data ingestion failed unexpectedly",
                extra={
                    "event": "ingestion_command_unexpected_error",
                    "context": {
                        "run_id": run_id,
                        "error_message": str(exc),
                    },
                },
            )
            self.stderr.write(
                self.style.ERROR(f"Carbon data ingestion failed unexpectedly: {exc}")
            )
            raise CommandError("Carbon data ingestion failed unexpectedly.") from exc

    def _run_step(self, run_id, dry_run, step_name, cli_message, ingest_fn, total):
        self.stdout.write(self.style.NOTICE(cli_message))
        step_started_at = time.monotonic()

        _log(
            logging.INFO,
            "Starting ingestion step",
            "ingestion_command_step_started",
            run_id=run_id,
            step=step_name,
            dry_run=dry_run,
        )

        if dry_run:
            # Django's transaction.atomic() allows the following code to run as if writing to a DB in production.
            # Atomicity in this context relates to all-or-nothing series of database operations.
            with transaction.atomic():
                result = ingest_fn()
                # All DB writes rolled back at the end, preventing persistence. Rollback is forced even if no exception occurs:
                transaction.set_rollback(True)
        else:
            result = ingest_fn()

        self._accumulate(total, result)

        _log(
            logging.INFO,
            "Completed ingestion step",
            "ingestion_command_step_completed",
            run_id=run_id,
            step=step_name,
            dry_run=dry_run,
            records_created=result.records_created,
            records_updated=result.records_updated,
            records_skipped=result.records_skipped,
            records_failed=result.records_failed,
            duration_ms=int((time.monotonic() - step_started_at) * 1000),
        )

    def _accumulate(self, total, result):
        total.records_created += result.records_created
        total.records_updated += result.records_updated
        total.records_skipped += result.records_skipped
        total.records_failed += result.records_failed

    def _print_summary(self, result):
        self.stdout.write("")
        if result.records_failed > 0:
            self.stdout.write(self.style.ERROR("Ingestion completed with failures"))
        else:
            self.stdout.write(self.style.SUCCESS("Ingestion complete"))
        self.stdout.write(f"Created : {result.records_created}")
        self.stdout.write(f"Updated : {result.records_updated}")
        self.stdout.write(f"Skipped : {result.records_skipped}")
        self.stdout.write(f"Failed : {result.records_failed}")
