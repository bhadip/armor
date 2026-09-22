#!/bin/bash
cd /Users/tom/armor/agent
source venv/bin/activate
python src/main.py >> /tmp/armor.log 2>> /tmp/armor.err
