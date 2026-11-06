# Our full stack (EESTEC PLC Hackathon 2026)

Everything we use, with versions as of 6 Nov 2026. Setup steps: **SETUP.md**. Project notes: **AGENTS.md**.

## 1. AI / agent layer
| Component | Version | Role | Where configured |
|---|---|---|---|
| **Claude Code** (CLI) | 2.1.319 | Orchestrator session plus background worker agents | — |
| **Model** | Claude Opus 5.5 (`claude-opus-5-5`), **effort high** | All workers are Opus/high. Planning agents used the `Plan` type; workers use `general-purpose`. | spawn parameters |
| **Orchestration pattern** | — | The main session is the orchestrator; the user talks only to it. Workers run in the background and write `work/PROGRESS.md`. A 15-minute cron loop monitors them and runs `sync.ps1`. | AGENTS.md |
| **Memory** | — | Claude auto-memory (user-local) plus AGENTS.md (shared) | `~/.claude/projects/.../memory`, AGENTS.md |

## 2. Skills (in repo: `.claude/skills/`)
| Skill | Contents |
|---|---|
| **machine-expert** | `SKILL.md` + `scripts/`. **`me_run.py`**: apply `src/*.st` as POU/DUT/GVL (`--folder Team`), build with exact errors, simulator tests from `tests.json`, **`--year 0,1`** full-year runs (SimCtrl reset/run/poll, SimScore vs Team_Results), `--save-archive`. **`me_dump.py`**: extract a `.projectarchive` and dump all objects to `.st`. **`me.ps1`**: wrapper with a lock check. |
| **tia-portal** | `scripts/TiaRun.cs` + `build.ps1`: TIA V21 Openness CLI. Attach to a running TIA or start headless; create or open a project; add a CPU from the catalogue; import `*.scl/*.db/*.udt` as external sources → generate blocks → compile → `TIA_RESULT errors/warnings`; save. |
| *(plugin)* **totally-integrated-claude** 4.6.0 | 18 skills: tia-openness-roadmap, tia-plc-operations, tia-project-general, tia-devices-general, tia-hmi-operations, tia-import-export, tia-networks, tia-testsuite, tia-python, tia-csharp-common, tia-doctor, plc-code-analysis, tia-simatic-drives, tia-sivarc, tia-multiuser, tia-teamcenter, tia-mac-module-builder, addin-operations. Enabled through `.claude/settings.json` (marketplace `Czarnak/totally-integrated-claude`). |

## 3. MCP servers (in repo: `.mcp.json`, plus the plugin)
| MCP | Version | Command | What it does |
|---|---|---|---|
| **tia-portal** (TiaMcpServer, MIT, by Czarnak) | 4.3.0 | `tia-mcp --access-mode read-write` (dotnet global tool) | TIA V21 via Openness: plc_read/plc_write, compile_check, bind/open/create/save/archive project, browse tree, HMI/network/VCI read/write, cross-references. `tia-mcp doctor` checks prerequisites. |
| **windows-mcp** (CursorTouch) | 0.8.8 | `uvx windows-mcp serve` (**`serve` is required**) | Desktop control: Screenshot/Snapshot (UI tree), Click, Type, Shortcut, Scroll, App launch/switch, Wait, Clipboard, Process, Registry. It pauses (`USER_CONTROL`) while a human uses the mouse or keyboard, and cannot drive elevated (admin) windows. |
| **siemens-docs** (from the plugin) | 0.1.2 | `uvx siemens-docs-mcp` | Search and read Siemens documentation (search_docs, read_page, get_toc, list_publications). |

## 4. PLC / automation software (installed locally; not in the repo)
| Software | Version | Used for |
|---|---|---|
| Schneider **EcoStruxure Machine Expert – Logic Builder** | V2.3 (`C:\Program Files\Schneider Electric\EcoStruxure Machine Expert\V2.3`) | ME task: project, build, **built-in simulator**. `LogicBuilderShell.exe` = headless IronPython 2.7.12 ScriptEngine. API stubs in `LogicBuilder\ScriptLib\Stubs\scriptengine\*.pyi`. |
| Schneider **Vijeo Designer** | 6.3.2 | ME HMI (HMIG2U / HMIDT351 panel), integrated in Machine Expert |
| Schneider License Manager | 2.10 | ME licences |
| Siemens **TIA Portal** | V21 (STEP 7 Professional + Safety, WinCC Basic ES, WinCC Unified ES) | TIA crane task. Openness API at `Portal V21\PublicAPI\V21\net48` (Base + Step7 DLLs). User must be in the `Siemens TIA Openness` group. |
| Siemens **WinCC Runtime Advanced** | V17.0 UPD8 + RT Advanced Simulator | TIA HMI: PC station "WinCC RT Advanced", **device version 17.0.0.0** |
| Siemens **S7-PLCSIM** | V21 | Simulating the S7-1515 (crane task) |
| Siemens **S7-PLCSIM Advanced** | V8.0 | Scriptable PLC simulation (Runtime API) for automated crane tests |
| Siemens Automation License Manager | V6.2 SP5 | TIA licences / trial |

## 5. Dev tooling
| Tool | Version | Used for |
|---|---|---|
| Git for Windows | 2.54.0 | repo; `core.autocrlf=true` |
| **GitHub CLI** (`gh`) | 2.103.3 | login (`gh auth login --web`), git credentials (`gh auth setup-git`) |
| Python (CPython) | 3.14.5 | analysis scripts (`tools_extract_profiles.py`), planned Python twin and crane model. Run with `python -I`. |
| uv / uvx | 0.11.16 | runs windows-mcp and siemens-docs-mcp |
| .NET SDK | 10.0.403 | TiaMcpServer (dotnet tool) |
| .NET Framework 4.8 `csc.exe` | C# 5 | builds TiaRun.exe |
| Node.js / npm | 26.13.0 / 11.20.0 | installed but currently unused (reserve for codesys-mcp-toolkit) |
| pdftotext (MinGW) | — | reading the task PDFs |

## 6. Repo workflow
- `sync.ps1`: mirror skills ⇄ repo → `git pull --rebase --autostash` → `add -A` → commit (with Claude attribution) → push.
- On every change: pull → commit → push. On the orchestrator laptop only the orchestrator session runs git; workers never do.
- `.gitignore`: no live `*.project`/TIA project folders, simulation caches, locks or installers. Builds are shared as archives in `deliver/`.

## 7. Evaluated but not used
- **codesys-mcp-toolkit** (npm) and other CODESYS MCPs: built for CODESYS 3.5 and untested on Machine Expert. Our own LogicBuilderShell scripts replace them.
- **Official CODESYS MCP Server:** needs CODESYS ≥ 3.5.22 plus a paid licence. Not compatible with ME V2.3.
- **mcp-snap7:** start/stop only. PLCSIM Advanced API or TiaMcpServer are used instead.
- **TiaCommander:** proprietary beta.
