# Overflow Recorder（直播錄影備份腳本）

[English](README.en.md) | [繁體中文](README.md)

這是一個 [OBS Studio](https://obsproject.com/) 的 Python 腳本，會在你的直播接近 **YouTube 12 小時封存保留限制** 時自動開始本機錄影，把 YouTube 會捨棄掉的那段直播內容保存到本機。

## 為什麼需要

YouTube 直播的自動封存（VOD）上限是 **12 小時**。只要直播超過 12 小時，第 12 小時之後的內容會在 YouTube 端靜悄悄地遺失。把 YouTube 的封存（0–12 小時）和這個腳本的本機錄影（11 小時 55 分之後）拼起來，你就有一份完整的直播檔可用於剪輯或重新上傳。

腳本會在 12 小時刻度之前幾分鐘（預設 11 小時 55 分，可調整）開始本機錄影，避免在分界秒數上漏掉內容。

## 需求

- OBS Studio 30 以上版本（Python 腳本功能內建於 OBS）。
- 已啟用 OBS Python 腳本引擎，並指向一份 Python 3.11 安裝。
  各作業系統的設定方式請見下方 **Python 環境設定**。

## 安裝

1. 下載 `overflow_recorder.py`（或 clone 這個 repo）。
2. 在 OBS 中開啟 **工具（Tools）→ 指令碼（Scripts）**。
3. 在 **指令碼（Scripts）** 分頁中按 **+**，選擇 `overflow_recorder.py`。
4. 切換到 **指令碼屬性（Script Properties）** 分頁（先選取剛載入的腳本）並確認：
   - **Enabled** 已勾選。
   - **Threshold (minutes)** 是 `715`（= 11 小時 55 分）。要做快速完整測試請設為 `1`（見下方 **測試** 一節）。
5. 按下 **Script Log** 按鈕可檢視腳本的執行訊息。

## Python 環境設定

OBS 的 Python 腳本需要一份 OBS 能找到的 Python 3.11 直譯器。設定位置在 **工具 → 設定 → 進階 → Python**（某些版本在 **工具 → 指令碼 → Python 設定**）。

### macOS

OBS 不會附帶 Python。請安裝 Python 3.11 並把 OBS 指向它：

```sh
brew install python@3.11
```

然後把 OBS 的 Python 路徑設為
`/opt/homebrew/opt/python@3.11/Frameworks/Python.framework/Versions/3.11`（Apple Silicon）或
`/usr/local/opt/python@3.11/Frameworks/Python.framework/Versions/3.11`（Intel）。該目錄的 `bin/` 內必須包含 `Python` 執行檔。

### Windows

較新版的 OBS for Windows 已附帶 Python 直譯器。若 **Python 設定** 呈灰色或顯示錯誤，請安裝
[Python 3.11](https://www.python.org/downloads/release/python-3110/)，再把 OBS 指向其安裝目錄。

### Linux

使用你發行版提供的 Python 3.11（例如 Debian/Ubuntu 上的 `python3.11`）。把 OBS 的 Python 路徑設為內含 `python3.11` 的目錄。

## 設定

| 設定項 | 預設值 | 說明 |
|---|---|---|
| Enabled | 開啟 | 總開關。不必卸載腳本即可停用。 |
| Threshold (minutes) | 715 | 何時（直播進行幾分鐘後）要開始本機錄影。715 = 11 小時 55 分。測試時設為 `1`。 |

## 行為

- **直播開始時** — 使用單調時鐘（monotonic clock）記錄起始時間，可免疫系統時鐘漂移與 NTP 校時。
- **每 30 秒** — 檢查直播進行時間；當進行時間 ≥ 閾值，透過 `obs_frontend_recording_start()` 開始本機錄影。
  - 如果你本來就已經在錄影（例如從 t=0 就開始本機錄），腳本不會去動它。
- **如果你在 overflow 錄影期間手動停止錄影** — 腳本會尊重你的動作，該次直播剩餘時間內不會再自動啟動錄影。
- **直播停止時** — 如果錄影是腳本啟動的，腳本會停止錄影。如果是你自己啟動的，則不動。
- **當機／重新載入復原** — 起始時間會以小型 JSON 檔保存在腳本旁邊（`overflow_recorder_state.json`）。重新載入時，若 OBS 表示直播仍在進行，腳本會接續原狀態；若 OBS 顯示未在直播，過時的狀態檔會被丟棄。

## 測試

不要傻等 12 小時。完整測試只需約 2 分鐘：

1. 把 **Threshold (minutes)** 設為 `1`。
2. 開始直播（你可以用一個丟棄用的 RTMP 目標，例如 `rtmp://localhost/live`，這樣不會真的播出去；OBS 仍會送出直播開始事件）。
3. 觀察 **Script Log**，應該會看到：
   - `Stream started. Threshold at +1m0s (wall clock ~HH:MM:SS).`
   - 約 60 秒後：`Threshold reached after 1m0s; started overflow recording.`
   - OBS 的錄影指示燈亮起。
4. 停止直播，應該會看到：
   - `Stream stopped; stopping overflow recording.`
5. 真正使用時，把 **Threshold (minutes)** 改回 `715`。

建議也測一次：當腳本正在錄影時，手動按 OBS 的 **停止錄影** 按鈕。Log 應顯示 `Overflow recording stopped by user; respecting and will not restart`，且腳本在該次直播剩餘時間內不會再啟動錄影。

## 疑難排解

**Script log 在哪？**
**工具 → 指令碼（Scripts）→ Script Log** 按鈕（不是分頁，是指令碼視窗下方的按鈕）。

**到了閾值卻沒開始錄影。**
打開 script log，找 `FAILED to start overflow recording` 或 `ERROR: unhandled exception`。最常見原因是 OBS 的錄影輸出設定錯誤（輸出路徑錯、未選編碼器）。請到 **設定 → 輸出 → 錄影** 修正。

**OBS 直播中途重啟後，腳本沒接續。**
下次啟動時查看 log 中的 `Recovered state across reload` 或 `State file's start time is in the future`。後者代表機器重開過（單調時鐘歸零），腳本會選擇放棄而不是亂猜。

## 平台支援

- **macOS**：已在 macOS 26（Darwin 25.5.0）、OBS 30+ 與 Homebrew 安裝的 Python 3.11 上測試。
- **Windows / Linux**：作者尚未親自驗證。腳本只使用跨平台的 OBS Python API（`obspython`），理論上可運作；若遇到問題請至
  https://github.com/gordonxc/obs-recorder/issues 回報。

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
