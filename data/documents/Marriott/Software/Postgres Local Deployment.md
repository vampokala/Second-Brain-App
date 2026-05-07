Below is a **concise, up‑to‑date guide** for installing PostgreSQL locally on **macOS** for **testing and debugging**, based directly on recent authoritative sources.

---

# ✅ **How to Install PostgreSQL on macOS (2026 Guide)**

There are multiple valid ways to install Postgres on macOS, but the **most common and developer‑friendly** method is **Homebrew**. Other options include **Postgres.app** and the official **EDB installer**.

Below are all three methods so you can pick the one that fits your workflow.

---

# 🥇 **Method 1 — Install PostgreSQL Using Homebrew (Recommended)**

Homebrew is the simplest and most flexible approach for development.

### **1. Install Homebrew (if not installed)**

/bin/bash -c "$(curl -fsSL [https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"](https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh\)%22)

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **2. Install PostgreSQL**

brew install postgresql

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **3. Start PostgreSQL as a background service**

brew services start postgresql

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **4. Verify installation**

psql --version

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **5. Connect to Postgres**

psql postgres

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **6. Create a dedicated user & database (optional but recommended)**

CREATE USER devuser WITH PASSWORD 'your_password';

CREATE DATABASE devdb OWNER devuser;

GRANT ALL PRIVILEGES ON DATABASE devdb TO devuser;

``

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

### **7. Start/Stop/Restart**

brew services stop postgresql

brew services restart postgresql

[[dev.to]](https://dev.to/techprane/setting-up-postgresql-for-macos-users-step-by-step-instructions-2e30)

---

# 🥈 **Method 2 — Install via Postgres.app (GUI, zero‑config)**

If you want a _no‑terminal, simple toggle‑on server_, Postgres.app is excellent.

- Postgres.app is a native macOS application that runs Postgres in your menu bar. [[postgresql.org]](https://www.postgresql.org/download/macosx/)

**Steps:**

1. Download Postgres.app
2. Drag it into Applications
3. Open the app → PostgreSQL server starts instantly
4. Use `psql` from the app or configure your PATH.

Great for quick testing, students, and GUI‑first setups.

---

# 🥉 **Method 3 — Use the Official EDB Installer (Full bundle w/ pgAdmin)**

For a more "enterprise‑style" installation with GUI tools included:

- The EDB installer provides PostgreSQL, pgAdmin, and StackBuilder. [[postgresql.org]](https://www.postgresql.org/download/macosx/)

This is ideal if you prefer **GUI management tools** or want **multiple Postgres versions**.

---

# 🧪 **Using PostgreSQL for Local Testing & Debugging**

Once installed:

### **Check running services**

brew services list

[[itsfoss.gitlab.io]](https://itsfoss.gitlab.io/post/install-postgresql-mac/)

### **Start a psql session**

psql -h localhost -U postgres

[[portal.perforce.com]](https://portal.perforce.com/s/article/Setting-up-a-Test-Postgres-Instance-on-Your-Mac)

### **Create test tables**

CREATE TABLE test_logs (

    id SERIAL PRIMARY KEY,

    note TEXT,

    created_at TIMESTAMP DEFAULT NOW()

);

### **Insert sample data**

INSERT INTO test_logs (note) VALUES ('Hello from macOS!');

``

### **View logs (homebrew installs)**

Logs are stored in:

```
/opt/homebrew/var/log/postgresql@<version>.log
```

[[portal.perforce.com]](https://portal.perforce.com/s/article/Setting-up-a-Test-Postgres-Instance-on-Your-Mac)

Great for debugging connection issues or startup failures.

---

# 🔧 **Running Multiple Postgres Versions (Optional)**

You can install alternative versions:

brew install postgresql@14

brew install postgresql@17

[[portal.perforce.com]](https://portal.perforce.com/s/article/Setting-up-a-Test-Postgres-Instance-on-Your-Mac)

If a version is “keg‑only,” update PATH:

echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc

[[portal.perforce.com]](https://portal.perforce.com/s/article/Setting-up-a-Test-Postgres-Instance-on-Your-Mac)

---

# 📝 **Which Should You Pick?**

|Method|Best For|
|---|---|
|**Homebrew**|Developers wanting flexibility, CLI tools, easy service mgmt|
|**Postgres.app**|Beginners, GUI‑first users, single‑click startup|
|**EDB Installer**|Enterprise setups, includes pgAdmin & extra tooling|

Configuration Details

**➜**  **mmf-src** **git:(****dev****)** **✗** psql -d postgres -c "SHOW data_directory;"                                                                

         data_directory          

---------------------------------

 /opt/homebrew/var/postgresql@14

(1 row)

  

**➜**  **mmf-src** **git:(****dev****)** **✗** psql -d postgres -c "SHOW config_file;"   

                   config_file                   

-------------------------------------------------

 /opt/homebrew/var/postgresql@14/postgresql.conf

(1 row)

  

**➜**  **mmf-src** **git:(****dev****)** **✗** nano /opt/homebrew/var/postgresql@14/postgresql.conf

**➜**  **mmf-src** **git:(****dev****)** **✗** brew services restart postgresql



---

