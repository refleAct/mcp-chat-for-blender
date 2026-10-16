# 🧊 MCP Chat for Blender  `v0.8.5`

**English** | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md)

A Blender add-on that lets you **chat with AI inside the 3D Viewport and have it build 3D models for you.**
Use Claude Code, Codex, the agy CLI, OpenRouter and more directly from the N-panel chat, and run the Python (bpy) code the AI writes safely through a task queue with automatic saving.

> ## ⚠️ Notice (unfinished parts)
> **I tried to use Claude from Termux with Blender for Android (unofficial build), but that integration is unfinished.**
> Blender for Android (APK) cannot run the `claude` installed in Termux because of the app sandbox, so the add-on ships a relay server (`termux_agent.py`) that runs in Termux and forwards requests. The code and install script are included, but **I have not been able to confirm that it works end to end on a real Android device.**
> The only setup verified to work is **Blender on a Windows PC + Claude Code installed on the same PC**. Codex CLI, agy CLI and macOS/Linux were written but not verified.

> ## 🚨 API KEY SECURITY WARNING
> - **Use a dedicated key with a spending limit** (a separate key/project with a budget cap). Never use your main or production key. Auto mode can send many requests, and **this add-on does not cap your spending.**
> - Keys are saved **encrypted inside the add-on folder (`.vault/`)** and are **deleted together with the add-on** — but the encryption is **best-effort**: it stops casual leaks (screenshots, copied files), **not** malware or anyone who can log in as you. On Android without `openssl` it is only weak obfuscation.
> - **Never share** the `.vault/` folder, screenshots of the preferences screen, or old backups (older versions stored keys in plain text). If a key might have leaked, **revoke it at the provider immediately.**
> - **Updating by replacing the add-on folder wipes your keys**; keys cannot be recovered if the vault is lost. Details: [section 8](#8-api-key-storage-notes-important).
> - You do **not** need an API key to use the add-on with Claude Code / Codex / agy CLI or the web UI — those use their own login.

---

## 1. What it is for

- Ask the AI in plain sentences, e.g. "make a hat like this photo", and it does the 3D modeling and materials inside Blender.
- AI-generated code is not run blindly: it goes into a **task queue**, runs in order, and after every successful task the add-on saves a `.blend`, a `.glb` and a viewport image.
- You can **review a plan first** and then run it or keep refining it.

## 2. Feature summary

| Area | What you get |
|---|---|
| **AI engines** | Claude Code (default), Codex CLI, agy CLI, Direct API (OpenRouter · NVIDIA NIM · local Ollama · custom) |
| **Model / reasoning** | Per-engine model (dropdown + custom ID) and reasoning level in the N-panel |
| **Modes** | Chat (talk and run) / Plan (make a plan, then review) / Auto (plan + run automatically) |
| **Plan review** | After a plan appears: **Run · Refine plan · Cancel** |
| **Task queue** | Add, edit, delete, reorder (▲▼), retry, duplicate; global delay (default 60 s); one instruction = one queue task |
| **Auto-save** | After each successful task: `.blend` (resources packed) + `.glb` + viewport PNG, with a configurable output folder |
| **Chat** | Up to 3 session tabs, multi-line scrollable history, compact / clear, copy message |
| **Image attachments** | Local images or viewport snapshots, up to 3 (small previews). The AI uses them as reference |
| **Prompt inspection** | **Preview** the final prompt before sending, and view the **prompt that was actually sent** (for Auto, including the AI's plan) |
| **Editable AI rules** | Edit / restore the built-in *Blender Execution Rules* in the add-on preferences |
| **Updater** | Check and install the latest GitHub Release from the add-on preferences |
| **User rules** | Rules such as "Bevel with 2 segments; black vertex color on bevel faces" are applied to every task |
| **Built-in safety rules** | No unrequested lights/cameras, existing objects are preserved, new work goes into a new collection, rendering is prepared but not run |
| **API key security** | Keys/tokens are stored encrypted inside the add-on folder (deleted together with the add-on) — see [section 8](#8-api-key-storage-notes-important) |
| **MCP server** | Runs an MCP/web server inside Blender so Claude Code and others can drive it with `execute_blender_code`, `get_scene_info`, `capture_viewport` |
| **Web chat UI** | Use the same sessions and queue from a browser (PC or mobile) |
| **Languages** | 한국어 · English · 中文 · 日本語 |
| **Blender support** | 3.x and newer (any MCP-capable AI client can connect regardless of version; not verified on every version) |

## 3. Installation

1. Download **`mcp-chat-for-blender-vX.Y.Z.zip`** from [Releases](https://github.com/refleAct/mcp-chat-for-blender/releases).
   - ⚠️ **Do not use GitHub's "Source code (zip)" / "Download ZIP".** Its folder name contains version dots (`.`), so Blender fails after installing with `No module named 'mcp-chat-for-blender-0'`. Always use the zip attached to the Release.
   - Build it yourself: `python package_addon.py --ci` → `dist/mcp-chat-for-blender-vX.Y.Z.zip`
2. In Blender: **Edit › Preferences › Add-ons › Install from Disk…** → choose the zip → enable the checkbox.
3. In the 3D Viewport press **N → `MCP Chat` tab**.
4. (Optional) For Claude Code: click **Auto-register Claude Code MCP** in the add-on preferences and install the `claude` CLI on your PC.

> 🔑 **To update**, use **Check for updates → Install update** in the add-on preferences. It keeps your saved keys. If you instead reinstall the zip with "overwrite", the add-on folder is replaced and **your saved API keys are deleted** (see [section 8](#8-api-key-storage-notes-important)).

### Supported Blender versions

| Version | Status |
|---|---|
| Blender 3.x | Supported (add-on minimum is 3.0); appears to work |
| Blender 4.x and newer | Supported (tested on 5.2.2: install, enable and UI drawing) |
| Blender for Android (unofficial) | Experimental — see the notice above |

- External AI clients connect to Blender through **MCP (Model Context Protocol)**, so any MCP-capable client can connect regardless of the Blender version.
- Not every version has been verified, and some UI behavior may differ. GLB export needs Blender's glTF add-on to be enabled.
- No external Python packages are required (standard library only).

## 4. How to use

### 4-1. Basic flow
1. In the N-panel **MCP Chat** tab choose the **Engine** (default: Claude Code) and the **model / reasoning level**.
2. Choose a mode. **The default is Auto** (plan + run automatically). Pick **Plan** if you want to review the plan before anything runs.
3. Type a prompt and press **Send**. (`+` attaches images, the clipboard button pastes text.)
4. Progress and results appear in the chat history (an `⏳ …` line while working, `✅` when done).

![Chat panel](docs/images/chat-panel.png)

### 4-2. Chat history
- Long messages wrap onto several lines; scroll with the mouse wheel or the scrollbar to see earlier messages.
- Buttons on a message's first line: ▼ expand, copy, and **view the prompt that was sent**.
- Small header buttons: reload / **compact** (turn old messages into one summary) / **clear** / delete session.
- The **Line width** setting controls where lines wrap (Korean/CJK characters count as 2 columns). Lower it if you see `...` in the middle of a line.

### 4-3. Plan → review → run
1. Send in **Plan** mode and the AI writes a step-by-step plan.
2. A **Review plan** box appears above the input:
   - **Run**: queue the approved plan as one task and run it
   - **Refine plan**: type changes or additions and the plan is rewritten
   - **✖**: discard the plan

### 4-4. Task queue
- Tasks are queued by **Auto** mode or the **Queue** button.
- Each item has a status icon (pending / running / done / failed), ▲▼ reorder, edit, retry, duplicate and delete.
- At the bottom set the **Output folder**, **Pack resources**, **Export GLB** and the **Auto-save** toggles.

![Task queue](docs/images/task-queue.png)

> Screenshots were taken from real Blender 5.2.2 with the English UI; they may differ slightly between versions.

### 4-5. User rules
Type rules into the field below the chat; they apply to **every task**. Separate several rules with `;`.
Example: `Bevel with 2 segments; black vertex color on bevel faces`

### 4-6. Server / web UI
- Start the server from the add-on preferences and open `http://127.0.0.1:8000` for the web chat UI.
- **No API key is required for the web UI:** if no key is set it automatically uses an installed CLI (Claude Code, then Codex, then agy). Set a key in ⚙ settings only if you want the Direct API.
- External AI such as Claude Code controls Blender through `http://127.0.0.1:8000/mcp`.

### 4-7. Connect your own AI CLI to Blender by MCP (manual setup)

The easiest way is the **Auto-register … MCP** buttons in the add-on preferences. If you prefer to do it yourself there are three ways. In every case **start the server in Blender first**, and use the add-on's bridge script `mcp_bridge.py` (inside the add-on folder) as the stdio command:

```
<Blender scripts>/addons/mcp-chat-for-blender/mcp_bridge.py
Windows example: C:/Users/<you>/AppData/Roaming/Blender Foundation/Blender/<version>/scripts/addons/mcp-chat-for-blender/mcp_bridge.py
```

**A. Run the CLI's own command**

| CLI | Command | Check |
|---|---|---|
| Claude Code | `claude mcp add -s user blender -- python "<path>/mcp_bridge.py"` | `claude mcp list` |
| Codex CLI | `codex mcp add blender -- python "<path>/mcp_bridge.py"` (recent versions) | `codex mcp list` |
| agy | (command unknown — use B) | — |

**B. Edit the config file yourself**

- Claude Code — `~/.claude.json`:
  ```json
  { "mcpServers": { "blender": { "command": "python", "args": ["<path>/mcp_bridge.py"] } } }
  ```
- Codex CLI — `~/.codex/config.toml`:
  ```toml
  [mcp_servers.blender]
  command = "python"
  args = ["<path>/mcp_bridge.py"]
  ```
- agy — `~/.gemini/config/mcp_config.json` (the file the add-on writes): the same `mcpServers` JSON shape as Claude Code.

**C. Ask the CLI with a prompt**

> Register an MCP server named `blender` that runs `python <path>/mcp_bridge.py` over stdio.

The CLI picks the right command for its own version. Ask it to show the command before running it, then verify with the list command from A.

**Test the connection**
- `python <path>/mcp_bridge.py --check` should print `OK - tools: execute_blender_code, get_scene_info, capture_viewport, …`.
- For a Blender on another machine (e.g. a PC reached from Termux) set `BLENDER_MCP_URL=http://<PC-IP>:8000/mcp` and `BLENDER_MCP_TOKEN=<token>` (or write them to `~/.config/blender_mcp_chat/bridge.json`).

> ⚠️ In this project's own testing only the Claude Code route on Windows has been used. The Codex and agy steps follow each CLI's usual pattern, but command names and file locations can differ between versions — check `--help` or the CLI's documentation.

## 5. Android + Termux (experimental · unfinished)

> This feature is **unfinished**. What follows is the intended design and it has not been verified on a real device.

1. Start the server in Blender (Android).
2. In Termux run: `curl -fsS http://127.0.0.1:8000/termux/setup.sh | bash`
   - Downloads the MCP bridge, registers MCP for `claude`/`agy`/`codex`, and starts the **Termux Agent** (`127.0.0.1:8787`).
3. In the Blender preferences enter the printed URL/token under **Termux Agent** → **Test Agent connection**.
4. If the Agent stopped, run `bash ~/.config/blender_mcp_chat/start_agent.sh` in Termux.

To control a PC's Blender from Termux on a phone, turn on **LAN access** (token-protected), allow TCP 8000 in the PC firewall, and use **Copy Termux install command** in the preferences.

## 6. Language support

| Language | Add-on (Blender) UI | Web UI |
|---|---|---|
| 한국어 | ✅ | ✅ |
| English | ✅ | ❌ |
| 中文 (简体) | ✅ | ❌ |
| 日本語 | ✅ | ❌ |

- Choose Auto (follow Blender) / Korean / English / Chinese / Japanese in **Language** at the top of the add-on preferences.
- All translations live in one table in `i18n.py`; add or fix entries there. Text that is not in the table is shown as written.
- Tooltips, previously saved chat content, the AI's reply language and the web UI are not translated.
- This README is available in four languages: [English](README.md) · [한국어](README.ko.md) · [中文](README.zh.md) · [日本語](README.ja.md).

## 7. Structure

```
mcp-chat-for-blender/
├─ __init__.py          Add-on entry: panels, operators, preferences, chat/queue UI
├─ blender_bridge.py    Main-thread-safe execution, scene info, viewport capture, .blend/.glb saving
├─ task_queue.py        Queue worker (sequential run, progress, auto-save, indentation repair)
├─ session_manager.py   SQLite store (sessions, messages, queue, settings) + encrypted key access
├─ llm_client.py        Direct API client and plan-prompt builder
├─ cli_runner.py        Runs claude / codex / agy, builds prompts, calls the Termux Agent
├─ guidelines.py        Built-in AI rules + user rules (shared by every engine)
├─ secrets_store.py     Encrypted vault for API keys/tokens (DPAPI · openssl · obfuscation fallback)
├─ i18n.py              UI translation table (ko/en/zh/ja)
├─ updater.py           GitHub Releases update check/installer
├─ server.py            HTTP/MCP server, web UI and REST API, token auth
├─ mcp_handler.py       MCP JSON-RPC tool handling
├─ mcp_bridge.py        stdio ↔ HTTP MCP bridge (used by Claude Code etc.)
├─ termux_agent.py      CLI relay server that runs in Termux
├─ install_termux.sh    PRoot install script
├─ package_addon.py     Release zip packaging (--ci for GitHub Actions)
├─ static/              Web chat UI (index.html · app.js · style.css)
├─ docs/images/         README screenshots
└─ .github/workflows/   Release automation (a v* tag builds and publishes the zip)
```

Data location: `~/.config/blender_mcp_chat/` (chat DB, saved .blend/.glb/images). Encrypted keys live in `.vault/` inside the add-on folder.

## 8. API key storage notes (important)

**Where keys are kept**
- API keys (OpenRouter / NVIDIA NIM / custom) and the LAN / Agent tokens are saved **encrypted in `.vault/` inside the add-on folder**.
- They are **never written** to Blender's user preferences, to `.blend` files, or to the chat database. The settings fields are write-only (they show "saved (encrypted)" plus a delete button), and the web API only returns `********`.
- Removing the add-on folder removes the keys too. The **Delete all data** button in the preferences wipes the vault, the chat database and the saved outputs (the chat database and outputs live outside the add-on folder, in `~/.config/blender_mcp_chat/`, so they stay after uninstalling unless you use this button).

**Protection strength depends on the OS**

| Environment | Method | What it protects against |
|---|---|---|
| Windows | DPAPI, bound to your Windows account | A copied vault file cannot be decrypted on another PC or by another Windows user |
| macOS / Linux / Termux | `openssl enc -aes-256-cbc` with a random key file stored next to the vault (permissions 600) | Casual leaks (screenshots, copied files). **Not** malware running as the same user |
| Android APK without `openssl` | Weak obfuscation (the preferences show a warning) | Only hides keys from casual viewing — **do not rely on it** |

**Please be careful with**
1. **Updating by replacing the folder deletes your keys.** Use the built-in updater (Check for updates → Install update), which preserves `.vault/`. A manual reinstall with "overwrite" replaces the folder and you must enter the keys again.
2. **Keys cannot be recovered** if the vault is lost or becomes undecryptable (different Windows account, reinstalled OS). Keep the original key at the provider, and revoke / regenerate a key if you suspect a leak.
3. **Never commit or share `.vault/`** (it is in `.gitignore`), and avoid sharing screenshots of the preferences screen.
4. **Older versions stored keys in plain text** (the chat database and Blender preferences). The first launch of the new version moves them into the vault and removes them, but **old copies may remain** in backups (for example `userpref.blend@` files or copied databases). If you ever shared those, revoke the old keys.
5. **Do not paste keys into prompts.** Prompts, AI replies and attached images are stored locally **in plain text** in the chat database, and they are sent to the AI service you chose. Claude Code / Codex / agy use their own login; this add-on does not store those credentials.
6. Keys are sent to the provider over HTTPS (local Ollama/LM Studio uses plain `http://localhost`). The code the AI writes **runs inside Blender with your user permissions** and could read files — use only AI services you trust.

**Other security notes**
- LAN access is off by default; when on, a Bearer token is required. Even local requests have their Origin/Host checked.
- This add-on **executes Python code written by an AI inside Blender.** Back up important files and use it only on networks you trust.

## 9. Known limitations
- Android Termux integration is unfinished (see the notice above).
- Typing a **space while entering Korean** in Blender's text field has been reported not to work (likely a Blender/IME issue). Work around it with the web chat UI or the clipboard paste button.
- CLI engines (Claude/Codex/agy) start a fresh conversation for every request (no continuation of earlier turns).
- Progress is shown as text; there is no spinning animation.

## 10. Versioning

- Current version: **0.8.5**
- **New features**: bump by 0.1 (0.8 → 0.9 → 1.0 …)
- **Bug fixes**: bump by 0.0.1 (0.8.1 → 0.8.2 … up to 0.8.999)
- Blender's `bl_info` stores it as a tuple such as `(0, 8, 5)`. See [CHANGELOG.md](CHANGELOG.md).
- Pushing a `v*` tag builds the zip with GitHub Actions and publishes it as a Release automatically.
- **Releases accumulate, one per version** (older ones are kept). The add-on's **Check for updates** button looks up the *latest* Release and installs it when it is newer than the installed version.

## 11. Credits and references

This project **references, or calls as external programs,** the specifications, tools and services below. Names and trademarks belong to their owners; this project is not affiliated with them.

| Item | Use in this project | Source |
|---|---|---|
| **MCP (Model Context Protocol)** | The Blender control server (`mcp_handler.py`) and stdio bridge (`mcp_bridge.py`) were **implemented directly from the public specification (protocol version 2024-11-05)**. No external MCP SDK code is included | Anthropic · <https://modelcontextprotocol.io> |
| **Claude Code** | Run as an external CLI (`claude -p`, `--model`, `--effort`, `--permission-mode`) | Anthropic · <https://docs.claude.com/en/docs/claude-code> |
| **Codex CLI** | Run as an external CLI (`codex exec`, `-m`, `-i`, `-c model_reasoning_effort`); MCP registration in `~/.codex/config.toml` | OpenAI · <https://github.com/openai/codex> |
| **agy CLI** | Run as an external CLI (Antigravity) | Google Antigravity |
| **OpenRouter / NVIDIA NIM / Ollama · LM Studio** | Direct API mode (OpenAI-compatible Chat Completions format) | <https://openrouter.ai> · <https://build.nvidia.com> · <https://ollama.com> |
| **Blender Python API (`bpy`)** | Add-on UI, scene control, saving | Blender Foundation · <https://docs.blender.org/api/current/> (GPL) |
| **glTF 2.0 / glTF-Blender-IO** | Calls Blender's built-in glTF add-on for `.glb` export | Khronos Group · <https://github.com/KhronosGroup/glTF-Blender-IO> (Apache-2.0) |
| **ambientCG** | Referenced by the AI rules ("AmbientCG-style PBR material"); no texture files are bundled | <https://ambientcg.com> (CC0) |
| **Termux** | Target environment for the Android integration (experimental) | <https://termux.dev> |
| **Windows DPAPI / OpenSSL** | Encrypted API-key storage (DPAPI on Windows, otherwise `openssl enc -aes-256-cbc`) | Microsoft · <https://www.openssl.org> (Apache-2.0) |
| **GitHub Releases API** | Add-on update check | <https://docs.github.com/rest/releases> |
| **Python standard library** | `http.server`, `sqlite3`, `urllib`, `zipfile`, etc. (no external packages bundled) | Python Software Foundation |

- No external library/SDK source code is **included** in this repository (standard library only). External services and CLIs must be installed or signed up for by the user.
- Designed and implemented in collaboration with **Anthropic Claude Code**.
- Because the add-on uses `bpy`, it is distributed under a license **compatible with Blender's GPL** (MIT-based).
- If a source is missing or wrong, please open an issue.

## 12. Author
- Author: **refleaction**
- AI collaboration: designed and implemented together with Anthropic **Claude Code**
- Unofficial project, not affiliated with the Blender Foundation, Anthropic, OpenAI or Google.

## 13. License

**MIT-based + attribution must be preserved**

- ✅ You may **modify the source**
- ✅ You may **redistribute** it (including modified versions and commercial use)
- ⚠️ **Do not change or remove the copyright notice and attribution.** When you modify and redistribute, keep the original author (refleaction) and this license text intact.
- The software is provided **as is**; the author is not liable for any problems caused by its use (such as damaged project files, leaked keys or API charges).

See the [LICENSE](LICENSE) file for the full text.
