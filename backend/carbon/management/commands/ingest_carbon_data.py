# The management command python manage.py ingest_carbon_data serves as the entry point for cron jobs to trigger automated carbon data ingestion. When invoked (either by human CLI or cron scheduler), it orchestrates service layer functions that handle API requests and database writes.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from carbon.services.ingestion_service import (
    IngestionResult,
    ingest_national_forecast,
    ingest_regional_forecast,
    ingest_national_actual
)

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
            help="Ingest national forecast only"
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
    # A function which orchestrates service layer functions (imported from ingestion_service.py at the top of this file) in relation to each of the flags defined in def add_arguments() above
    # Ran when python manage.py ingest_carbon_data is executed, but after def add_arguments() has completed
    # *args ensures that an unknown number of arbitrary arguments, of data type tuple, can be passed into def handle(). In this case, *args is often empty and is preserved for positional arguments (if defined).
    # **options ensures that an unknown number of keyword arguments can be collected into a dict to then be passed into def handle(). The data associated with each keyword, in this case the --national-only etc. flags, can be accessed via dict index, options["national_only"] (option keys do not include leading dashes)
    def handle(self, *args, **options):
        # Access the parsed option key "national_only" from the options within def add_arguments(). Assign it as a bool value (see the action="store_true" lines above) to 'national_only'
        national_only = options["national_only"]
        regional_only = options["regional_only"]
        actual_only = options["actual_only"]
        dry_run = options["dry_run"]
        # stdout - the standard output from the BaseCommand class
        # style determines console output formatting
        self.stdout.write(self.style.NOTICE("Starting carbon data ingestion..."))

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY RUN mode..."))

        total = IngestionResult()
        # The following variables are needed to decide which ingestion jobs should run based on flag combinations
        run_national = national_only or not (regional_only or actual_only)
        run_regional = regional_only or not (national_only or actual_only)
        run_actual = actual_only or not (national_only or regional_only)

        # If 0/3 flagged argument objects in add_arguments() or if only --national-only passed:
        if run_national:
            # If dry_run, and records aren't written to the DB
            if dry_run:
                # Django's transaction.atomic() allows the following code to run as if writing to a DB in production. Atomicity in this context relates to all or nothing series of database operations - either all operations succeed or they all fail. No partial commits are allowed
                with transaction.atomic():
                    # Write to the console this NOTICE method to confirm the orchestration process has started for option["national_only"]
                    self.stdout.write(self.style.NOTICE("Ingesting national forecast..."))
                    # Call ingest_national_forecast(), and assign the return value to result
                    result = ingest_national_forecast()
                    # All DB writes to be rolled back at the end, preventing the writing of these records to the DB. In this context, rollback is forced even if no exception occurs, extending the protection against DB writing:
                    transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.NOTICE("Ingesting national forecast..."))
                result = ingest_national_forecast()
            # For this instance of the Command class processed, relative to run_national only, update IngestionResult() with the total int value against the corresponding result key
            self._accumulate(total, result)

        if run_regional:
            if dry_run:
                with transaction.atomic():
                    self.stdout.write(self.style.NOTICE("Ingesting regional forecast..."))
                    result = ingest_regional_forecast()
                    transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.NOTICE("Ingesting regional forecast..."))
                result = ingest_regional_forecast()
            self._accumulate(total, result)

        if run_actual:
            if dry_run:
                with transaction.atomic():
                    self.stdout.write(self.style.NOTICE("Ingesting national actual..."))
                    result = ingest_national_actual()
                    transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.NOTICE("Ingesting national actual..."))
                result = ingest_national_actual()
            self._accumulate(total, result)
        
        self._print_summary(total)


    def _accumulate(self, total, result):
        total.records_created += result.records_created
        total.records_updated += result.records_updated
        total.records_skipped += result.records_skipped
        total.records_failed += result.records_failed

    def _print_summary(self, result):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Ingestion complete"))
        self.stdout.write(f"Created : {result.records_created}")
        self.stdout.write(f"Updated : {result.records_updated}")
        self.stdout.write(f"Skipped : {result.records_skipped}")
        self.stdout.write(f"Failed : {result.records_failed}")