"""Built-in exclusion patterns."""
from __future__ import annotations

BUILTIN_EXCLUSIONS: list[str] = [
    # Version control
    "**/.git/**",
    "**/.svn/**",
    "**/.hg/**",
    # Python
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/.venv/**",
    "**/venv/**",
    "**/.env/**",
    # Node.js
    "**/node_modules/**",
    # Build artifacts
    "**/dist/**",
    "**/build/**",
    "**/.next/**",
    "**/.nuxt/**",
    # Caches
    "**/.cache/**",
    "**/.npm/**",
    "**/.yarn/**",
    "**/.cargo/registry/**",
    "**/.cargo/git/**",
    # OS
    "**/.DS_Store",
    "**/Thumbs.db",
    "**/desktop.ini",
    # Temp files
    "**/*.tmp",
    "**/*.temp",
    "**/*.swp",
    "**/*.swo",
    "**/*~",
    # Browser caches
    "**/CacheStorage/**",
    "**/GPUCache/**",
    "**/ShaderCache/**",
    "**/Code Cache/**",
    # Steam Proton runtimes (but NOT user data paths)
    "**/steamapps/common/**",
    "**/steamapps/shadercache/**",
    "**/steamapps/temp/**",
    # Linux runtime dirs
    "**/proc/**",
    "**/sys/**",
    "**/dev/**",
    "**/run/**",
]

STEAM_USER_DATA_ALLOWLIST: list[str] = [
    # Allow these Steam paths even though steamapps is excluded
    "**/compatdata/*/pfx/drive_c/users/steamuser/My Documents/**",
    "**/compatdata/*/screenshots/**",
]
