# Custom LED Display Generator
A Python-based tool for designing and generating custom LED displays from a single design.  The goal of this project is to make it easier for electronics hobbyists and makers to create their own custom LED displays without having to manually design the mechanical, graphical, and electronic parts separately.  You define your display and select the required MCU and LED-driving configuration, and the tool generates the files needed to build it.


#Installation and Usage

Steps
1. Install Python 3.12

Download from:

Python 3.12 Downloads

During install:

check "Add Python to PATH"



# Create a virtual environment named .venv
python -m venv .venv

Activate the venv (PowerShell)
.\.venv\Scripts\Activate

# or in Command Prompt (cmd)
.\.venv\Scripts\activate.bat

# Confirm Python and pip point to venv
python -V
python -m pip --version


# Upgrade pip inside venv (recommended)
python -m pip install --upgrade pip setuptools wheel

#Restore dependencies:

python -m pip install -r requirements.txt


#start app
python main.py
