# Renders the milestone demos at 1080p with motion blur and writes QA reports (Windows PowerShell).
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force out | Out-Null
apex render examples\motion_test.json       -o out\motion_test.mp4       --samples 3 --qa-json out\motion_test_qa.json
apex render examples\gravity_switch_1b.json -o out\gravity_switch_1b.mp4 --samples 3 --qa-json out\gravity_switch_1b_qa.json
