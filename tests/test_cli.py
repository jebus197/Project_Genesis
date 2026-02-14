"""Tests for Genesis CLI — proves CLI dispatches correctly."""

import pytest
from genesis.cli import main, build_parser


class TestCLIParsing:
    def test_status_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_register_actor_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "register-actor", "--id", "alice",
            "--kind", "human", "--region", "NA", "--org", "Org1",
        ])
        assert args.command == "register-actor"
        assert args.id == "alice"
        assert args.kind == "human"

    def test_create_mission_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "create-mission", "--id", "M-001",
            "--title", "Test", "--class", "documentation_update",
        ])
        assert args.command == "create-mission"
        assert args.mission_class == "documentation_update"


class TestCLIExecution:
    def test_status_runs(self) -> None:
        exit_code = main(["status"])
        assert exit_code == 0

    def test_check_invariants_runs(self) -> None:
        exit_code = main(["check-invariants"])
        assert exit_code == 0

    def test_no_command_shows_help(self, capsys) -> None:
        exit_code = main([])
        assert exit_code == 0

    def test_register_actor_e2e(self) -> None:
        exit_code = main([
            "register-actor", "--id", "cli_test_actor",
            "--kind", "human", "--region", "EU", "--org", "TestOrg",
        ])
        assert exit_code == 0

    def test_create_mission_e2e(self) -> None:
        exit_code = main([
            "create-mission", "--id", "M-CLI-001",
            "--title", "CLI test mission",
            "--class", "documentation_update",
        ])
        assert exit_code == 0
