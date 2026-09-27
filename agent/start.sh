#!/bin/bash
# Add Homebrew paths for both Apple Silicon and Intel
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/tom/armor/agent
source venv/bin/activate
python src/main.py >> /tmp/armor.log 2>> /tmp/armor.err
