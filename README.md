# LCUS NY Police Lamp API

LCUS-1互換USBリレーをPythonのHTTP APIから操作します。Python 3.9以上。

## ハードウェアの製作に使用した部材

| 部材 | 製品・仕様 | 用途 |
| --- | --- | --- |
| USBリレー | 基板表記 `LCUS NY X1`（LCUS-1互換として制御） | PCからのON/OFF制御 |
| パトランプ | NIKKEI NICO MINI `VL04M-100NPR` 赤 | 点灯表示 |
| ケース | TAKACHI `PF13-4-9` | 制御部の収納 |
| USB延長ケーブル | Amazon Basics USB2.0延長ケーブル | ケース収納に伴うUSB接続の延長 |
| AC電源ケーブル | プラグ付き、長さ2m | AC電源の接続 |

パトランプを加工し、USBリレー経由でON/OFFを制御する構成として製作しました。

上記は使用部材の記録です。加工の詳細・配線図・電源仕様・リレー接点との適合性の確認結果は未記録です。ON/OFF命令の送信と3秒間隔での10セットの切り替え操作は実施済みですが、ソフトウェアでは実際の点灯・消灯を検知しません。商用電源部分を加工する場合は、メーカー資料と現物の定格を確認し、感電防止と接点・配線の絶縁を確保してください。

## セットアップ・起動

macOS・Windows（PowerShell）・Linuxに対応します。Python 3.9以上をインストールしてください。以下はプロジェクトを `~/src/lcus-ny-police-lamp` に配置した例です。

### macOS

```sh
cd ~/src/lcus-ny-police-lamp
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m serial.tools.list_ports -v
```

一覧でUSBリレーのポートを確認し、`.env` の `SERIAL_PORT` に記入します（例：`/dev/cu.usbserial-10`）。

```sh
.venv/bin/python app.py
```

### Windows（PowerShell）

```powershell
Set-Location ~/src/lcus-ny-police-lamp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
notepad .env
```

`.env` に `SERIAL_PORT=COM3` のように記入して保存します。番号は実際の一覧に合わせてください。デバイスマネージャーの「ポート (COM と LPT)」でも確認できます。

```powershell
.\.venv\Scripts\python.exe app.py
```

仮想環境のPythonを直接呼ぶため、PowerShellの実行ポリシー変更や `Activate.ps1` は不要です。`py` がない場合は、インストール済みPythonの `python` コマンドに置き換えてください。

### Linux

```sh
cd ~/src/lcus-ny-police-lamp
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m serial.tools.list_ports -v
```

`.env` の `SERIAL_PORT` に `/dev/ttyUSB0` など実際のポートを記入します。`/dev/serial/by-id/` に対応するリンクがあれば、そのパスを使うと接続順による番号の変化を避けられます。

```sh
.venv/bin/python app.py
```

Debian/Ubuntuで仮想環境の作成に失敗する場合は `sudo apt install python3-venv` を実行してください。ポートの権限エラーが出た場合は `ls -l /dev/ttyUSB0` で所有グループを確認します。Debian/Ubuntuでグループが `dialout` の場合は `sudo usermod -aG dialout "$USER"` を実行し、ログアウト・ログインしてから再起動してください。他のディストリビューションではグループ名が異なる場合があります。

### 共通事項

- `.env.example` のコピーは初回のみです。既存の `.env` がある場合は、そのファイルを編集してください。
- USBリレーの識別の目安はVID:PID `1A86:7523`（CH340系）です。同じチップを使う機器がある場合は、抜き差し前後の一覧で区別してください。
- ポートが表示されない場合はUSB接続とOSのデバイス認識を確認してください。WindowsでCH340のドライバーが不足している場合は、メーカー提供のドライバーが必要です。
- 標準の待受先は `http://127.0.0.1:8000`、シリアル通信は9600bps / 8N1です。
- 起動・終了時にはリレーの切り替え命令を送りません。終了は `Ctrl+C` です。

## API

```sh
curl -X POST http://127.0.0.1:8000/on
curl -X POST http://127.0.0.1:8000/off
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/health
```

PowerShellでは次のコマンドを使用します。

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/on
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/off
Invoke-RestMethod -Uri http://127.0.0.1:8000/status
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

| エンドポイント | 内容 |
| --- | --- |
| `POST /on` | `A0 01 01 A2` を送信 |
| `POST /off` | `A0 01 00 A1` を送信 |
| `GET /status` | ポートと最後に正常送信した命令を取得 |
| `GET /health` | APIサーバーの稼働確認（USB接続確認ではありません） |

リレーからの動作確認応答は読み取らないため、HTTP 200は送信成功を表します。接点の実際の状態は `physical_state: "unknown"` です。起動直後の `last_command` は `null`。通信失敗時はHTTP 503を返し、最後の成功した命令を保持します。

リレーのON/OFFとランプの点灯/消灯の対応はNO/NC端子の配線によって異なります。

## 設定（.env）

`app.py` と同じフォルダの `.env` を自動で読み込みます。別の作業ディレクトリから起動しても同じファイルを使用します。UTF-8で保存してください（BOM付きも対応）。

```dotenv
SERIAL_PORT=/dev/cu.usbserial-10
HOST=127.0.0.1
PORT=8000
```

| OS | `SERIAL_PORT` の例 |
| --- | --- |
| macOS | `/dev/cu.usbserial-10` |
| Windows | `COM3` |
| Linux | `/dev/ttyUSB0` または `/dev/serial/by-id/...` |

`SERIAL_PORT` は必須です。未設定の場合はエラーで終了します。`.env` はGit管理対象外で、共有用の雛形は `.env.example` です。変更を反映するにはサーバーを再起動してください。

設定の優先順位は **コマンドライン引数 > OS環境変数 > .env > 既定値** です。`--serial-port`、`--host`、`--port` で一時的に上書きできます。接続先ポートに既定値はありません。

他の端末から操作する場合は `.env` に `HOST=0.0.0.0` を指定し、クライアントからサーバーのLAN IPアドレスに接続してください。必要に応じてOSのファイアウォールで設定ポートへの接続を許可します。このAPIには認証がないため、信頼できるネットワーク内で使用してください。

## テスト（実機は操作しません）

macOS / Linux:

```sh
.venv/bin/python -m unittest -v
```

Windows（PowerShell）:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

APIのON/OFF命令、通信失敗、各OSのポート名を含む `.env` 読み込み、設定の優先順位をテストします。シリアル通信はモックを使用するため、実機の点灯・消灯確認は別途必要です。
