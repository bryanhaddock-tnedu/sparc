from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ALEMBIC_VERSION_NUM_LIMIT = 32
MIGRATION_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def test_alembic_revision_identifiers_fit_default_version_column():
    revisions: list[str] = []
    for path in MIGRATION_DIR.glob("*.py"):
        spec = spec_from_file_location(path.stem, path)
        assert spec is not None
        assert spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        revision = getattr(module, "revision")
        revisions.append(revision)
        assert len(revision) <= ALEMBIC_VERSION_NUM_LIMIT, f"{path.name} revision is too long for alembic_version.version_num"

        down_revision = getattr(module, "down_revision")
        down_revisions = down_revision if isinstance(down_revision, tuple) else (down_revision,)
        for value in down_revisions:
            if value is not None:
                assert len(value) <= ALEMBIC_VERSION_NUM_LIMIT, f"{path.name} down_revision is too long for alembic_version.version_num"

    assert len(revisions) == len(set(revisions))
