# Setting Up a Python 3.12 Virtual Environment on Windows (CMD)

This guide explains how to create, activate, and manage an isolated Python virtual environment using the standard Windows Command Prompt (cmd).

## Step 1: Open Command Prompt
Press the `Win` key, type **cmd**, and press **Enter**.

## Step 2: Navigate to Your Project Directory
Use the `cd` command to move into the folder where you want to keep your project. Replace `C:\path\to\your\project` with your actual folder path:
```cmd
cd C:\(\path\to\your\project
%%\)MAGIT_PARSER_PROTECT%%```

## Step 3: Create the Virtual Environment
Run the built-in Python `venv` module. This command creates a new folder named `.venv` inside your project directory to hold the isolated environment:
```cmd
python -m venv .venv
```

## Step 4: Activate the Virtual Environment
Run the activation batch file. Once activated, you will see `(.venv)` appear at the very beginning of your command prompt line:
```cmd
.venv\Scripts\activate.bat
```

## Step 5: Verify and Upgrade Tools
Ensure your environment is using the correct Python version and upgrade `pip` inside your active virtual environment:
```cmd
python --version
python -m pip install --upgrade pip
```

---

## Useful Commands

* **Deactivate the environment:** When you are done working, return to your global Python environment by running:
  ```cmd
  deactivate
  ```
* **Install packages:** Install dependencies safely inside your active environment without affecting your global system:
  ```cmd
  pip install <package_name>
  ```
