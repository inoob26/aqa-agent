import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Registers the Playwright MCP server that the playwright-tests skill uses for live page
// snapshots. Pi's built-in MCP and pi-mcp-extension both connect registered servers. A pi
// version without `registerMcpServer` skips it; the skill then uses the component source
// and `npx playwright codegen`. A `playwright` entry in mcp.json takes precedence over this one.
export default function (pi: ExtensionAPI) {
  if (typeof pi.registerMcpServer !== "function") return;
  try {
    pi.registerMcpServer("playwright", {
      command: "npx",
      args: ["-y", "@playwright/mcp@latest"],
      exposure: "direct",
      description: "Browser control for live page snapshots: browser_navigate, browser_snapshot",
    });
  } catch {
    // Another extension already registered a "playwright" server: keep that one.
  }
}
