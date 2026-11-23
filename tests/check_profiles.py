"""Smoke test of profile-guided deposition in this repository.

Runs against the repository's own services as an ordinary depositor and checks
the contract a repository builder relies on: the configuration API, saving an
incomplete draft, and publication through a publish request, which is refused
until the draft meets its profile. It leaves one published record and one
metadata-only draft.

Run with the repository's services up and its environment loaded:

    set -a; source variables; set +a
    .venv/bin/python tests/check_profiles.py
"""

import sys
from pathlib import Path

from invenio_access.permissions import authenticated_user, system_identity
from invenio_access.utils import get_identity
from invenio_accounts.proxies import current_datastore
from invenio_app.factory import create_api
from invenio_db import db
from invenio_requests.errors import CannotExecuteActionError
from marshmallow import ValidationError

FIXTURES = Path(__file__).parent / "fixtures"
EMAIL = "depositor@example.org"
PROFILE = {"id": "recorded-interview", "revision": "1.0"}
TRANSCRIPT = {"file_key": "interview.txt", "semantic_types": ["interview-transcript"]}
RECORDING = {"file_key": "interview.wav", "semantic_types": ["interview-recording"]}
REQUIRED = "Recordings: 0 of at least 1 file. Upload the recording of the interview."

failures = []


def report(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{': ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def refused(name, action):
    """Run `action`; pass when the profile check refuses it."""
    try:
        action()
    except ValidationError as error:
        report(name, REQUIRED in str(error.messages), str(error.messages))
    else:
        report(name, False, "not refused")


def depositor():
    user = current_datastore.get_user(EMAIL) or current_datastore.create_user(email=EMAIL, password=None, active=True)
    current_datastore.add_role_to_user(user, current_datastore.find_or_create_role("submitter"))
    db.session.commit()
    identity = get_identity(user)
    identity.provides.add(authenticated_user)
    return identity


def record_data(annotations, files_enabled=True):
    metadata = {
        "title": "Synthetic profile smoke test",
        "description": "Synthetic test data, not research data.",
        "resource_type": {"id": "dataset"},
        "publication_date": "2026-11-18",
        "creators": [{"person_or_org": {"type": "personal", "given_name": "Synthetic", "family_name": "Tester"}}],
        "pgd_deposition_profile": PROFILE if files_enabled else None,
        "pgd_file_annotations": annotations,
    }
    return {"access": {"record": "public", "files": "public"}, "files": {"enabled": files_enabled}, "metadata": metadata}


def upload(service, identity, id_, key):
    files = service.draft_files
    files.init_files(identity, id_, [{"key": key}])
    with open(FIXTURES / key, "rb") as stream:
        files.set_file_content(identity, id_, key, stream)
    files.commit_file(identity, id_, key)


def profile_errors(item):
    return [m for e in item.errors or [] if e["field"] == "metadata.pgd_file_annotations" for m in e["messages"]]


app = create_api()
with app.app_context():
    from invenio_records_resources.proxies import current_service_registry
    from oarepo_requests.proxies import current_requests_service

    service = current_service_registry.get("datasets")
    identity = depositor()

    response = app.test_client().get("/deposition-profiles?model=datasets", base_url="https://localhost")
    ids = [profile["id"] for profile in (response.get_json() or {}).get("profiles", [])]
    report("configuration API serves the model's profiles", response.status_code == 200 and PROFILE["id"] in ids, str(ids))

    # An incomplete draft is saved, with the profile problem reported.
    draft = service.create(identity, record_data([TRANSCRIPT]))
    id_ = draft.id
    upload(service, identity, id_, "interview.txt")
    saved = service.update_draft(identity, id_, record_data([TRANSCRIPT]))
    report("incomplete draft saves and reports the missing recording", profile_errors(saved) == [REQUIRED], str(profile_errors(saved)))
    stored = service.read_draft(identity, id_).data["metadata"]
    report("draft keeps profile and annotations", stored["pgd_deposition_profile"] == PROFILE and stored["pgd_file_annotations"] == [TRANSCRIPT])

    topic = service.read_draft(identity, id_)._record
    refused("publish request refused for an incomplete draft",
            lambda: current_requests_service.create(identity, {}, "publish_draft", topic=topic))

    # Complete the draft and submit a publish request.
    upload(service, identity, id_, "interview.wav")
    saved = service.update_draft(identity, id_, record_data([TRANSCRIPT, RECORDING]))
    report("complete draft saves without profile errors", not profile_errors(saved), str(saved.errors))
    topic = service.read_draft(identity, id_)._record
    request = current_requests_service.create(identity, {}, "publish_draft", topic=topic)
    current_requests_service.execute_action(identity, request.id, "submit")

    # The draft loses its recording annotation while the request waits. Accepting
    # validates the draft again; oarepo-requests reports a failed validation as
    # "cannot execute", so the cause is shown by validating the same draft directly.
    service.update_draft(system_identity, id_, record_data([TRANSCRIPT]))
    refused("the waiting draft no longer validates", lambda: service.validate_draft(system_identity, id_))
    try:
        current_requests_service.execute_action(identity, request.id, "accept")
        report("accepting the request is refused while the draft misses the recording", False, "accepted")
    except CannotExecuteActionError:
        report("accepting the request is refused while the draft misses the recording", True)
    db.session.rollback()

    # Restoring only the annotation makes the same request acceptable.
    service.update_draft(system_identity, id_, record_data([TRANSCRIPT, RECORDING]))
    current_requests_service.execute_action(identity, request.id, "accept")
    published = service.read(system_identity, id_).data["metadata"]
    report("accepted request publishes the record with its annotations",
           published["pgd_deposition_profile"] == PROFILE and published["pgd_file_annotations"] == [TRANSCRIPT, RECORDING])

    # Metadata-only records have no files to check.
    other = service.create(identity, record_data([], files_enabled=False))
    try:
        service.validate_draft(identity, other.id)
        report("metadata-only draft needs no profile", True)
    except ValidationError as error:
        report("metadata-only draft needs no profile", False, str(error.messages))

    print(f"records: {id_} (published), {other.id} (metadata-only draft)")

sys.exit(1 if failures else 0)
