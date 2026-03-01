"""
OpenAkita 工具模块
"""

import sys

from .file import FileTool
from .mcp import MCPClient, MCPConnectResult, mcp_client
from .mcp_catalog import MCPCatalog, mcp_catalog, scan_mcp_servers
from .shell import ShellTool
from .web import WebTool

__all__ = [
    "ShellTool",
    "FileTool",
    "WebTool",
    "MCPClient",
    "MCPConnectResult",
    "mcp_client",
    "MCPCatalog",
    "mcp_catalog",
    "scan_mcp_servers",
]

# Windows 桌面自动化模块（仅 Windows 平台可用）
if sys.platform == "win32":
    try:
        from .desktop import (  # noqa: F401
            DESKTOP_TOOLS,
            DesktopController,
            DesktopToolHandler,
            KeyboardController,
            MouseController,
            ScreenCapture,
            UIAClient,
            VisionAnalyzer,
            get_controller,
            register_desktop_tools,
        )

        __all__.extend(
            [
                "DesktopController",
                "get_controller",
                "ScreenCapture",
                "MouseController",
                "KeyboardController",
                "UIAClient",
                "VisionAnalyzer",
                "DESKTOP_TOOLS",
                "DesktopToolHandler",
                "register_desktop_tools",
            ]
        )
    except ImportError as e:
        # 依赖未安装时的警告
        import logging

        logging.getLogger(__name__).debug(
            f"Desktop automation module not available: {e}. "
            "Install with: pip install mss pyautogui pywinauto"
        )
