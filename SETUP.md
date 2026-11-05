# EduPulse: setup on a new laptop

This guide takes a laptop that has **none** of the required software and gets EduPulse running on it. It is
written for **Windows 10/11**. Notes for macOS and Linux are at the end.

Allow about **30–45 minutes** the first time; most of it is downloads. After that, starting the app takes
about one minute (see [Part C](#part-c-running-the-app-every-time)).

What you will install:

| Software | Why | Version |
|---|---|---|
| Git | download the project from GitHub | latest |
| Python | runs the backend (FastAPI + machine-learning model) | **3.12 or 3.13** |
| Node.js | runs the frontend (React website) | **LTS, 20 or newer** |
| PostgreSQL | the database | 16 or 17 |

> **No time for PostgreSQL?** You can skip Step 5 and use SQLite instead. SQLite is a single file and needs no
> install. See [Option B](#option-b-sqlite-no-database-install). PostgreSQL is the intended database, so use it if
> you can.

All commands below are typed into **PowerShell**. To open it: press the **Start** key, type `PowerShell`, and press
**Enter**. Paste each command with **right-click** (or Ctrl+V), then press **Enter**.

---

## Part A: install the software (one time only)

### Step 1. Allow PowerShell to run scripts

A fresh Windows install blocks the small helper scripts that `npm` and Python's virtual environment use. Run this
once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Type `Y` and press Enter if it asks. This affects only your user account.

### Step 2. Install Git

1. Go to <https://git-scm.com/download/win> and download the **64-bit Git for Windows Setup**.
2. Run the installer and click **Next** on every screen. The defaults are fine.
3. **Close PowerShell and open a new one**, so it picks up the new program.
4. Check:
   ```powershell
   git --version
   ```
   You should see something like `git version 2.47.0.windows.1`.

### Step 3. Install Python

1. Go to <https://www.python.org/downloads/windows/> and download the **Windows installer (64-bit)** for
   **Python 3.12.x or 3.13.x**. Don't use 3.14 or newer: some packages may not support it yet.
2. Run the installer. **On the first screen, tick "Add python.exe to PATH"** at the bottom. This is the most
   common thing people miss.
3. Click **Install Now**. When it finishes, click **Disable path length limit** if that option appears.
4. Open a **new** PowerShell and check:
   ```powershell
   python --version
   ```
   You should see `Python 3.12.x` or `Python 3.13.x`.

   > If the Microsoft Store opens instead, or you see "Python was not found", go to
   > **Settings → Apps → Advanced app settings → App execution aliases** and turn **off** the two
   > `python.exe` / `python3.exe` entries. Then open a new PowerShell and try again.

### Step 4. Install Node.js

1. Go to <https://nodejs.org/> and download the **LTS** version (Windows Installer, `.msi`).
2. Run it and click **Next** on every screen. You can leave "Tools for Native Modules" unticked.
3. Open a **new** PowerShell and check:
   ```powershell
   node --version
   npm --version
   ```
   You should see `v20.x` or newer, and an npm version number.

### Step 5. Install PostgreSQL and create the database

1. Go to <https://www.postgresql.org/download/windows/>, click **Download the installer**, and download
   **PostgreSQL 17** (or 16) for Windows x86-64.
2. Run the installer:
   - Components: keep **PostgreSQL Server** and **Command Line Tools** ticked. pgAdmin is optional, and you can
     untick **Stack Builder**.
   - **Password**: choose a password for the `postgres` superuser and **write it down**. You need it in a minute.
   - Port: leave it at **5432**.
   - Everything else: keep the defaults. At the end, untick "Launch Stack Builder" and click **Finish**.

   PostgreSQL now runs in the background and starts automatically with Windows.
3. Open the database shell. Press **Start**, type **SQL Shell (psql)**, and open it.
4. It asks five questions. Press **Enter** for the first four to accept the defaults (`localhost`, `postgres`,
   `5432`, `postgres`), then type the **password from step 2** and press Enter. The password is not shown while you
   type; that is normal.
5. You now see `postgres=#`. Paste these three lines and press Enter:
   ```sql
   CREATE USER edupulse WITH PASSWORD 'edupulse' CREATEDB;
   CREATE DATABASE edupulse OWNER edupulse;
   CREATE DATABASE edupulse_test OWNER edupulse;
   ```
   You should see `CREATE ROLE`, then `CREATE DATABASE` twice.
6. Type `\q` and press Enter to leave the shell.

`edupulse` is the app's database. `edupulse_test` is only used by the automated tests.

---

## Part B: set up the project (one time only)

### Step 6. Download the project

Pick a folder for the project. This example uses the Desktop:

```powershell
cd $HOME\Desktop
git clone https://github.com/vvvvvivekkk/edupluse.git
cd edupluse
```

You now have a folder `Desktop\edupluse` with `backend`, `frontend` and `docs` inside.

> **Without Git:** on the GitHub page, click **Code → Download ZIP**, extract it to the Desktop, and rename the
> folder to `edupluse`.

### Step 7. Set up the backend

From the `edupluse` folder:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt now starts with `(.venv)`. This "virtual environment" keeps the project's Python packages inside the
project folder instead of installing them system-wide.

Install the packages. This takes 2–5 minutes:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

It should finish with `Successfully installed ...`.

### Step 8. Create the settings file

```powershell
Copy-Item .env.example .env
```

Generate a random secret key, which is used to sign login tokens:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the long string it prints. Then open the settings file:

```powershell
notepad .env
```

Replace `replace-with-a-long-random-string` with the string you copied. The rest can stay as it is, since it
matches the database you created in Step 5. Save (Ctrl+S) and close Notepad.

The file should look like this, with your own key:

```ini
DATABASE_URL=postgresql+psycopg2://edupulse:edupulse@localhost:5432/edupulse
TEST_DATABASE_URL=postgresql+psycopg2://edupulse:edupulse@localhost:5432/edupulse_test
SECRET_KEY=3f9a...your-own-64-characters...c21e
ACCESS_TOKEN_MINUTES=480
CORS_ORIGINS=http://localhost:5173
```

### Step 9. Load the demo data

```powershell
python -m scripts.seed --reset
```

This creates all the tables and fills them with demo students, faculty, an admin, and academic records. All the
data is synthetic. You don't need to train the machine-learning model: the trained model is already in
`backend/models/`.

> If you see `DLL load failed ... An Application Control policy has blocked this file`, see
> [Troubleshooting](#troubleshooting).

### Step 10. Set up the frontend

Open a **second** PowerShell window and run:

```powershell
cd $HOME\Desktop\edupluse\frontend
npm install
```

This downloads the website's packages into `frontend\node_modules` and takes 1–3 minutes. Warnings are normal;
only lines that say `ERR!` are a problem.

**Setup is done.** Continue with Part C to start the app.

---

## Part C: running the app (every time)

The app has two parts and each needs its own PowerShell window. Both must stay open while you use the app.
PostgreSQL is already running in the background.

**Window 1: backend (API)**

```powershell
cd $HOME\Desktop\edupluse\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Wait for `Uvicorn running on http://127.0.0.1:8000` and `Application startup complete.`

**Window 2: frontend (website)**

```powershell
cd $HOME\Desktop\edupluse\frontend
npm run dev
```

Wait for `Local: http://localhost:5173/`.

**Open the app:** go to **<http://localhost:5173>** in Chrome, Edge or Firefox.

### Demo accounts

| Role | Email (username) | Password |
|---|---|---|
| Student | `student1@edupulse.edu` … `student16@edupulse.edu`, or roll number `EP26001` … `EP26016` | `Student@123` |
| Faculty | `faculty1@edupulse.edu`, `faculty2@edupulse.edu` | `Faculty@123` |
| Admin | `admin@edupulse.edu` | `Admin@123` |

You can also click the **Student / Faculty / Admin** buttons under the login form to fill these in.

Other useful pages while the backend runs:

- API documentation (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

### Stopping the app

Click into each PowerShell window and press **Ctrl+C**, then close the windows. To start again later, repeat
Part C; you don't need to repeat Parts A and B.

### Resetting the demo data

To wipe everything and start with fresh demo data, run this in the backend window while the server is stopped:

```powershell
cd $HOME\Desktop\edupluse\backend
.venv\Scripts\Activate.ps1
python -m scripts.seed --reset
```

### Getting the latest version of the project

```powershell
cd $HOME\Desktop\edupluse
git pull
cd backend;  .venv\Scripts\Activate.ps1;  pip install -r requirements.txt
cd ..\frontend;  npm install
```

Then start the app as usual.

### Running the automated tests (optional)

```powershell
# backend: uses the edupulse_test database
cd $HOME\Desktop\edupluse\backend
.venv\Scripts\Activate.ps1
python -m pytest -q

# frontend: no server needed
cd $HOME\Desktop\edupluse\frontend
npm test
```

---

## Option B: SQLite (no database install)

Use this if you can't install PostgreSQL. Skip Step 5. In Step 8, set these two lines in `backend\.env`:

```ini
DATABASE_URL=sqlite:///./edupulse.db
TEST_DATABASE_URL=sqlite:///./test.db
```

Everything else is the same. The data is stored in the file `backend\edupulse.db`.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| `running scripts is disabled on this system` (when running `Activate.ps1` or `npm`) | Do [Step 1](#step-1-allow-powershell-to-run-scripts), then open a new PowerShell. |
| `'python' / 'git' / 'node' is not recognized` | The program isn't on PATH. Close **all** PowerShell windows and open a new one. For Python, re-run the installer, choose **Modify**, and make sure **Add Python to environment variables** is ticked. |
| `No module named uvicorn` / `No module named fastapi` | The virtual environment isn't active: the prompt doesn't start with `(.venv)`. Run `.venv\Scripts\Activate.ps1` inside `backend`. |
| `pip install` fails while building `psycopg2`, `numpy` or `pandas` | Your Python is too new. Uninstall it, install **Python 3.12 or 3.13**, delete the `backend\.venv` folder, and repeat Step 7. |
| `password authentication failed for user "edupulse"` | The database user wasn't created. Repeat Step 5, parts 3–6. |
| `connection refused` / `could not connect to server` on port 5432 | PostgreSQL isn't running. Press **Win+R**, type `services.msc`, find **postgresql-x64-17**, and click **Start**. |
| `database "edupulse" does not exist` | Repeat Step 5, parts 3–6. |
| `DLL load failed while importing ...: An Application Control policy has blocked this file` | Windows **Smart App Control** is blocking SQLAlchemy's optional speed-up files. SQLAlchemy works without them. In the backend window, with `(.venv)` active, run the command below this table, then try again. |
| `[Errno 10048] ... address already in use` / `Port 5173 is in use` | The app is already running in another window, so close that one. Or restart the laptop. |
| The login page shows **"Request failed (500)"** or **"Failed to fetch"** | The backend (Window 1) isn't running, or stopped with an error. Check that window. |
| The login says **"Incorrect email or password"** for the demo accounts | The demo data isn't loaded. Run Step 9. |
| `npm install` shows `ERR!` | Delete the `frontend\node_modules` folder and run `npm install` again. Check your internet connection. |

The Smart App Control fix (run from the `backend` folder with `(.venv)` active). It renames SQLAlchemy's compiled
`.pyd` files so SQLAlchemy uses its built-in pure-Python version instead:

```powershell
Get-ChildItem .venv\Lib\site-packages\sqlalchemy -Recurse -Filter *.pyd | Rename-Item -NewName { $_.Name + ".blocked" }
```

You only need this on laptops where the error appears. Run it again after deleting or re-creating `.venv`.

---

## macOS / Linux

The steps are the same, with these differences:

- **Install the software**:
  - macOS: install [Homebrew](https://brew.sh), then run
    `brew install git python@3.12 node postgresql@16 && brew services start postgresql@16`.
  - Ubuntu: `sudo apt install git python3 python3-venv nodejs npm postgresql`, or use <https://nodejs.org> for a
    newer Node.
- **Create the database (Step 5)**: open the shell with `psql postgres` on macOS, or `sudo -u postgres psql` on
  Linux, then paste the same three `CREATE` lines.
- **Activate the virtual environment**: `source .venv/bin/activate` instead of `.venv\Scripts\Activate.ps1`.
- **Copy the settings file**: `cp .env.example .env`. Edit it with any text editor, for example `nano .env`.
- Use `python3` where this guide says `python`, if `python` is not found.
- Skip Step 1 and the Smart App Control fix, which apply only to Windows.
