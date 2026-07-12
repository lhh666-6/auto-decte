from fastapi import FastAPI


def test_canonical_api_entrypoint_remains_importable() -> None:
    from app.api.main import create_app

    assert isinstance(create_app(), FastAPI)
