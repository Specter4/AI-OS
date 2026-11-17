# AI-OS File Operations

The built-in filesystem adapter supports text and binary file access, directory listing and creation, filename-pattern search, metadata, copy, move, rename, and deletion.

## Local access roots

- Relative paths are resolved from the AI-OS workspace (`AI_OS_WORKSPACE`, or the current working directory when unset).
- Absolute paths are accepted when they resolve inside a configured access root.
- By default, the signed-in user's home directory and the AI-OS workspace are available.
- Set `AI_OS_ALLOWED_ROOTS` to a platform-separated list of additional or replacement roots. On Windows, separate roots with `;`; on Linux/macOS, use `:`.

Example PowerShell configuration:

```powershell
$env:AI_OS_WORKSPACE = "D:\AI-OS\workspace"
$env:AI_OS_ALLOWED_ROOTS = "D:\AI-OS\workspace;C:\Users\YourUser\Documents;D:\Projects"
```

Use actual local paths for the machine running AI-OS. Configured roots are resolved before operations, so traversal and symlink targets outside those roots are rejected.

## Tool permissions and data safety

- Listing, searching, metadata, and reads use `read`.
- Creating, editing, copying, moving, and renaming use `write`.
- Permanent file and directory deletion use `destructive`.
- Recursive directory deletion must be explicitly requested.
- Writes and transfers refuse to overwrite existing destinations by default. An explicit `overwrite=true` is required to replace an existing file.
- Text reads default to a 10 MB limit. Binary files are transported through base64, avoiding assumptions that every file is UTF-8 text.

The filesystem adapter does not grant access to another computer or cloud sandbox by itself. Cross-environment transfers will be implemented through a separate authenticated transfer capability, rather than exposing a shared filesystem implicitly.
