# AI-OS Application Control

Application control lets JARVIS discover local applications, launch them, inspect running processes and visible windows, and manage application windows.

## Discovery

The built-in tools are:

- \`applications.list_installed\`: on Windows, lists Start Menu shortcuts and application metadata from uninstall registry entries. It does not execute applications or expose uninstall commands.
- \`applications.list_running\`: lists running processes with process IDs and available metadata. Uses \`psutil\` when installed, otherwise platform process-list commands.
- \`applications.list_windows\`: lists visible top-level Windows windows with title, handle, and process ID. Window enumeration is Windows-only in this step.

Use the returned shortcut path or exact Start Menu display name when launching an installed app that is not found through PATH.

## Launching

\`applications.launch\` accepts an executable path or command name, an optional list of individual arguments, and an optional existing working directory.

- Launches executable files with an argument array and \`shell=False\`; it does not invoke a command interpreter.
- Windows direct executable launch accepts \`.exe\` and \`.com\`. Other application types should be launched through their Start Menu shortcut.
- A Start Menu shortcut can be launched by its exact display name or shortcut path. If a name matches multiple shortcuts, JARVIS returns the candidates instead of choosing arbitrarily.
- Arguments must be a list of strings. Command strings, NUL characters, excessive argument counts, and excessive argument sizes are rejected.
- Importing the module does not launch anything.

Launching an application is registered as a write action and passes through the existing authorization gateway.

## Window management

The following actions operate on a visible window handle returned by \`applications.list_windows\`:

- \`applications.focus_window\`
- \`applications.minimize_window\`
- \`applications.maximize_window\`
- \`applications.restore_window\`

Window handles are validated before use. Windows may refuse foreground activation due to OS foreground restrictions; JARVIS reports the operation result rather than claiming it succeeded.

## Closing and terminating applications

- \`applications.close_window\` posts the standard Windows \`WM_CLOSE\` message. This gives the application an opportunity to prompt for unsaved work. It is classified as destructive because closing a window may affect unsaved changes.
- \`applications.terminate\` requires both a process ID and the expected process name. The name is checked before termination to reduce the chance of acting on a reused or mistaken PID.
- Normal termination is requested first. Force termination is explicit and destructive; it may discard unsaved work.

These operations use the existing permission and approval system. They are not performed automatically during discovery.

## Current boundaries

- This step does not implement arbitrary shell commands, keyboard shortcut chords, application uninstall, or application installation.
- Installed application discovery is Windows-focused; process listing has portable fallbacks.
- Window management is Windows-only.
- Windows AppX/UWP package activation and deep application-specific UI automation are not guaranteed. Use the general desktop interaction and browser tools where appropriate.
- Real desktop interaction must be verified manually on the target PC. Unit tests use injected fake drivers and do not prove that a specific installed application launches or responds on the user's machine.
