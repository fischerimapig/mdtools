## R2：Documentモデルと元原稿位置

親#52、Milestone M2-redesign（10）。#54の契約・profile・差分表の承認と先行PRマージを着手条件とする。最新 `milestone/m2-redesign` から `issue/55-document-model` を分岐し同MilestoneへPRする。

利用者が原稿の一文字へ戻れる出典と失敗状態を保つ。試作 `model.py` のSourceIndex/ByteRange/Node/Attribute/DocumentParseを再利用候補とし、本番配置案 `mdtools/document/model.py` とsource bridgeをレビューする。本文を共有snapshotの範囲で保持し、重複属性・不正トークン・開閉・本文・coverageを失わない。spec/Workspace/CLI/solverへ逆依存せず、公開SourceSpan/IRの座標単位は変更しない。

`SourceSnapshot → SourceIndex`、`byte_range(cp_start, cp_end)`、`slice(byte_range)`、`span(byte_range)` の半開契約を固定する。小入力 `a\r\n界\rZ\n` はbyte境界 `[0,1,2,3,6,7,8,9]`、界の開始はbyte3/2行1列、EOFは4行1列。CRLF途中byte2はSourceSpanに変換できず丸めない。UTF-8内部byteも拒否する。単一snapshotの同一性、親子包含、兄弟順、coverageの非重複全域partitionを検証する。

正常空はcomplete/0件。opaque EOFと不正Divを区別し、未知profile/byte超過はrejected、途中上限はpartial、engine/invariant失敗はfailedと元範囲を保持する。未対応はunsupported、未処理はunparsed。意味・JSON・参照・式の成功はモデルから推論しない。`parse_document(source, *, profile, limits)` と後続extractorの境界は#54に従い、本体未完成のfake completeを本番へ接続しない。

必須試験は `test_independent_original_coordinates`、`test_reject_boundaries_without_rounding`、`test_snapshot_identity_is_not_uri_identity`、`test_document_partition_and_ownership`。Cには `C-unicode-crlf` / `C-unicode-cr` を継承する。実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（[results](../results.md)）。今後は本番配置後の同契約試験、python -S、公開SourceSpan回帰を実行する。

成果物は最小モデル、bridge、不変条件、異常試験と文書。#58/#59/#60が同契約を利用でき、所定PRマージ後にClose。Block/Inline全文法、意味検査、FFI/Rust、複数snapshot連結と#31は対象外。
