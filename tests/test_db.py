"""Tests for Context Engine database layer."""

import os
import tempfile
import pytest

from context_engine import db


@pytest.fixture
def tmp_db():
    """Create a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.init_db(path)
    yield path
    os.unlink(path)


class TestInit:
    def test_init_creates_db(self, tmp_db):
        result = db.stats(db_path=tmp_db)
        assert "people" in result
        assert result["people"]["total"] == 0

    def test_init_creates_scan_log(self, tmp_db):
        scans = db.scan_status(db_path=tmp_db)
        sources = {s["source"] for s in scans}
        assert sources == {"gmail", "slack", "asana", "drive", "calendar"}

    def test_init_idempotent(self, tmp_db):
        # Second init should not fail
        db.init_db(tmp_db)
        result = db.stats(db_path=tmp_db)
        assert "people" in result


class TestAddAndFind:
    def test_add_person(self, tmp_db):
        result = db.add_record("people", {"name": "Martin Marko", "email": "martin@test.sk", "domain": "work"}, tmp_db)
        assert result["status"] == "ok"
        assert result["id"] == 1

    def test_add_person_duplicate(self, tmp_db):
        db.add_record("people", {"name": "Martin Marko", "email": "martin@test.sk"}, tmp_db)
        result = db.add_record("people", {"name": "Martin Marko", "email": "martin@test.sk"}, tmp_db)
        assert result["status"] == "duplicate"

    def test_add_company(self, tmp_db):
        result = db.add_record("companies", {"name": "Test Firma", "type": "klient", "domain": "work"}, tmp_db)
        assert result["status"] == "ok"

    def test_add_project(self, tmp_db):
        result = db.add_record("projects", {"name": "Projekt X", "domain": "work"}, tmp_db)
        assert result["status"] == "ok"

    def test_add_rule(self, tmp_db):
        result = db.add_record("rules", {"context": "Email klientom", "rule": "Vykat", "domain": "work"}, tmp_db)
        assert result["status"] == "ok"

    def test_add_note(self, tmp_db):
        result = db.add_note({
            "title": "Heslo k wifi", "content": "abc123",
            "domain": "home", "category": "reference",
            "tags": '["password", "2026-W17"]', "source": "manual-input",
        }, tmp_db, skip_dedupe_check=True)
        assert result["status"] == "ok"

    def test_add_note_missing_required(self, tmp_db):
        result = db.add_note({"title": "T", "content": "x", "domain": "home", "category": "reference"}, tmp_db, skip_dedupe_check=True)
        assert result["status"] == "error"
        assert result["code"] == "VALIDATION_FAILED"

    def test_add_note_alias_normalization(self, tmp_db):
        result = db.add_note({
            "title": "Q&A Peter", "content": "meeting content here",
            "domain": "work", "category": "meeting",
            "tags": '["test", "2026-W17"]', "source": "test",
        }, tmp_db, skip_dedupe_check=True)
        assert result["status"] == "ok"
        assert any("normalized" in w for w in result.get("warnings", []))

    def test_find_person(self, tmp_db):
        db.add_record("people", {"name": "Martin Marko", "email": "martin@test.sk"}, tmp_db)
        result = db.find("Martin", db_path=tmp_db)
        assert result["total"] >= 1
        assert any(p["name"] == "Martin Marko" for p in result["results"].get("people", []))

    def test_find_with_domain_filter(self, tmp_db):
        db.add_record("people", {"name": "Work Person", "domain": "work"}, tmp_db)
        db.add_record("people", {"name": "Personal Person", "email": "p@p.sk", "domain": "personal"}, tmp_db)

        work_results = db.find("Person", domain="work", db_path=tmp_db)
        personal_results = db.find("Person", domain="personal", db_path=tmp_db)

        work_names = [p["name"] for p in work_results["results"].get("people", [])]
        personal_names = [p["name"] for p in personal_results["results"].get("people", [])]

        assert "Work Person" in work_names
        assert "Personal Person" not in work_names
        assert "Personal Person" in personal_names

    def test_find_notes(self, tmp_db):
        db.add_note({
            "title": "Wifi heslo doma", "content": "SuperSecret123",
            "domain": "home", "category": "reference",
            "tags": '["password", "2026-W17"]', "source": "test",
        }, tmp_db, skip_dedupe_check=True)
        db.add_note({
            "title": "Fitness plan", "content": "3x tyzdenne",
            "domain": "health", "category": "health-record",
            "tags": '["fitness", "2026-W17"]', "source": "test",
        }, tmp_db, skip_dedupe_check=True)

        result = db.find_notes("wifi", db_path=tmp_db)
        assert result["total"] >= 1

        result = db.find_notes("plan", domain="health", db_path=tmp_db)
        assert result["total"] >= 1

    def test_invalid_table(self, tmp_db):
        with pytest.raises(ValueError, match="Invalid table"):
            db.add_record("evil_table", {"name": "hack"}, tmp_db)


class TestGetDetails:
    def test_get_person(self, tmp_db):
        db.add_record("people", {"name": "Jana Nova", "email": "jana@test.sk", "role": "CTO"}, tmp_db)
        result = db.get_person("Jana", db_path=tmp_db)
        assert result["name"] == "Jana Nova"
        assert result["role"] == "CTO"

    def test_get_person_not_found(self, tmp_db):
        result = db.get_person("Neexistuje", db_path=tmp_db)
        assert "error" in result

    def test_get_company_with_people(self, tmp_db):
        db.add_record("companies", {"name": "Firma SK"}, tmp_db)
        db.add_record("people", {"name": "Jana", "company_name": "Firma SK"}, tmp_db)
        result = db.get_company("Firma SK", db_path=tmp_db)
        assert result["name"] == "Firma SK"
        assert len(result["people"]) == 1

    def test_get_project(self, tmp_db):
        db.add_record("projects", {"name": "Rebrand", "description": "Novy brand"}, tmp_db)
        result = db.get_project("Rebrand", db_path=tmp_db)
        assert result["name"] == "Rebrand"

    def test_context_for(self, tmp_db):
        db.add_record("companies", {"name": "TestCo"}, tmp_db)
        db.add_record("people", {"name": "Peter Test", "email": "peter@test.sk", "company_name": "TestCo", "formality": "ty", "tone": "priatelsky"}, tmp_db)
        db.add_record("rules", {"context": "Komunikacia s TestCo", "rule": "Vzdy tykat", "applies_to": '["TestCo"]'}, tmp_db)

        result = db.context_for("Peter", db_path=tmp_db)
        assert result["person"]["name"] == "Peter Test"
        assert result["communication"]["formality"] == "ty"
        assert len(result["rules"]) >= 1

    def test_get_note(self, tmp_db):
        add_result = db.add_note({
            "title": "Test Note", "content": "content body",
            "domain": "personal", "category": "reference",
            "tags": '["test", "2026-W17"]', "source": "test",
        }, tmp_db, skip_dedupe_check=True)
        assert add_result["status"] == "ok", add_result
        note = db.get_note(add_result["id"], db_path=tmp_db)
        assert note["title"] == "Test Note"


class TestUpdate:
    def test_update_record(self, tmp_db):
        db.add_record("people", {"name": "Update Test"}, tmp_db)
        result = db.update_record("people", 1, {"role": "CEO", "notes": "updated"}, tmp_db)
        assert result["status"] == "ok"
        assert result["record"]["role"] == "CEO"

    def test_update_not_found(self, tmp_db):
        result = db.update_record("people", 999, {"role": "CEO"}, tmp_db)
        assert result["status"] == "error"


class TestInteractions:
    def test_log_interaction(self, tmp_db):
        db.add_record("people", {"name": "Log Test"}, tmp_db)
        result = db.log_interaction({
            "person_id": 1,
            "person_name": "Log Test",
            "channel": "email",
            "direction": "outgoing",
            "summary": "Test email",
            "domain": "work",
        }, tmp_db)
        assert result["status"] == "ok"

    def test_interaction_appears_in_person(self, tmp_db):
        db.add_record("people", {"name": "Log Test"}, tmp_db)
        db.log_interaction({"person_id": 1, "person_name": "Log Test", "channel": "email", "summary": "Test"}, tmp_db)
        person = db.get_person("Log Test", db_path=tmp_db)
        assert len(person["recent_interactions"]) == 1


class TestStats:
    def test_stats_empty(self, tmp_db):
        result = db.stats(db_path=tmp_db)
        assert result["people"]["total"] == 0

    def test_stats_with_data(self, tmp_db):
        db.add_record("people", {"name": "A", "domain": "work"}, tmp_db)
        db.add_record("people", {"name": "B", "email": "b@b.sk", "domain": "personal"}, tmp_db)
        result = db.stats(db_path=tmp_db)
        assert result["people"]["total"] == 2
        assert "domains" in result

    def test_stats_domain_filter(self, tmp_db):
        db.add_record("people", {"name": "A", "domain": "work"}, tmp_db)
        db.add_record("people", {"name": "B", "email": "b@b.sk", "domain": "personal"}, tmp_db)
        result = db.stats(domain="work", db_path=tmp_db)
        assert result["people"]["total"] == 1


class TestMaintenanceQueries:
    def test_stale(self, tmp_db):
        result = db.stale(days=0, db_path=tmp_db)
        assert result["total_stale"] == 0

    def test_incomplete(self, tmp_db):
        db.add_record("people", {"name": "Incomplete", "status": "to_verify"}, tmp_db)
        result = db.incomplete(db_path=tmp_db)
        assert result["total_incomplete"] >= 1

    def test_recent(self, tmp_db):
        db.add_record("people", {"name": "Recent Test"}, tmp_db)
        result = db.recent(days=1, db_path=tmp_db)
        assert result["total_changes"] >= 1

    def test_export(self, tmp_db):
        db.add_record("people", {"name": "Export Test"}, tmp_db)
        result = db.export_data(db_path=tmp_db)
        assert "people" in result
        assert len(result["people"]) == 1


class TestScanManagement:
    def test_scan_status(self, tmp_db):
        scans = db.scan_status(db_path=tmp_db)
        assert len(scans) == 5

    def test_set_scan_marker(self, tmp_db):
        result = db.set_scan_marker("gmail", "2026-02-27T06:00:00", db_path=tmp_db)
        assert result["status"] == "ok"

        scans = db.scan_status(db_path=tmp_db)
        gmail = next(s for s in scans if s["source"] == "gmail")
        assert gmail["last_scan"] == "2026-02-27T06:00:00"

    def test_update_scan_stats(self, tmp_db):
        result = db.update_scan_stats("gmail", 100, 5, 3, "Test scan", db_path=tmp_db)
        assert result["status"] == "ok"


class TestBulkImport:
    def test_import_people(self, tmp_db):
        data = {
            "people": [
                {"name": "Import Test 1", "email": "import1@test.sk", "domain": "work"},
                {"name": "Import Test 2", "email": "import2@test.sk", "role": "CTO"},
            ]
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_added"] == 2
        assert result["tables"]["people"]["added"] == 2

        stats = db.stats(db_path=tmp_db)
        assert stats["people"]["total"] == 2

    def test_import_companies_and_people(self, tmp_db):
        data = {
            "companies": [
                {"name": "Firma A", "type": "klient", "domain": "work"},
                {"name": "Firma B", "type": "partner"},
            ],
            "people": [
                {"name": "Clovek A", "company_name": "Firma A"},
                {"name": "Clovek B", "company_name": "Firma B", "email": "b@test.sk"},
            ],
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_added"] == 4
        assert result["tables"]["companies"]["added"] == 2
        assert result["tables"]["people"]["added"] == 2

    def test_import_skip_duplicates(self, tmp_db):
        db.add_record("people", {"name": "Existujuci", "email": "exist@test.sk"}, tmp_db)

        data = {
            "people": [
                {"name": "Existujuci", "email": "exist@test.sk"},
                {"name": "Novy Clovek", "email": "novy@test.sk"},
            ]
        }
        result = db.bulk_import(data, on_duplicate="skip", db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_added"] == 1
        assert result["total_skipped"] == 1
        assert result["tables"]["people"]["skipped"] == 1

    def test_import_update_duplicates(self, tmp_db):
        db.add_record("people", {"name": "Update Me", "email": "update@test.sk", "role": "Junior"}, tmp_db)

        data = {
            "people": [
                {"name": "Update Me", "email": "update@test.sk", "role": "Senior"},
            ]
        }
        result = db.bulk_import(data, on_duplicate="update", db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_updated"] == 1

        person = db.get_person("Update Me", db_path=tmp_db)
        assert person["role"] == "Senior"

    def test_import_notes(self, tmp_db):
        data = {
            "notes": [
                {"title": "Poznamka 1", "content": "Obsah 1", "domain": "home", "category": "reference"},
                {"title": "Poznamka 2", "content": "Obsah 2", "domain": "health"},
            ]
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["tables"]["notes"]["added"] == 2

    def test_import_rules(self, tmp_db):
        data = {
            "rules": [
                {"context": "Email klientom", "rule": "Vzdy vykat", "priority": "high"},
                {"context": "Slack tim", "rule": "Tykat", "priority": "low"},
            ]
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["tables"]["rules"]["added"] == 2

    def test_import_projects_and_products(self, tmp_db):
        data = {
            "projects": [
                {"name": "Projekt Alpha", "description": "Test projekt", "domain": "work"},
            ],
            "products": [
                {"name": "Produkt X", "price": "99 EUR", "format": "digitalny"},
            ],
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["tables"]["projects"]["added"] == 1
        assert result["tables"]["products"]["added"] == 1

    def test_import_unknown_table(self, tmp_db):
        data = {"evil_table": [{"name": "hack"}]}
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "error"
        assert "Unknown tables" in result["error"]

    def test_import_invalid_records(self, tmp_db):
        data = {
            "people": [
                "not a dict",
                {"name": "Valid Person"},
                {"email": "no-name@test.sk"},  # missing required 'name'
            ]
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["tables"]["people"]["added"] == 1
        assert result["tables"]["people"]["errors"] == 2

    def test_import_empty(self, tmp_db):
        result = db.bulk_import({}, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_added"] == 0

    def test_import_strips_readonly_fields(self, tmp_db):
        """Import should ignore id, created_at, first_seen, updated_at from export data."""
        data = {
            "people": [
                {
                    "id": 999,
                    "name": "Stripped Fields",
                    "email": "stripped@test.sk",
                    "created_at": "2020-01-01",
                    "first_seen": "2020-01-01",
                    "updated_at": "2020-01-01",
                },
            ]
        }
        result = db.bulk_import(data, db_path=tmp_db)
        assert result["status"] == "ok"
        assert result["total_added"] == 1

        person = db.get_person("Stripped Fields", db_path=tmp_db)
        assert person["id"] != 999  # ID should be auto-assigned

    def test_import_roundtrip_with_export(self, tmp_db):
        """Data exported via ctx_export should be importable via ctx_import."""
        # Seed some data
        db.add_record("companies", {"name": "Roundtrip Co", "type": "klient"}, tmp_db)
        db.add_record("people", {"name": "Roundtrip Person", "email": "rt@test.sk", "company_name": "Roundtrip Co"}, tmp_db)
        db.add_record("rules", {"context": "Test", "rule": "Test rule"}, tmp_db)
        db.add_note({"title": "Test Note", "content": "content"}, tmp_db)

        # Export
        exported = db.export_data(db_path=tmp_db)
        assert len(exported["people"]) == 1
        assert len(exported["companies"]) == 1

        # Import into fresh DB
        import tempfile
        fd2, path2 = tempfile.mkstemp(suffix=".db")
        os.close(fd2)
        try:
            db.init_db(path2)
            result = db.bulk_import(exported, db_path=path2)
            assert result["status"] == "ok"
            assert result["total_added"] >= 3  # company + person + rule + note

            stats = db.stats(db_path=path2)
            assert stats["companies"]["total"] == 1
            assert stats["people"]["total"] == 1
            assert stats["rules"]["total"] == 1
        finally:
            os.unlink(path2)
