# vicebrowser
<img src="assets/banner.png" width=300>
Vicebrowser is a browser created with PyQt. This project is created in vibe-coding hackathon of Turkish-German University's Informatix student club.
<br>

## Features
- star favorite pages
- history of visited pages
<img src="assets/banner2.png" width=900>

# Building vicebrowser Executable

## Prerequisites
- Python 3.8+
- PyInstaller: `pip install pyinstaller`

## Build Instructions

### Option 1: Using the build script (recommended)
```bash
python build.py
```

### Option 2: Direct PyInstaller command
```bash
pyinstaller vicebrowser.spec
```

## Output
The executable will be created in the `dist/vicebrowser/` directory as a folder distribution.

### Running the Application

**Linux / macOS:**
```bash
cd dist/vicebrowser
./vicebrowser
```

**Windows:**
```
cd dist\vicebrowser
vicebrowser.exe
```

## Distribution
To distribute the application, **copy the entire `dist/vicebrowser/` folder** to the target computer. All files in this folder are required for the application to run.

## Notes
- The `assets/` folder is automatically included in the build
- Database files are stored in:
  - **Windows**: `%APPDATA%\vicebrowser\browser_history.db`
  - **macOS/Linux**: `~/.vicebrowser/browser_history.db`
- Custom background images are saved with absolute paths
- All settings are persistent across application restarts
- The application does NOT require Python to be installed on the target computer
