import os
import sys

# Add loanshield directory to path for modules lookup
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(current_dir, "..", "loanshield"))
sys.path.insert(0, project_dir)

from app.custom_web_server import app
