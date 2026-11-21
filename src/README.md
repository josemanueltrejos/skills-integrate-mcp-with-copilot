# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Log in as a teacher; sets an HTTP-only session cookie                |
| GET    | `/auth/me`                                                        | Get the current teacher session                                     |
| POST   | `/auth/logout`                                                    | End the current teacher session                                     |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Teacher-only student sign-up                                        |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Teacher-only student removal                                      |

Only authenticated teachers can register or unregister students. Students and
other visitors can still browse activities and see who is registered.

### Provisioning teacher accounts

Teacher accounts are stored locally in `src/teachers.json`; this file is
git-ignored and contains salted PBKDF2 password hashes, not plaintext passwords.
From the repository root, add an assigned teacher account with:

```
python src/manage_teachers.py teacher-username
```

The command prompts for the password and confirmation. Do not commit the
generated `src/teachers.json` file. `src/teachers.example.json` shows its
expected structure.

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
