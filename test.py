import subprocess

result = subprocess.run(
    [
        "osascript",
        "-e",
        'tell application "System Events" to get name of first application process whose frontmost is true'
    ],
    capture_output=True,
    text=True
)

print(result.stdout.strip())