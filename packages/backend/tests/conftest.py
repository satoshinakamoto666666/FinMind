import fnmatch
import os
import pytest
from app import create_app
from app.config import Settings
from app.extensions import db, redis_client
from app import models  # noqa: F401 - ensure models are registered


class _InMemoryRedis:
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, *args, **kwargs):
        self._store[key] = str(value)
        return True

    def setex(self, key, ttl, value):
        self._store[key] = str(value)
        return True

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                count += 1
        return count

    def scan(self, cursor=0, match=None, count=100):
        keys = list(self._store.keys())
        if match:
            keys = [k for k in keys if fnmatch.fnmatch(k, match)]
        return 0, keys

    def flushdb(self):
        self._store.clear()
        return True

    def ping(self):
        return True


_mem_redis = _InMemoryRedis()


def _patch_redis(monkeypatch):
    monkeypatch.setattr(redis_client, "get", _mem_redis.get)
    monkeypatch.setattr(redis_client, "set", _mem_redis.set)
    monkeypatch.setattr(redis_client, "setex", _mem_redis.setex)
    monkeypatch.setattr(redis_client, "delete", _mem_redis.delete)
    monkeypatch.setattr(redis_client, "scan", _mem_redis.scan)
    monkeypatch.setattr(redis_client, "flushdb", _mem_redis.flushdb)
    monkeypatch.setattr(redis_client, "ping", _mem_redis.ping)


class TestSettings(Settings):
    # Override defaults for tests
    database_url: str = "sqlite+pysqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/15"  # not used in tests
    jwt_secret: str = "test-secret"


def _setup_db(app):
    with app.app_context():
        db.create_all()


@pytest.fixture()
def app_fixture(monkeypatch):
    # Ensure a clean env for tests
    os.environ.setdefault("FLASK_ENV", "testing")
    _patch_redis(monkeypatch)
    settings = TestSettings(
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/15",
        jwt_secret="test-secret-with-32-plus-chars-1234567890",
    )
    app = create_app(settings)
    app.config.update(TESTING=True)
    _setup_db(app)
    redis_client.flushdb()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    redis_client.flushdb()


@pytest.fixture()
def client(app_fixture):
    return app_fixture.test_client()


@pytest.fixture()
def auth_header(client):
    # Register and login a default user, return auth header
    email = "test@example.com"
    password = "password123"
    r = client.post("/auth/register", json={"email": email, "password": password})
    register_debug = f"register failed: status={r.status_code}, body={r.get_json()}"
    assert r.status_code in (
        200,
        201,
        409,
    ), register_debug  # 409 if already exists
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    access = r.get_json()["access_token"]
    return {"Authorization": f"Bearer {access}"}
