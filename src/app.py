"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")

TEACHERS_FILE = current_dir / "teachers.json"
SESSION_COOKIE_NAME = "teacher_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
teacher_sessions: dict[str, tuple[str, float]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash suitable for storing in teachers.json."""
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return f"pbkdf2_sha256${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against the salted hash stored for a teacher."""
    try:
        algorithm, salt_hex, expected_hash_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(expected_hash_hex)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return hmac.compare_digest(actual_hash, expected_hash)


def load_teacher_accounts() -> list[dict[str, str]]:
    """Read and validate the locally provisioned teacher accounts."""
    with TEACHERS_FILE.open(encoding="utf-8") as teacher_file:
        data = json.load(teacher_file)

    if not isinstance(data, dict) or not isinstance(data.get("teachers"), list):
        raise RuntimeError("teachers.json must contain a 'teachers' list.")

    accounts = data["teachers"]
    for account in accounts:
        if (
            not isinstance(account, dict)
            or not isinstance(account.get("username"), str)
            or not isinstance(account.get("password_hash"), str)
        ):
            raise RuntimeError(
                "Each teacher account must include a username and password_hash."
            )
        try:
            algorithm, salt_hex, password_hash_hex = account["password_hash"].split("$")
            salt = bytes.fromhex(salt_hex)
            password_hash = bytes.fromhex(password_hash_hex)
        except ValueError as error:
            raise RuntimeError("A teacher account has an invalid password hash.") from error
        if algorithm != "pbkdf2_sha256" or len(salt) != 16 or len(password_hash) != 32:
            raise RuntimeError("A teacher account has an invalid password hash.")
    return accounts


def get_authenticated_teacher(request: Request) -> str:
    """Resolve the teacher identity from the server-side session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    session = teacher_sessions.get(token or "")
    if session is None or session[1] <= time.time():
        if token:
            teacher_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Teacher login required")
    return session[0]

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(credentials: LoginRequest, request: Request, response: Response):
    if not TEACHERS_FILE.is_file():
        raise HTTPException(status_code=503, detail="Teacher accounts are not configured")

    for account in load_teacher_accounts():
        if account["username"] == credentials.username and verify_password(
            credentials.password, account["password_hash"]
        ):
            token = secrets.token_urlsafe(32)
            teacher_sessions[token] = (
                account["username"],
                time.time() + SESSION_TTL_SECONDS,
            )
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=token,
                max_age=SESSION_TTL_SECONDS,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
                path="/",
            )
            return {"username": account["username"]}

    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.get("/auth/me")
def get_current_teacher(teacher: str = Depends(get_authenticated_teacher)):
    return {"username": teacher}


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        teacher_sessions.pop(token, None)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"message": "Logged out"}


@app.post(
    "/activities/{activity_name}/signup",
    dependencies=[Depends(get_authenticated_teacher)],
)
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete(
    "/activities/{activity_name}/unregister",
    dependencies=[Depends(get_authenticated_teacher)],
)
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
