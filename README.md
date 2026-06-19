# VTuber 直播監測與觀看人數收集

## 專案目標

這個專案要做一個 VTuber 直播資料收集工具。

主要目標：

- 監測 VTuber 是否正在開台。
- 抓取直播中的即時觀看人數。
- 同時支援 YouTube 與 Twitch。
- 定期執行資料抓取。
- 將抓到的資料儲存到資料庫。
- 讓程式可以在 GitHub Actions 上自動執行。

## 初步執行頻率

目前初步規劃：

```text
每 5 分鐘抓取一次
```

後續可以依照實際穩定性、API 限制與 YouTube 抓取速度再調整。

## 本機每 5 分鐘執行

如果 GitHub Actions 上的 YouTube 抓取受到限制，可以先在本機用長駐程式每 5 分鐘執行一次完整抓取。

執行前先設定 Twitch API 環境變數：

```powershell
$env:TWITCH_CLIENT_ID="你的 Twitch Client ID"
$env:TWITCH_CLIENT_SECRET="你的 Twitch Client Secret"
```

啟動本機排程：

```powershell
python src/run_local_scheduler.py
```

也可以直接執行專案根目錄的 bat 檔：

```powershell
.\start_local_scheduler.bat
```

預設行為：

- 固定使用 `Asia/Taipei` 顯示時間。
- 對齊每小時的 `00`、`05`、`10`、`15` 分執行。
- 每輪會呼叫 `collect_all.py` 的相同流程。
- 每輪結束會列出目前 YouTube / Twitch 各有幾個直播，以及直播清單。
- 會先確認 `live_data.db` 與 `streamer_config.db` 的必要資料表存在。
- 按 `Ctrl+C` 可以停止。

測試只跑一次：

```powershell
python src/run_local_scheduler.py --once
```

修改執行間隔：

```powershell
python src/run_local_scheduler.py --interval-seconds 600
```

如果希望啟動後先立刻跑一次，再等待下一個對齊時間：

```powershell
python src/run_local_scheduler.py --run-immediately
```

## 預計執行環境

目標執行環境：

```text
GitHub Actions
```

本機開發與測試仍會使用目前資料夾內的 SQLite database。

## 目前資料來源

目前會使用兩個 SQLite database：

```text
streamer_config.db
live_data.db
```

用途：

| Database | 用途 |
| --- | --- |
| `streamer_config.db` | 人工維護 VTuber 名單，包含多張 `streamer_團體` 表 |
| `live_data.db` | 程式執行用資料庫，包含同步後的單一 `streamer` 表與抓取結果 |

資料流：

```text
streamer_config.db 的 streamer_團體表
-> sync_streamers.py
-> live_data.db 的 streamer 表
-> Twitch / YouTube collector
```

`streamer_config.db` 的用途：

- 記錄要追蹤哪些 VTuber。
- 記錄各 VTuber 的 YouTube / Twitch 來源。
- 方便依照團體分表維護名單。

`live_data.db.streamer` 的用途：

- 提供 collector 統一讀取的 VTuber 清單。
- 提供前端查詢 VTuber 基本資料。
- 避免 collector 直接依賴多張團體表。

## 待定資料表

接下來需要補上新的資料表設計。

### streamer

用途：

```text
記錄要監測的 VTuber 與其平台連結。
```

目前 streamer 設計分成兩層。

第一層是人工維護用的 config 表：

- 存在 `streamer_config.db`。
- 拆成多張 `streamer_團體代號` 表。
- 每張表代表一個團體或分類。
- 方便手動修改各團體資料。
- 所有 config streamer 表必須使用相同欄位格式。

第二層是程式讀取用的 live 表：

- 存在 `live_data.db`。
- 表名固定為 `streamer`。
- 由 `sync_streamers.py` 從 `streamer_config.db` 同步產生。
- Twitch / YouTube collector 只讀這張單一 `streamer` 表。

config 表命名規則：

```text
streamer_團體代號
```

範例：

```text
streamer_meridian
streamer_teraz
streamer_moonlit
streamer_independent
```

config streamer 表目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `vtuber_id` | `TEXT` | 是 | 不重複的單一 VTuber ID，使用英數與底線，例如 `rei`、`koyuki` |
| `name` | `TEXT` | 是 | VTuber 顯示名稱，例如 `澪Rei` |
| `youtube_url` | `TEXT` | 否 | YouTube 頻道連結 |
| `youtube_channel_id` | `TEXT` | 否 | YouTube 真正的 channel id，比 handle / URL 穩定 |
| `twitch_url` | `TEXT` | 否 | Twitch 頻道連結 |
| `twitch_login` | `TEXT` | 否 | Twitch API 查詢用 login，比從 URL 解析穩定 |
| `enabled` | `INTEGER` | 是 | 是否啟用監測，`1` 代表啟用，`0` 代表停用 |
| `display_order` | `INTEGER` | 否 | 顯示或報表排序用 |
| `note` | `TEXT` | 否 | 備註 |
| `created_at` | `TEXT` | 是 | 建立時間 |
| `updated_at` | `TEXT` | 是 | 最後修改時間 |

參考 SQL：

```sql
CREATE TABLE streamer_group_name (
    vtuber_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    youtube_url TEXT,
    youtube_channel_id TEXT,
    twitch_url TEXT,
    twitch_login TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    display_order INTEGER,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

`live_data.db.streamer` 目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `vtuber_id` | `TEXT` | 是 | 不重複的單一 VTuber ID |
| `group_name` | `TEXT` | 是 | 來源團體代號，例如 `meridian` |
| `name` | `TEXT` | 是 | VTuber 顯示名稱 |
| `youtube_url` | `TEXT` | 否 | YouTube 頻道連結 |
| `youtube_channel_id` | `TEXT` | 否 | YouTube channel id |
| `twitch_url` | `TEXT` | 否 | Twitch 頻道連結 |
| `twitch_login` | `TEXT` | 否 | Twitch API 查詢用 login |
| `enabled` | `INTEGER` | 是 | 是否啟用監測 |
| `display_order` | `INTEGER` | 否 | 排序用 |
| `note` | `TEXT` | 否 | 備註 |
| `synced_at` | `TEXT` | 是 | 最近同步時間 |

注意事項：

- `vtuber_id` 必須全資料庫唯一，即使分散在不同團體表也不能重複。
- `youtube_url` 和 `twitch_url` 主要方便人工查看與維護。
- `youtube_channel_id` 和 `twitch_login` 主要給程式穩定查詢。
- 沒有 YouTube 或 Twitch 的 VTuber，對應欄位可以留空。
- 若 VTuber 暫停追蹤，不要刪除資料，改將 `enabled` 設為 `0`。
- collector 不直接讀取 `streamer_config.db`，而是讀取同步後的 `live_data.db.streamer`。

### 直播資料儲存表

用途：

```text
儲存每次抓取到的直播狀態與即時觀看人數。
```

設計目標分成兩種：

- 讓前端快速知道「現在有哪些人正在開台」。
- 長期紀錄每場直播的即時觀看人數變化。

因此目前建議拆成三種資料表：

| 表 | 用途 |
| --- | --- |
| `stream` | 記錄一場直播本身 |
| `stream_snapshot` | 每次抓取時記錄即時觀看人數與當下直播資訊 |
| `current_live_status` | 給前端快速查詢目前正在直播的人 |
| `working` | 記錄每次抓取任務的執行狀態與錯誤 |

### stream

用途：

```text
記錄一場直播的基本資料。
```

一場 YouTube 直播或 Twitch 直播都會在這裡有一筆資料。

目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `stream_id` | `INTEGER` | 是 | 內部直播 ID，主鍵 |
| `vtuber_id` | `TEXT` | 是 | 對應 streamer 表的 `vtuber_id` |
| `platform` | `TEXT` | 是 | 平台，使用 `youtube` 或 `twitch` |
| `platform_stream_id` | `TEXT` | 是 | 平台上的直播 ID，例如 YouTube video id 或 Twitch stream id |
| `stream_url` | `TEXT` | 否 | 直播連結，YouTube 通常會有固定影片連結 |
| `title` | `TEXT` | 否 | 目前已知的直播標題 |
| `category` | `TEXT` | 否 | 目前已知的分類或遊戲名稱，Twitch 較常用 |
| `tags` | `TEXT` | 否 | 直播標籤，可先用 JSON 字串儲存 |
| `started_at` | `TEXT` | 否 | 直播開始時間 |
| `ended_at` | `TEXT` | 否 | 直播結束時間 |
| `first_seen_at` | `TEXT` | 是 | 第一次被程式抓到的時間 |
| `last_seen_at` | `TEXT` | 是 | 最後一次被程式確認仍在直播的時間 |
| `created_at` | `TEXT` | 是 | 資料建立時間 |
| `updated_at` | `TEXT` | 是 | 資料更新時間 |

參考 SQL：

```sql
CREATE TABLE stream (
    stream_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    platform_stream_id TEXT NOT NULL,
    stream_url TEXT,
    title TEXT,
    category TEXT,
    tags TEXT,
    started_at TEXT,
    ended_at TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (platform, platform_stream_id)
);
```

注意事項：

- `platform_stream_id` 用來判斷是不是同一場直播。
- YouTube 可以使用 video id。
- Twitch 可以使用 Helix API 回傳的 stream id。
- `title`、`category`、`tags` 可能在直播中改變，所以 `stream` 表只保存目前已知的最新狀態。

### stream_snapshot

用途：

```text
每次抓取時，紀錄該時間點的觀看人數與直播資訊快照。
```

這張表是長期分析觀看人數變化的主要資料表。

目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `snapshot_id` | `INTEGER` | 是 | 快照 ID，主鍵 |
| `stream_id` | `INTEGER` | 是 | 對應 `stream.stream_id` |
| `vtuber_id` | `TEXT` | 是 | 對應 streamer 表的 `vtuber_id`，方便查詢 |
| `platform` | `TEXT` | 是 | 平台，使用 `youtube` 或 `twitch` |
| `viewer_count` | `INTEGER` | 是 | 當下即時觀看人數 |
| `captured_at` | `TEXT` | 是 | 抓取時間 |
| `title` | `TEXT` | 否 | 當下抓到的直播標題 |
| `category` | `TEXT` | 否 | 當下抓到的分類或遊戲名稱 |
| `tags` | `TEXT` | 否 | 當下抓到的直播標籤，可先用 JSON 字串儲存 |

參考 SQL：

```sql
CREATE TABLE stream_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id INTEGER NOT NULL,
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    viewer_count INTEGER NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT,
    category TEXT,
    tags TEXT,
    FOREIGN KEY (stream_id) REFERENCES stream(stream_id)
);
```

注意事項：

- 長期觀看人數紀錄主要看這張表。
- `captured_at` 可以同時代表日期與時間；之後查詢時再用 SQL 或程式拆成日期、時間。
- 因為標題與標籤可能在直播中改變，所以快照表也保留當下抓到的 `title`、`category`、`tags`。
- 建議只在直播中時寫入快照，沒直播的狀態交給 `current_live_status` 處理。

### current_live_status

用途：

```text
讓前端快速查詢目前哪些 VTuber 正在直播。
```

這張表只保存每個 VTuber 在每個平台的最新狀態，不作為長期歷史紀錄。

目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `vtuber_id` | `TEXT` | 是 | 對應 streamer 表的 `vtuber_id` |
| `platform` | `TEXT` | 是 | 平台，使用 `youtube` 或 `twitch` |
| `is_live` | `INTEGER` | 是 | 是否正在直播，`1` 代表直播中，`0` 代表未直播 |
| `stream_id` | `INTEGER` | 否 | 如果正在直播，對應 `stream.stream_id` |
| `viewer_count` | `INTEGER` | 否 | 最新一次抓到的即時觀看人數 |
| `stream_url` | `TEXT` | 否 | 最新直播連結 |
| `title` | `TEXT` | 否 | 最新直播標題 |
| `category` | `TEXT` | 否 | 最新分類或遊戲名稱 |
| `tags` | `TEXT` | 否 | 最新直播標籤 |
| `started_at` | `TEXT` | 否 | 直播開始時間 |
| `last_checked_at` | `TEXT` | 是 | 最近一次檢查時間 |
| `last_live_at` | `TEXT` | 否 | 最近一次確認直播中的時間 |

參考 SQL：

```sql
CREATE TABLE current_live_status (
    vtuber_id TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('youtube', 'twitch')),
    is_live INTEGER NOT NULL DEFAULT 0,
    stream_id INTEGER,
    viewer_count INTEGER,
    stream_url TEXT,
    title TEXT,
    category TEXT,
    tags TEXT,
    started_at TEXT,
    last_checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_live_at TEXT,
    PRIMARY KEY (vtuber_id, platform),
    FOREIGN KEY (stream_id) REFERENCES stream(stream_id)
);
```

注意事項：

- 前端查目前開台列表時，主要查這張表。
- 每次排程跑完都更新這張表。
- 主鍵使用 `(vtuber_id, platform)`，因此同一個 VTuber 可以同時在 YouTube 和 Twitch 開台，兩邊狀態會分開保存。
- 之後前端如果要顯示「一個 VTuber 目前有哪些平台正在直播」，需要用 `vtuber_id` 分組讀取多筆平台狀態。
- 如果某 VTuber 從直播中變成未直播，將 `is_live` 改為 `0`，並保留上一場直播資訊供除錯或顯示使用。
- 長期統計不要查這張表，要查 `stream_snapshot`。

### 時間欄位原則

時間欄位目前統一使用 `TEXT` 儲存 ISO 格式時間。

建議原則：

- 儲存時使用 UTC。
- 前端顯示時再轉成需要的時區。
- 不另外拆 `date` 與 `time` 欄位，避免資料重複與不一致。
- 如果之後查詢需求很多，再用 SQL view 或額外欄位處理日期彙整。

### working

用途：

```text
記錄每次抓取任務的執行狀態、統計結果與錯誤訊息。
```

目前規劃欄位：

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `working_id` | `INTEGER` | 是 | 任務紀錄 ID，主鍵 |
| `job_name` | `TEXT` | 是 | 任務名稱，例如 `twitch_collector`、`youtube_collector` |
| `platform` | `TEXT` | 否 | 平台，例如 `youtube`、`twitch`，總任務可留空 |
| `status` | `TEXT` | 是 | 狀態：`running`、`success`、`partial_success`、`failed` |
| `started_at` | `TEXT` | 是 | 任務開始時間 |
| `finished_at` | `TEXT` | 否 | 任務結束時間 |
| `elapsed_seconds` | `REAL` | 否 | 任務執行秒數 |
| `checked_count` | `INTEGER` | 是 | 本次檢查頻道數 |
| `live_count` | `INTEGER` | 是 | 本次直播中頻道數 |
| `offline_count` | `INTEGER` | 是 | 本次未直播頻道數 |
| `snapshots_inserted` | `INTEGER` | 是 | 本次新增觀看人數快照數 |
| `error_count` | `INTEGER` | 是 | 本次錯誤數 |
| `error_message` | `TEXT` | 否 | 錯誤摘要 |
| `summary` | `TEXT` | 否 | 額外摘要，可用 JSON 字串 |

參考 SQL：

```sql
CREATE TABLE IF NOT EXISTS working (
    working_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    platform TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial_success', 'failed')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    elapsed_seconds REAL,
    checked_count INTEGER NOT NULL DEFAULT 0,
    live_count INTEGER NOT NULL DEFAULT 0,
    offline_count INTEGER NOT NULL DEFAULT 0,
    snapshots_inserted INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    summary TEXT
);
```

### YouTube 特例紀錄

#### 會員限定直播

觀察日期：

```text
2026-06-19
```

測試頻道：

```text
https://www.youtube.com/@ItsukiIanvs/streams
```

觀察到的特例：

- 頻道當時有一個會員限定直播。
- `/live` 沒有指到該會員限定直播，而是指到另一個待機直播。
- `/streams` 的 flat playlist 可以看到會員限定直播的基本資料，例如影片 ID、標題、URL。
- 直接用 `yt-dlp` 查會員限定影片詳細資料會失敗。

當時觀察到的會員限定影片：

```text
id: eq-hL6RQjSA
title: 【會限】這是一個養喉嚨的會限 | 玥Itsuki
url: https://www.youtube.com/watch?v=eq-hL6RQjSA
```

直接查影片時的錯誤：

```text
Join this channel to get access to members-only content like this video, and other exclusive perks.
```

這代表未來 YouTube collector 需要處理以下狀況：

- 不能只依賴 `/live` 判斷所有直播。
- `/streams` 可能能看到會員限定直播候選，但無登入 cookies 時無法取得詳細資料。
- 會員限定直播可能無法取得即時觀看人數。
- 這種狀況應該被記錄成特殊狀態，而不是當成一般抓取失敗。

後續可能需要考慮的處理方式：

- 在 `current_live_status` 或錯誤 log 中標記 `members_only`。
- 對會員限定直播只保存可取得的基本資訊，例如 `platform_stream_id`、`stream_url`、`title`。
- 若未來需要完整資料，可能要支援 YouTube cookies，但 cookies 不可 commit 到 Git。

## 待辦事項

- [ ] 定義新的 `streamer` 表格式。
- [ ] 定義抓取結果的儲存資料表格式。
- [ ] 決定 YouTube 與 Twitch 的欄位如何統一。
- [ ] 撰寫 Twitch 直播狀態與觀看人數抓取程式。
- [ ] 撰寫 YouTube 直播狀態與觀看人數抓取程式。
- [ ] 撰寫統一執行入口。
- [ ] 將抓取結果寫入資料庫。
- [ ] 加入錯誤處理與紀錄。
- [ ] 設定 GitHub Actions 每 5 分鐘執行。
- [ ] 確認 GitHub Actions 上的資料庫保存方式。

## 舊測試檔

舊的原型測試檔已整理到：

```text
legacy_prototypes/
```

這些檔案只作為測試參考，後續正式程式會另外建立新檔案。

## 專案檔案規劃

目前正式專案檔案會依照以下方向整理：

```text
sql_init/
src/
```

### sql_init

`sql_init/` 用來保存每張資料表的 SQL schema。

目前規劃：

```text
sql_init/001_streamer_template.sql
sql_init/002_streamer.sql
sql_init/010_stream.sql
sql_init/011_stream_snapshot.sql
sql_init/012_current_live_status.sql
sql_init/013_working.sql
```

其中：

| 檔案 | 說明 |
| --- | --- |
| `001_streamer_template.sql` | 建立 `streamer_config.db` 團體表的模板 |
| `002_streamer.sql` | 建立 `live_data.db.streamer` 同步表 |
| `010_stream.sql` | 建立 `stream` 表 |
| `011_stream_snapshot.sql` | 建立 `stream_snapshot` 表 |
| `012_current_live_status.sql` | 建立 `current_live_status` 表 |
| `013_working.sql` | 建立 `working` 表 |

之後如果新增或修改資料表，會保留對應 SQL 檔，方便檢視表格格式與追蹤修改。

### src

`src/` 用來放正式 Python 程式。

目前已有工具：

```text
src/init_db.py
src/init_streamer_config.py
src/create_streamer_group.py
src/add_streamer.py
src/list_streamers.py
src/sync_streamers.py
src/twitch_collector.py
src/youtube_collector.py
src/collect_all.py
```

### init_db.py

用途：

```text
初始化 live data SQLite database。
```

目前預設會建立：

```text
live_data.db
```

會建立或確認：

```text
live_data.db.streamer
stream
stream_snapshot
current_live_status
working
```

使用方式：

```powershell
python src/init_db.py
```

也可以指定 database：

```powershell
python src/init_db.py --database live_data.db
```

### init_streamer_config.py

用途：

```text
初始化人工維護用的 streamer config database。
```

目前預設會建立：

```text
streamer_config.db
```

預設建立的團體表：

```text
streamer_meridian
streamer_squarelive
```

使用方式：

```powershell
python src/init_streamer_config.py
```

也可以指定 database 和團體：

```powershell
python src/init_streamer_config.py --database streamer_config.db --group meridian --group squarelive
```

### create_streamer_group.py

用途：

```text
快速建立指定名稱的 streamer 團體表。
```

使用方式：

```powershell
python src/create_streamer_group.py meridian
```

預設會建立或確認以下資料表：

```text
streamer_meridian
```

預設 database：

```text
streamer_config.db
```

也可以指定 database：

```powershell
python src/create_streamer_group.py teraz --database streamer_config.db
```

### add_streamer.py

用途：

```text
新增或更新 streamer_config.db 指定團體表中的 VTuber。
```

範例：

```powershell
python src/add_streamer.py meridian rei "澪Rei" `
  --youtube-url "https://www.youtube.com/@%E6%BE%AARei" `
  --twitch-url "https://www.twitch.tv/reirei_neon" `
  --twitch-login "reirei_neon"
```

### list_streamers.py

用途：

```text
列出 live_data.db 中同步後的 streamer 表資料。
```

使用方式：

```powershell
python src/list_streamers.py
```

包含停用資料：

```powershell
python src/list_streamers.py --all
```

### sync_streamers.py

用途：

```text
將 streamer_config.db 的多張 streamer_團體表同步到 live_data.db 的單一 streamer 表。
```

使用方式：

```powershell
python src/sync_streamers.py
```

也可以指定 database：

```powershell
python src/sync_streamers.py --config-database streamer_config.db --live-database live_data.db
```

注意事項：

- 同步時會檢查 `vtuber_id` 是否重複。
- 同步時會重建 `live_data.db.streamer` 的內容。
- collector 只讀同步後的 `live_data.db.streamer`。

### twitch_collector.py

用途：

```text
抓取 Twitch 直播狀態與即時觀看人數，並寫入資料庫。
```

會更新：

```text
stream
stream_snapshot
current_live_status
working
```

需要環境變數：

```powershell
$env:TWITCH_CLIENT_ID="你的 Client ID"
$env:TWITCH_CLIENT_SECRET="你的 Client Secret"
```

使用方式：

```powershell
python src/twitch_collector.py
```

目前測試狀態：

```text
已確認可以讀取 streamer 表，寫入 stream / stream_snapshot / current_live_status，並記錄 working 執行紀錄。
```

### youtube_collector.py

用途：

```text
使用 yt-dlp 抓取 YouTube 直播狀態與即時觀看人數，並寫入資料庫。
```

會更新：

```text
stream
stream_snapshot
current_live_status
working
```

使用方式：

```powershell
python src/youtube_collector.py
```

目前測試狀態：

```text
已確認可以讀取 streamer 表、抓取 YouTube /live、寫入 stream / stream_snapshot / current_live_status，並記錄 working 執行紀錄。
```

### collect_all.py

用途：

```text
統一執行 Twitch 與 YouTube collector。
```

執行順序：

```text
1. sync_streamers.py：同步 streamer_config.db -> live_data.db.streamer
2. twitch_collector.py
3. youtube_collector.py
```

會額外在 `working` 表記錄一筆總任務：

```text
job_name = collect_all
platform = NULL
```

同時 Twitch 與 YouTube collector 仍會各自寫入自己的 `working` 紀錄。

需要 Twitch 環境變數：

```powershell
$env:TWITCH_CLIENT_ID="你的 Client ID"
$env:TWITCH_CLIENT_SECRET="你的 Client Secret"
```

使用方式：

```powershell
python src/collect_all.py
```

也可以指定 database：

```powershell
python src/collect_all.py --config-database streamer_config.db --database live_data.db
```

目前測試狀態：

```text
已確認可以先同步 streamer，再依序執行 Twitch 與 YouTube collector，並寫入 collect_all / twitch_collector / youtube_collector 三種 working 紀錄。
```
