# Teammate setup: Claude Code + PLC tooling
> The full list of tools, versions and MCPs is in **STACK.md**.

Clone the repo and run `claude` **inside the repo folder**. Claude Code then loads automatically:
- **CLAUDE.md → AGENTS.md**: all project notes. Read it first.
- **Skills** in `.claude/skills/`:
  - `machine-expert`: headless Machine Expert. Write ST, build, run the simulator and full-year tests.
  - `tia-portal`: the `TiaRun` Openness CLI.
- **MCP servers** in `.mcp.json`:
  - `tia-portal`: TiaMcpServer, read-write.
  - `windows-mcp`: screenshots, clicks and typing in GUIs.
  - Claude asks you to approve them on first start.
- **Plugin** `totally-integrated-claude` in `.claude/settings.json`: 18 TIA Openness skills and the `siemens-docs` MCP. Claude offers to install it on first start; accept.

## One-time installs (Windows)
```powershell
winget install --id Microsoft.DotNet.SDK.10 -e     # for TiaMcpServer
winget install --id astral-sh.uv -e                # for uvx (windows-mcp, siemens-docs)
winget install --id GitHub.cli -e                  # for git auth: gh auth login --web; gh auth setup-git
dotnet tool install -g TiaMcpServer                # provides tia-mcp (in %USERPROFILE%\.dotnet\tools)
```
Open a **new terminal** afterwards so PATH refreshes, then run `tia-mcp doctor`.

**TIA Openness** (TIA-side tools only): in an admin terminal run `net localgroup "Siemens TIA Openness" %USERNAME% /add`, then **sign out and back in**. The first time a tool attaches, TIA shows an access dialog; answer **Yes to all**.

**TiaRun.exe** is not committed (`*.exe` is ignored). Build it with `powershell -File .claude\skills\tia-portal\scripts\build.ps1`. This needs TIA V21 installed.

## Caveats
- **Paths:** the skills and scripts were written on the laptop where the repo is at `C:\Users\sajic\Documents\plc-hackathon`. If your clone lives elsewhere, tell Claude your path. The scripts take absolute paths as arguments.
- **Machine Expert** V2.3 must be installed at the default path for the `machine-expert` skill (`LogicBuilderShell.exe`).
- **windows-mcp** drives your real mouse and keyboard and pauses whenever you touch them. It cannot click into windows that run as admin.
- **Git rule:** on every change, pull → commit → push (`.\sync.ps1 "message"`). Don't edit agent-owned files: `work/src`, `work/PROGRESS.md`. See AGENTS.md "Team repo & git workflow".
