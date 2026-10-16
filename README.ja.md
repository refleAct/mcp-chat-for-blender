# 🧊 MCP Chat for Blender  `v0.8.3`

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | **日本語**

**3D ビューポートの中で AI と会話しながら 3D モデリングを任せられる Blender アドオン**です。
Claude Code、Codex、agy CLI、OpenRouter などの AI エンジンを N パネルのチャットから直接使い、AI が書いた Python（bpy）コードをタスクキュー経由で安全に実行し、自動保存します。

> ## ⚠️ お知らせ（未完成の部分）
> **Blender for Android（非公式ビルド）で Termux 連携により Claude を使おうとしましたが、この連携は未完成です。**
> Android 版 Blender（APK）はアプリのサンドボックスのため、Termux にインストールした `claude` を直接実行できません。そのためアドオンには Termux 内で動く中継サーバー（`termux_agent.py`）を同梱しています。コードとインストールスクリプトは含まれていますが、**実際の Android 端末で最後まで動作することは確認できていません。**
> 動作を確認できている環境は **Windows PC の Blender + 同じ PC にインストールした Claude Code** のみです。Codex CLI、agy CLI、macOS/Linux はコードを書いただけで未検証です。

> ## 🔑 重要：API キーの保存方法
> API キーとトークンは**アドオンフォルダ内（`.vault/`）に暗号化して保存**され、**アドオンを削除すると一緒に削除**されます。キーを入力する前に [第 8 章](#8-api-キー保存に関する注意重要)を必ずお読みください。特に、保護の強さは OS によって異なること、**アドオンフォルダを置き換える方法でアップデートするとキーが消える**こと、金庫を失うとキーを復元できないことにご注意ください。

---

## 1. 用途

- Blender の中で「この写真のような帽子を作って」のような文章で、3D モデリングやマテリアル作成を AI に任せます。
- AI が作ったコードをそのまま実行せず、**タスクキュー**に積んで順番に実行し、成功するたびに `.blend` / `.glb` / ビューポート画像を自動保存します。
- 作業前に**計画（Plan）を確認**し、よければ実行、そうでなければ修正を続けられます。

## 2. 機能の概要

| 区分 | 内容 |
|---|---|
| **AI エンジン** | Claude Code（既定）、Codex CLI、agy CLI、Direct API（OpenRouter · NVIDIA NIM · ローカル Ollama · カスタム） |
| **モデル / 推論設定** | N パネルでエンジンごとにモデル（ドロップダウン + 任意 ID）と推論レベルを選択 |
| **モード** | Chat（会話して即実行）/ Plan（計画を立てて確認）/ Auto（計画 + 自動実行） |
| **Plan の確認** | 計画が出たら **実行 · 計画を続ける · キャンセル** を選択 |
| **タスクキュー** | 追加・編集・削除・並べ替え（▲▼）・再試行・複製、グローバル遅延（既定 60 秒）、1 つの指示 = 1 つのキュータスク |
| **自動保存** | タスク成功のたびに `.blend`（リソースをパック）+ `.glb` + ビューポート PNG を保存。保存場所を指定可能 |
| **チャット** | セッションタブ最大 3 つ、複数行のスクロール履歴、圧縮・クリア、メッセージのコピー |
| **画像添付** | ローカル画像 / ビューポートのスナップショットを最大 3 枚（小さなプレビュー）。AI が参考にします |
| **プロンプト確認** | 送信前に最終プロンプトを**プレビュー**、送信後に**実際に送られたプロンプト**を表示（Auto は AI の計画を含む） |
| **AI ルールの編集** | アドオン設定で内蔵の *Blender Execution Rules* を編集・復元 |
| **アップデート** | アドオン設定から最新の GitHub Release を確認してインストール |
| **ユーザー指針** | 「ベベルは 2 段階; ベベル面に黒い頂点カラーを適用」のような指針をすべての作業に適用 |
| **内蔵の安全ルール** | 頼まれていないライト/カメラは追加しない、既存オブジェクトを保持、新しいコレクションに配置、レンダリングは準備まで |
| **API キーのセキュリティ** | キー/トークンをアドオンフォルダ内に暗号化して保存（アドオン削除時に一緒に削除）— [第 8 章](#8-api-キー保存に関する注意重要)参照 |
| **MCP サーバー** | Blender 内で MCP/Web サーバーを起動。Claude Code などが `execute_blender_code`、`get_scene_info`、`capture_viewport` で Blender を操作 |
| **Web チャット UI** | ブラウザ（PC・モバイル）から同じセッション/キューを利用 |
| **言語** | 한국어 · English · 中文 · 日本語 |
| **Blender 対応** | 3.x 以上（MCP 対応の AI クライアントならバージョンを問わず接続可能。全バージョンでの検証は未完） |

## 3. インストール

1. [Releases](https://github.com/refleAct/mcp-chat-for-blender/releases) から **`mcp-chat-for-blender-vX.Y.Z.zip`** をダウンロードします。
   - ⚠️ GitHub の **「Source code (zip)」/「Download ZIP」は使わないでください。** フォルダ名にバージョンのドット（`.`）が含まれるため、Blender がインストール後に `No module named 'mcp-chat-for-blender-0'` というエラーを出します。必ず Release に添付された zip を使ってください。
   - 自分でビルドする場合：`python package_addon.py --ci` → `dist/mcp-chat-for-blender-vX.Y.Z.zip`
2. Blender：**Edit › Preferences › Add-ons › Install from Disk…** → zip を選択 → チェックボックスで有効化
3. 3D ビューポートで **N キー → `MCP Chat` タブ**
4. （任意）Claude Code 連携：アドオン設定の **Claude Code MCP 自動登録** をクリックし、PC に `claude` CLI をインストール

> 🔑 **アップデート**にはアドオン設定の **アップデートを確認 → アップデートをインストール** を使ってください。保存済みのキーが維持されます。zip を「上書き」で再インストールするとアドオンフォルダが置き換わり、**保存済みの API キーが削除されます**（[第 8 章](#8-api-キー保存に関する注意重要)参照）。

### 対応 Blender バージョン

| バージョン | 状態 |
|---|---|
| Blender 3.x | 対応（アドオンの最低バージョンは 3.0）。動作すると思われます |
| Blender 4.x 以上 | 対応（5.2.2 でインストール・有効化・UI 表示を確認） |
| Android 版 Blender（非公式） | 実験的 — 上のお知らせを参照 |

- 外部の AI は **MCP（Model Context Protocol）** で Blender に接続するため、MCP 対応の AI クライアントであれば Blender のバージョンに関係なく接続できます。
- ただし**すべてのバージョンで検証したわけではありません。** バージョンによって一部の UI 動作が異なる場合があります。GLB エクスポートには Blender の glTF アドオンの有効化が必要です。
- Python の外部パッケージは不要です（標準ライブラリのみ）。

## 4. 使い方

### 4-1. 基本の流れ
1. N パネルの **MCP Chat** タブで **Engine**（既定は Claude Code）と**モデル / 推論レベル**を選びます。
2. モードを選びます。**既定は Auto**（計画 + 自動実行）です。実行前に計画を確認したい場合は **Plan** を選んでください。
3. プロンプトを入力して **Send（送信）** します。（`+` ボタンで画像を添付、クリップボードボタンで貼り付け）
4. 結果と進行状況はチャット履歴に表示されます（作業中は `⏳ …` の行、完了すると `✅`）。

![チャットパネル（英語 UI のスクリーンショット）](docs/images/chat-panel.png)

### 4-2. チャット履歴
- 長いメッセージは複数行で表示され、マウスホイールやスクロールバーで過去の会話を見られます。
- メッセージ 1 行目のボタン：▼ 展開、コピー、**送信されたプロンプトを見る**。
- ヘッダーの小さなボタン：再読み込み / **圧縮**（古い会話を 1 つの要約に）/ **クリア** / セッション削除。
- **行幅（Line width）** の設定で折り返し位置を調整します（日本語・中国語・韓国語の文字は 2 桁として計算）。行の途中に `...` が出る場合は値を小さくしてください。

### 4-3. Plan → 確認 → 実行
1. **Plan** モードで送信すると、AI が段階的な計画を作ります。
2. 入力欄の上に**計画の確認**ボックスが表示されます。
   - **実行**：承認した計画を 1 件のタスクとしてキューに登録して実行
   - **計画を続ける**：修正・追加の要望を入力して計画を書き直す
   - **✖**：計画を破棄

### 4-4. タスクキュー
- **Auto** モードまたは **Queue（キュー登録）** ボタンでタスクがキューに積まれます。
- 各項目に、状態アイコン（待機/実行中/完了/失敗）、▲▼ 並べ替え、編集、再試行、複製、削除があります。
- 下部で**保存場所**、**リソースのパック**、**GLB エクスポート**、**自動保存**のトグルを設定します。

![タスクキュー（英語 UI のスクリーンショット）](docs/images/task-queue.png)

> スクリーンショットは実際の Blender 5.2.2 の英語 UI で撮影したもので、バージョンによって多少異なる場合があります。

### 4-5. ユーザー指針
チャット下の入力欄に書いておくと**すべての作業**に適用されます。複数ある場合は `;` で区切ります。
例）`ベベルは2段階; ベベル面に黒い頂点カラーを適用`

### 4-6. サーバー / Web UI
- アドオン設定でサーバーを起動すると、`http://127.0.0.1:8000` で Web チャット UI を使えます。
- Claude Code などの外部 AI は `http://127.0.0.1:8000/mcp` 経由で Blender を操作します。

### 4-7. お使いの AI CLI を MCP で Blender に接続する（手動設定）

いちばん簡単なのは、アドオン設定の **MCP 自動登録** ボタンです。自分で行う場合は 3 つの方法があります。どの方法でも**先に Blender でサーバーを起動**し、アドオンフォルダ内のブリッジスクリプト `mcp_bridge.py` を stdio コマンドとして使います。

```
<Blender scripts>/addons/mcp-chat-for-blender/mcp_bridge.py
Windows の例: C:/Users/<ユーザー名>/AppData/Roaming/Blender Foundation/Blender/<バージョン>/scripts/addons/mcp-chat-for-blender/mcp_bridge.py
```

**A. CLI のコマンドで登録**

| CLI | コマンド | 確認 |
|---|---|---|
| Claude Code | `claude mcp add -s user blender -- python "<パス>/mcp_bridge.py"` | `claude mcp list` |
| Codex CLI | `codex mcp add blender -- python "<パス>/mcp_bridge.py"`（新しいバージョン） | `codex mcp list` |
| agy | （コマンド未確認 — B を使用） | — |

**B. 設定ファイルを直接編集**

- Claude Code — `~/.claude.json`：
  ```json
  { "mcpServers": { "blender": { "command": "python", "args": ["<パス>/mcp_bridge.py"] } } }
  ```
- Codex CLI — `~/.codex/config.toml`：
  ```toml
  [mcp_servers.blender]
  command = "python"
  args = ["<パス>/mcp_bridge.py"]
  ```
- agy — `~/.gemini/config/mcp_config.json`（アドオンが書き込むファイル）：Claude Code と同じ `mcpServers` の JSON 形式。

**C. プロンプトで CLI に頼む**

> stdio で `python <パス>/mcp_bridge.py` を実行する、`blender` という名前の MCP サーバーを登録してください。

CLI が自分のバージョンに合ったコマンドを選んで実行します。実行前にコマンドを見せてもらい、終わったら A の一覧コマンドで確認してください。

**接続テスト**
- `python <パス>/mcp_bridge.py --check` を実行すると `OK - tools: execute_blender_code, get_scene_info, capture_viewport, …` と表示されるはずです。
- 別のマシンの Blender（例：Termux から接続する PC）の場合は、環境変数 `BLENDER_MCP_URL=http://<PC-IP>:8000/mcp` と `BLENDER_MCP_TOKEN=<トークン>` を設定します（または `~/.config/blender_mcp_chat/bridge.json` に記述）。

> ⚠️ このプロジェクト自身のテストで使ったのは Windows 上の Claude Code の方法だけです。Codex と agy の手順は各 CLI の一般的なやり方に沿っていますが、バージョンによってコマンド名やファイルの場所が異なる場合があります。`--help` や各 CLI のドキュメントを確認してください。

## 5. Android + Termux 連携（実験的 · 未完成）

> この機能は**未完成**です。以下は設計した方式で、実機での検証はできていません。

1. Blender（Android）でサーバーを起動
2. Termux で実行：`curl -fsS http://127.0.0.1:8000/termux/setup.sh | bash`
   - MCP ブリッジをダウンロードし、`claude`/`agy`/`codex` に MCP を登録し、**Termux Agent**（`127.0.0.1:8787`）を起動
3. Blender 設定 › **Termux Agent** に出力された URL/トークンを入力 → **Agent 接続テスト**
4. Agent が止まっていたら、Termux で `bash ~/.config/blender_mcp_chat/start_agent.sh`

スマホの Termux から PC の Blender を操作するには、**LAN アクセス**をオンにし（トークン認証）、PC のファイアウォールで TCP 8000 を許可して、設定画面の **Termux インストールコマンドをコピー** を使います。

## 6. 言語サポート

| 言語 | アドオン（Blender）UI | Web UI |
|---|---|---|
| 한국어 | ✅ | ✅ |
| English | ✅ | ❌ |
| 中文（简体） | ✅ | ❌ |
| 日本語 | ✅ | ❌ |

- アドオン設定の一番上にある **Language** で、自動（Blender に従う）/ 韓国語 / 英語 / 中国語 / 日本語を選びます。
- 翻訳はすべて `i18n.py` の 1 つの表にまとめてあり、そこで修正・追加できます。表にない文言は原文のまま表示されます。
- ツールチップ、以前保存したチャット内容、AI の返答言語、Web UI は翻訳されません。
- この README は 4 言語で提供されています：[English](README.md) · [한국어](README.ko.md) · [中文](README.zh.md) · [日本語](README.ja.md)

## 7. 構成

```
mcp-chat-for-blender/
├─ __init__.py          アドオン本体：パネル・オペレーター・設定、チャット/キュー UI
├─ blender_bridge.py    メインスレッドで安全に実行、シーン情報、ビューポートキャプチャ、.blend/.glb 保存
├─ task_queue.py        キューワーカー（順次実行・進行表示・自動保存・インデント修復）
├─ session_manager.py   SQLite 保存（セッション・メッセージ・キュー・設定）+ 暗号化キー連携
├─ llm_client.py        Direct API クライアント、Plan プロンプト生成
├─ cli_runner.py        claude / codex / agy の実行、プロンプト組み立て、Termux Agent 呼び出し
├─ guidelines.py        AI の基本ルール + ユーザー指針（全エンジン共通）
├─ secrets_store.py     API キー/トークンの暗号化金庫（DPAPI · openssl · 難読化フォールバック）
├─ i18n.py              UI 翻訳表（ko/en/zh/ja）
├─ updater.py           GitHub Releases の更新確認/インストール
├─ server.py            HTTP/MCP サーバー、Web UI・REST API、トークン認証
├─ mcp_handler.py       MCP JSON-RPC ツール処理
├─ mcp_bridge.py        stdio ↔ HTTP MCP ブリッジ（Claude Code などで使用）
├─ termux_agent.py      Termux で動く CLI 中継サーバー
├─ install_termux.sh    PRoot 環境用インストールスクリプト
├─ package_addon.py     配布用 zip パッケージング（GitHub Actions 用 --ci）
├─ static/              Web チャット UI（index.html · app.js · style.css）
├─ docs/images/         README のスクリーンショット
└─ .github/workflows/   リリース自動化（v* タグをプッシュすると zip を作成して公開）
```

データの場所：`~/.config/blender_mcp_chat/`（チャット DB、保存された .blend/.glb/画像）。暗号化されたキーはアドオンフォルダ内の `.vault/` にあります。

## 8. API キー保存に関する注意（重要）

**キーが保存される場所**
- API キー（OpenRouter / NVIDIA NIM / カスタム）と LAN・Agent トークンは、**アドオンフォルダ内の `.vault/` に暗号化して**保存されます。
- Blender のユーザー設定、`.blend` ファイル、チャット DB には**保存されません。** 設定の入力欄は書き込み専用で（「保存済み（暗号化）」と削除ボタンを表示）、Web API は `********` だけを返します。
- アドオンフォルダを削除するとキーも一緒に消えます。設定の**すべてのデータを削除**ボタンは、金庫・チャット DB・保存済み出力をすべて削除します（チャット DB と出力はアドオンフォルダの外の `~/.config/blender_mcp_chat/` にあるため、このボタンを使わない限りアドオンを削除しても残ります）。

**保護の強さは OS によって異なります**

| 環境 | 方式 | 防げるもの |
|---|---|---|
| Windows | DPAPI（Windows アカウントに紐づく） | 金庫ファイルを別の PC や別の Windows ユーザーにコピーしても復号できない |
| macOS / Linux / Termux | `openssl enc -aes-256-cbc` + 金庫の隣に置くランダムなキーファイル（権限 600） | 画面共有やファイルコピーなどの不用意な流出。同じユーザーで動く悪意あるプログラムは**防げません** |
| `openssl` のない Android APK | 弱い難読化（設定に警告が表示されます） | 目に見えないようにするだけ — **頼らないでください** |

**特にご注意ください**
1. **フォルダを置き換えるアップデートはキーを消します。** 内蔵のアップデート（アップデートを確認 → アップデートをインストール）は `.vault/` を維持します。zip を「上書き」で手動再インストールするとフォルダが置き換わり、キーを入力し直す必要があります。
2. 金庫を失ったり復号できなくなったりした場合（別の Windows アカウント、OS の再インストールなど）、**キーは復元できません。** 元のキーは提供元で管理し、漏えいが疑われる場合は失効・再発行してください。
3. **`.vault/` をコミットしたり共有したりしないでください**（`.gitignore` に含まれています）。設定画面のスクリーンショットの共有にもご注意ください。
4. **旧バージョンはキーを平文で保存していました**（チャット DB と Blender のユーザー設定）。新バージョンの初回起動で金庫に移して削除しますが、**バックアップに古いコピーが残っている場合があります**（例：`userpref.blend@` ファイル、コピーした DB）。それらを共有したことがある場合は、古いキーを失効させてください。
5. **プロンプトにキーを貼り付けないでください。** プロンプト、AI の返答、添付画像はチャット DB に**平文で**ローカル保存され、選択した AI サービスに送信されます。Claude Code / Codex / agy はそれぞれのログインを使い、このアドオンはその認証情報を保存しません。
6. キーは HTTPS で提供元に送信されます（ローカルの Ollama/LM Studio は `http://localhost`）。AI が書いたコードは**あなたの権限で Blender 内で実行**され、ファイルを読める可能性があります。信頼できる AI サービスだけを使ってください。

**その他のセキュリティ上の注意**
- LAN アクセスは既定でオフです。オンにすると Bearer トークンが必要です。ローカルからのリクエストでも Origin/Host を検査します。
- このアドオンは AI が書いた **Python コードを Blender 内で実行**します。重要なファイルはバックアップし、信頼できるネットワークでのみ使用してください。

## 9. 既知の制限
- Android Termux 連携は未完成（上のお知らせを参照）
- Blender のテキスト欄で**韓国語入力中にスペースが入力できない**という報告があります（Blender/IME 側の問題と推測）。Web チャット UI での入力やクリップボード貼り付けボタンで回避できます。
- CLI エンジン（Claude/Codex/agy）は毎回新しい会話として実行されます（過去の会話は引き継がれません）
- 進行表示は文字ベースで、回転アニメーションはありません

## 10. バージョン規則

- 現在のバージョン：**0.8.3**
- **機能追加**：0.1 単位で上げる（0.8 → 0.9 → 1.0 …）
- **バグ修正**：0.0.1 単位で上げる（0.8.1 → 0.8.2 … 最大 0.8.999）
- Blender の `bl_info` には `(0, 8, 3)` のようなタプルで記録されます。変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照。
- `v*` タグをプッシュすると、GitHub Actions が zip をビルドして Releases に自動公開します。
- **リリースはバージョンごとに蓄積**されます（古いものは削除しません）。アドオン設定の**アップデートを確認**ボタンは*最新*のリリースを調べ、インストール済みより新しければそれでアップデートします。

## 11. 出典・参照（Credits）

このプロジェクトは、以下の仕様・ツール・サービスを**参照、または外部プログラムとして呼び出し**ています。名称および商標はそれぞれの所有者に帰属し、このプロジェクトとは提携関係にありません。

| 項目 | このプロジェクトでの利用 | 出典 |
|---|---|---|
| **MCP (Model Context Protocol)** | Blender 操作用サーバー（`mcp_handler.py`）と stdio ブリッジ（`mcp_bridge.py`）は、**公開仕様（プロトコルバージョン 2024-11-05）を見て自前で実装**。外部の MCP SDK のコードは含みません | Anthropic · <https://modelcontextprotocol.io> |
| **Claude Code** | 外部 CLI として実行（`claude -p`、`--model`、`--effort`、`--permission-mode`） | Anthropic · <https://docs.claude.com/en/docs/claude-code> |
| **Codex CLI** | 外部 CLI として実行（`codex exec`、`-m`、`-i`、`-c model_reasoning_effort`）、`~/.codex/config.toml` に MCP を登録 | OpenAI · <https://github.com/openai/codex> |
| **agy CLI** | 外部 CLI として実行（Antigravity） | Google Antigravity |
| **OpenRouter / NVIDIA NIM / Ollama · LM Studio** | Direct API モード（OpenAI 互換の Chat Completions 形式） | <https://openrouter.ai> · <https://build.nvidia.com> · <https://ollama.com> |
| **Blender Python API (`bpy`)** | アドオン UI、シーン操作、保存 | Blender Foundation · <https://docs.blender.org/api/current/> (GPL) |
| **glTF 2.0 / glTF-Blender-IO** | `.glb` エクスポートに Blender 内蔵の glTF アドオンを呼び出し | Khronos Group · <https://github.com/KhronosGroup/glTF-Blender-IO> (Apache-2.0) |
| **ambientCG** | AI ルールの「AmbientCG スタイルの PBR マテリアル」の参照（テクスチャファイルは含みません） | <https://ambientcg.com> (CC0) |
| **Termux** | Android 連携の対象環境（実験的） | <https://termux.dev> |
| **Windows DPAPI / OpenSSL** | API キーの暗号化保存（Windows は DPAPI、それ以外は `openssl enc -aes-256-cbc`） | Microsoft · <https://www.openssl.org> (Apache-2.0) |
| **GitHub Releases API** | アドオンの更新確認 | <https://docs.github.com/rest/releases> |
| **Python 標準ライブラリ** | `http.server`、`sqlite3`、`urllib`、`zipfile` など（外部パッケージは同梱していません） | Python Software Foundation |

- 外部ライブラリ/SDK のソースコードはこのリポジトリに**含まれていません**（標準ライブラリのみ）。外部サービスや CLI は、ユーザー自身でインストール・登録する必要があります。
- **Anthropic Claude Code** と協力して設計・実装しました。
- アドオンは `bpy` を使用するため、Blender の GPL と**互換性のあるライセンス（MIT ベース）** で配布します。
- 出典に漏れや誤りがあれば、issue でお知らせください。

## 12. 作者
- 作者：**refleaction**
- AI との協力：Anthropic **Claude Code** と共に設計・実装
- 非公式のプロジェクトであり、Blender Foundation、Anthropic、OpenAI、Google とは無関係です。

## 13. ライセンス

**MIT ベース + 表記の維持が条件**

- ✅ **ソースの改変**が可能
- ✅ **再配布**が可能（改変版・商用利用を含む）
- ⚠️ **著作権表示と出典は変更・削除しないでください。** 改変して再配布する場合も、元の作者（refleaction）とこのライセンス文をそのまま維持する必要があります。
- ソフトウェアは**現状のまま**提供され、利用によって生じた問題（作業ファイルの破損、キーの漏えい、API 料金など）について作者は責任を負いません。

全文は [LICENSE](LICENSE) ファイルをご覧ください。
