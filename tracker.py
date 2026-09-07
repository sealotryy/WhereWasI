from AppKit import NSWorkspace ## this imports the MacOS application framework into Python

workspace = NSWorkspace.sharedWorkspace() ## get access to MacOS workspace information
app = workspace.frontmostApplication() ## tells us what app is working in the backgroun

print(app.localizedName())