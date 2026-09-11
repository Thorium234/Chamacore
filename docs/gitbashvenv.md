# Setting Up a Python 3.12 Virtual Environment on Windows (Git Bash)

This guide explains how to create, activate, and manage an isolated Python virtual environment using Git Bash on Windows.

## Step 1: Open Git Bash
Press the `Win` key, type **Git Bash**, and press **Enter**.

## Step 2: Navigate to Your Project Directory
Use the `cd` command to move into the folder where you want to keep your project. Git Bash uses Linux-style paths (forward slashes `/` instead of backslashes `\`). 

Replace the path below with your actual folder path:
```bash
cd /c/path/to/your/project
```

## Step 3: Create the Virtual Environment
Run the built-in Python `venv` module. This command creates a new folder named `.venv` inside your project directory to hold the isolated environment:
```bash
python -m venv .venv
```

## Step 4: Activate the Virtual Environment
Run the activation script using the `source` command. Once activated, you will see `(.venv)` appear at the beginning of your Git Bash prompt line:
```bash
source .venv/Scripts/activate
```

## Step 5: Verify and Upgrade Tools
Ensure your environment is using the correct Python version and upgrade `pip` inside your active virtual environment:
```bash
python -m pip install --upgrade pip
```
*(Note: Sometimes Git Bash bypasses the local virtual environment when running just `python`. Using `python -m pip` ensures you are installing safely inside the environment.)*

---

## Useful Commands

* **Deactivate the environment:** When you are done working, return to your global Python environment by running:
  ```bash
  deactivate
  ```
* **Install packages:** Install dependencies safely inside your active environment without affecting your global system:
  ```bash
  pip install <package_name>
  ```
