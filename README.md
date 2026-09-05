# Custom LED Display Generator
A Python-based tool for designing and generating custom LED displays from a single design.  The goal of this project is to make it easier for electronics hobbyists and makers to create their own custom LED displays without having to manually design the mechanical, graphical, and electronic parts separately.  You define your display and select the required MCU and LED-driving configuration, and the tool generates the files needed to build it.


# Installation and Usage

Steps
1. Install Python 3.12

Download from:

Python 3.12 Downloads

https://www.python.org/downloads/release/python-3120/


During install:

check "Add Python to PATH"



Setup and Run
2. Create a virtual environment

Create a virtual environment named .venv:

'python -m venv .venv'

3. Activate the virtual environment
PowerShell
'.\.venv\Scripts\Activate'

Command Prompt (cmd)
'.\.venv\Scripts\activate.bat'

4. Confirm Python and pip point to the virtual environment
'''python -V
python -m pip --version'''

5. Upgrade pip

Upgrade pip, setuptools, and wheel inside the virtual environment:

'python -m pip install --upgrade pip setuptools wheel'

6. Install dependencies

Install the required Python packages:

'python -m pip install -r requirements.txt'

7. Start the app
'python main.py'


![Preview](preview.png?raw=true "preview")
![Preview](preview2.png?raw=true "preview")