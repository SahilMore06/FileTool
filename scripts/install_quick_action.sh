#!/usr/bin/env bash
# ==============================================================================
# FileTool - Finder Quick Action Installer for macOS
# Installs "Convert with FileTool" in Finder right-click context menu (Services).
# ==============================================================================

set -euo pipefail

SERVICES_DIR="${HOME}/Library/Services"
mkdir -p "${SERVICES_DIR}"

WORKFLOW_NAME="Convert with FileTool"
WORKFLOW_DIR="${SERVICES_DIR}/${WORKFLOW_NAME}.workflow"
CONTENTS_DIR="${WORKFLOW_DIR}/Contents"

echo "Installing Finder Quick Action: '${WORKFLOW_NAME}'..."

# Determine python and filetool paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_EXEC="${ROOT_DIR}/.venv/bin/python"
else
    PYTHON_EXEC="$(command -v python3)"
fi

mkdir -p "${CONTENTS_DIR}/QuickLook"

cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>${WORKFLOW_NAME}</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendFileTypes</key>
            <array>
                <string>public.item</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
EOF

cat > "${CONTENTS_DIR}/document.wflow" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AMApplicationBuild</key>
    <string>523</string>
    <key>AMApplicationVersion</key>
    <string>2.10</string>
    <key>AMDocumentVersion</key>
    <string>2</string>
    <key>actions</key>
    <array>
        <dict>
            <key>action</key>
            <dict>
                <key>AMAccepts</key>
                <dict>
                    <key>Container</key>
                    <string>List</string>
                    <key>Optional</key>
                    <true/>
                    <key>Types</key>
                    <array>
                        <string>com.apple.cocoa.path</string>
                    </array>
                </dict>
                <key>AMActionVersion</key>
                <string>2.0.3</string>
                <key>AMParameterProperties</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <dict/>
                </dict>
                <key>ActionBundlePath</key>
                <string>/System/Library/Automator/Run Shell Script.action</string>
                <key>ActionName</key>
                <string>Run Shell Script</string>
                <key>ActionParameters</key>
                <dict>
                    <key>COMMAND_STRING</key>
                    <string>export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
"${PYTHON_EXEC}" -m filetool.app "\$@" &amp;
</string>
                    <key>CheckedForUserDefaultShell</key>
                    <true/>
                    <key>inputMethod</key>
                    <integer>1</integer>
                    <key>shell</key>
                    <string>/bin/bash</string>
                    <key>source</key>
                    <string></string>
                </dict>
                <key>BundleIdentifier</key>
                <string>com.apple.RunShellScript</string>
                <key>CFBundleVersion</key>
                <string>2.0.3</string>
            </dict>
        </dict>
    </array>
    <key>workflowMetaData</key>
    <dict>
        <key>workflowTypeIdentifier</key>
        <string>com.apple.Automator.servicesMenu</string>
    </dict>
</dict>
</plist>
EOF

echo "✔ Finder Quick Action successfully installed in:"
echo "  ${WORKFLOW_DIR}"
echo ""
echo "Right-click any file or folder in Finder -> Quick Actions -> '${WORKFLOW_NAME}'"
