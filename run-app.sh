#!/usr/bin/bash

# Kill anything on port 5000
lsof -ti :5000 | xargs kill -9 2>/dev/null; sleep 1 

# Run the app
source ~/.zshrc && source .venv/bin/activate && python app.py
