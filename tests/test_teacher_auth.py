import asyncio
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from src import app as app_module


async def _asgi_request(method, path, *, query=None, body=None, cookie=None):
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    headers = [(b"host", b"testserver")]
    if body is not None:
        headers.extend(
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode("ascii")),
            ]
        )
    if cookie:
        headers.append((b"cookie", f"teacher_session={cookie}".encode("ascii")))

    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {
                "type": "http.request",
                "body": body_bytes,
                "more_body": False,
            }
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": urlencode(query or {}).encode("ascii"),
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
        "extensions": {},
    }
    await app_module.app(scope, receive, send)

    response_start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    response_headers = dict(response_start["headers"])
    return response_start["status"], response_headers, json.loads(response_body)


class TeacherAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.teachers_file = Path(self.temp_dir.name) / "teachers.json"
        self.teachers_file.write_text(
            json.dumps(
                {
                    "teachers": [
                        {
                            "username": "teacher",
                            "password_hash": app_module.hash_password("correct horse"),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.teachers_file_patch = patch.object(
            app_module, "TEACHERS_FILE", self.teachers_file
        )
        self.teachers_file_patch.start()
        self.original_activities = deepcopy(app_module.activities)
        app_module.activities.clear()
        app_module.activities["Chess"] = {
            "description": "Chess",
            "schedule": "Fridays",
            "max_participants": 3,
            "participants": ["student@mergington.edu"],
        }
        app_module.teacher_sessions.clear()

    def tearDown(self):
        app_module.teacher_sessions.clear()
        app_module.activities.clear()
        app_module.activities.update(self.original_activities)
        self.teachers_file_patch.stop()
        self.temp_dir.cleanup()

    def test_activity_listing_is_public_but_mutations_require_teacher(self):
        status, _, activities = asyncio.run(_asgi_request("GET", "/activities"))
        self.assertEqual(status, 200)
        self.assertIn("student@mergington.edu", activities["Chess"]["participants"])

        signup_status, _, _ = asyncio.run(
            _asgi_request(
                "POST",
                "/activities/Chess/signup",
                query={"email": "new@mergington.edu"},
            )
        )
        unregister_status, _, _ = asyncio.run(
            _asgi_request(
                "DELETE",
                "/activities/Chess/unregister",
                query={"email": "student@mergington.edu"},
            )
        )

        self.assertEqual(signup_status, 401)
        self.assertEqual(unregister_status, 401)
        self.assertEqual(
            app_module.activities["Chess"]["participants"],
            ["student@mergington.edu"],
        )

    def test_authenticated_teacher_can_register_and_unregister_students(self):
        login_status, login_headers, login_result = asyncio.run(
            _asgi_request(
                "POST",
                "/auth/login",
                body={"username": "teacher", "password": "correct horse"},
            )
        )
        self.assertEqual(login_status, 200)
        self.assertEqual(login_result["username"], "teacher")
        set_cookie = login_headers[b"set-cookie"].decode("ascii")
        self.assertIn("httponly", set_cookie.lower())
        cookie = set_cookie.split(";", 1)[0]
        token = cookie.split("=", 1)[1]
        current_status, _, current_teacher = asyncio.run(
            _asgi_request("GET", "/auth/me", cookie=token)
        )
        self.assertEqual(current_status, 200)
        self.assertEqual(current_teacher["username"], "teacher")

        signup_status, _, _ = asyncio.run(
            _asgi_request(
                "POST",
                "/activities/Chess/signup",
                query={"email": "new@mergington.edu"},
                cookie=token,
            )
        )
        unregister_status, _, _ = asyncio.run(
            _asgi_request(
                "DELETE",
                "/activities/Chess/unregister",
                query={"email": "student@mergington.edu"},
                cookie=token,
            )
        )

        self.assertEqual(unregister_status, 200)
        self.assertEqual(signup_status, 200)
        self.assertEqual(
            app_module.activities["Chess"]["participants"],
            ["new@mergington.edu"],
        )

        logout_status, _, _ = asyncio.run(
            _asgi_request("POST", "/auth/logout", cookie=token)
        )
        self.assertEqual(logout_status, 200)
        post_logout_status, _, _ = asyncio.run(
            _asgi_request(
                "POST",
                "/activities/Chess/signup",
                query={"email": "another@mergington.edu"},
                cookie=token,
            )
        )
        self.assertEqual(post_logout_status, 401)

    def test_invalid_teacher_credentials_are_rejected(self):
        status, _, _ = asyncio.run(
            _asgi_request(
                "POST",
                "/auth/login",
                body={"username": "teacher", "password": "wrong password"},
            )
        )
        self.assertEqual(status, 401)

    def test_login_reports_missing_teacher_configuration(self):
        self.teachers_file.unlink()
        status, _, result = asyncio.run(
            _asgi_request(
                "POST",
                "/auth/login",
                body={"username": "teacher", "password": "correct horse"},
            )
        )

        self.assertEqual(status, 503)
        self.assertEqual(result["detail"], "Teacher accounts are not configured")


if __name__ == "__main__":
    unittest.main()
