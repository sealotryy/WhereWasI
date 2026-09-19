"""Quick check that the macOS probes work on this machine.

Run this first if the tracker reports no window titles or never goes idle.
Reading window titles needs Accessibility permission for whatever runs Python
(Terminal, iTerm, VS Code) under System Settings > Privacy & Security.
"""

import macos

app, window_title = macos.get_frontmost()
idle_seconds = macos.get_idle_seconds()

print(f"frontmost app:  {app or '(unreadable)'}")
print(f"window title:   {window_title or '(none)'}")
print(f"idle seconds:   {idle_seconds:.1f}")

if not app:
    print("\nCannot read the frontmost app. Grant Accessibility permission.")
elif not window_title:
    print("\nApp name works but no window title came back.")
    print("Either this app has no open window, or Accessibility permission is missing.")
else:
    print("\nBoth probes look good.")
