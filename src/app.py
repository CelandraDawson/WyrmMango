from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QDate
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database import DEFAULT_DB


APP_TITLE = "WyrmMango"
APP_VERSION = "0.2.0"
# GMAIL_MULTI_ACCOUNT_UI_020: multi-select Gmail filtering + account inventory
# COMPACT_CONTROL_GEOMETRY_FIX_020: minimum geometry for compact form/filter controls
# IMPORT_PROGRESS_COMPLETION_FIX_020: stop indeterminate progress bar when import finishes
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMPORTER_PATH = Path(__file__).resolve().parent / "import_archive.py"
ASSET_DIR = PROJECT_ROOT / "assets"
BRAND_ICON = ASSET_DIR / "wyrmmango_icon.png"


STYLE = """
QWidget {
    background-color: #07111f;
    color: #edf7ff;
    font-family: "Segoe UI";
    font-size: 13px;
}

QMainWindow {
    background-color: #07111f;
}

QLabel {
    background-color: transparent;
}

QFrame#sidebar {
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #0b1d31,
        stop:0.52 #0a1828,
        stop:1 #081522
    );
    border-right: 1px solid #18364d;
}

QFrame#heroCard {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #0b2237,
        stop:0.55 #0b1a2b,
        stop:1 #101a28
    );
    border: 1px solid #1e4961;
    border-radius: 18px;
}

QFrame#filterCard,
QFrame#panelCard,
QFrame#importCard {
    background-color: #0b1827;
    border: 1px solid #17344a;
    border-radius: 15px;
}

QPushButton#gmailAccountFilterAll {
    background-color: #184861;
    border: 1px solid #54ddff;
    color: #e8fbff;
    font-weight: 600;
    padding: 7px 11px;
    border-radius: 8px;
}

QPushButton#gmailAccountFilterActive {
    background-color: #4b3814;
    border: 1px solid #e7b84f;
    color: #fff4ca;
    font-weight: 700;
    padding: 7px 11px;
    border-radius: 8px;
}

QPushButton#gmailAccountFilterAll:disabled,
QPushButton#gmailAccountFilterActive:disabled {
    background-color: #101d29;
    border-color: #294052;
    color: #6f8798;
}

QMenu {
    background-color: #0b1827;
    color: #edf7ff;
    border: 1px solid #2b536b;
    padding: 5px;
}

QMenu::item {
    padding: 7px 24px 7px 9px;
    border-radius: 5px;
}

QMenu::item:selected {
    background-color: #14344a;
}

QMenu::item:checked {
    background-color: #184861;
    color: #ffffff;
    font-weight: 700;
}

QFrame#statCard {
    background-color: #0c2033;
    border: 1px solid #1b4058;
    border-radius: 12px;
}

QFrame#goldAccentCard {
    background-color: #211a0f;
    border: 1px solid #6f501d;
    border-radius: 13px;
}

QLabel#brand {
    color: #f7fbff;
    font-size: 29px;
    font-weight: 700;
}

QLabel#tagline {
    color: #88a8be;
    font-size: 12px;
}

QLabel#pageTitle {
    color: #f8fcff;
    font-size: 25px;
    font-weight: 700;
}

QLabel#heroSubtitle {
    color: #9ab5c8;
    font-size: 13px;
}

QLabel#eyebrow {
    color: #ffb52e;
    font-size: 10px;
    font-weight: 700;
}

QLabel#section {
    color: #5e8aa5;
    font-size: 10px;
    font-weight: 700;
}

QLabel#paneTitle {
    color: #d9efff;
    font-size: 13px;
    font-weight: 700;
}

QLabel#statNumber {
    color: #ffba3a;
    font-size: 22px;
    font-weight: 700;
}

QLabel#statLabel {
    color: #78a3bd;
    font-size: 9px;
    font-weight: 600;
}

QLabel#privacy {
    background-color: #082a27;
    color: #7bf1d0;
    border: 1px solid #176256;
    border-radius: 12px;
    padding: 12px;
}

QLabel#version {
    color: #4f7188;
    font-size: 9px;
}

QLabel#resultCount {
    color: #72ddfa;
    font-size: 11px;
    font-weight: 600;
}

QLabel#success {
    color: #6ee7bd;
    font-weight: 700;
}

QLabel#warning {
    color: #ffbd4a;
    font-weight: 700;
}

QLineEdit, QComboBox, QDateEdit {
    background-color: #0d2033;
    color: #eef8ff;
    border: 1px solid #24475f;
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: #2a7896;
}

QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
    border: 1px solid #32627f;
}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #38d8ff;
    background-color: #10263b;
}

QLineEdit:disabled, QDateEdit:disabled {
    color: #526d80;
    background-color: #0a1724;
    border: 1px solid #162d3f;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QPushButton {
    background-color: #0e2b3f;
    color: #dff7ff;
    border: 1px solid #235a75;
    border-radius: 10px;
    padding: 10px 17px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #123a52;
    border: 1px solid #36bada;
}

QPushButton:pressed {
    background-color: #0a2538;
}

QPushButton:disabled {
    background-color: #0a1724;
    color: #456275;
    border: 1px solid #142d3f;
}

QPushButton#primaryGold {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff9d24,
        stop:1 #ffc64b
    );
    color: #18202a;
    border: 1px solid #ffd064;
    font-weight: 800;
}

QPushButton#primaryGold:hover {
    background-color: #ffd166;
    border: 1px solid #ffe39c;
}

QPushButton#secondary {
    background-color: #0d2133;
    color: #cfe8f5;
    border: 1px solid #24465d;
}

QPushButton#secondary:hover {
    background-color: #123149;
    color: #ffffff;
    border: 1px solid #2e7795;
}

QPushButton#nav {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 11px 13px;
    text-align: left;
    color: #8fb0c5;
}

QPushButton#nav:hover {
    background-color: #0e273b;
    border: 1px solid #173c54;
    color: #eaf9ff;
}

QPushButton#navActive {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #0d3345,
        stop:1 #10243a
    );
    border: 1px solid #1f7891;
    border-radius: 10px;
    padding: 11px 13px;
    text-align: left;
    color: #8eeaff;
    font-weight: 700;
}

QCheckBox {
    color: #a9c4d5;
    spacing: 8px;
}

QCheckBox:hover {
    color: #e8f8ff;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QListWidget {
    background-color: #081522;
    border: 1px solid #17344a;
    border-radius: 13px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    background-color: #0d1d2d;
    color: #dcebf5;
    border: 1px solid #1a3b51;
    border-radius: 11px;
    padding: 14px;
    margin: 5px;
}

QListWidget::item:hover {
    background-color: #11273a;
    border: 1px solid #2a6885;
}

QListWidget::item:selected {
    background-color: #123349;
    color: #ffffff;
    border: 1px solid #3bdcff;
}

QTextEdit {
    background-color: #081522;
    color: #e8f4fb;
    border: 1px solid #17344a;
    border-radius: 13px;
    padding: 16px;
}

QProgressBar {
    background-color: #0a1928;
    color: #dff8ff;
    border: 1px solid #23455b;
    border-radius: 8px;
    min-height: 16px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #20c6d9,
        stop:1 #ffb52e
    );
    border-radius: 7px;
}

QSplitter::handle {
    background-color: #153246;
    width: 2px;
}

QScrollBar:vertical {
    background: #07111f;
    width: 10px;
    margin: 3px;
}

QScrollBar::handle:vertical {
    background: #1c4a62;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: #2a7896;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class WyrmMangoWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.resize(1460, 900)
        self.setMinimumSize(1120, 720)

        if BRAND_ICON.exists():
            self.setWindowIcon(QIcon(str(BRAND_ICON)))

        db_override = os.environ.get("WYRMMANGO_DB")
        self.db_path = (
            Path(db_override)
            if db_override
            else Path(DEFAULT_DB)
        )
        self.read_only_database = (
            os.environ.get(
                "WYRMMANGO_READ_ONLY",
                "",
            ).strip()
            == "1"
        )
        self.results = []
        self.total_results = 0
        self.search_offset = 0

        self.import_process = None
        self.selected_export = None

        root = QWidget()
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = self.build_sidebar()

        self.pages = QStackedWidget()
        self.search_page = self.build_search_page()
        self.import_page = self.build_import_page()

        self.pages.addWidget(self.search_page)
        self.pages.addWidget(self.import_page)

        outer.addWidget(self.sidebar)
        outer.addWidget(self.pages, 1)

        self.show_search_page()
        self.refresh_stats()
        self.refresh_account_filter()
        self.refresh_email_account_inventory()
        self.update_source_filter_state()


    def brand_pixmap(self, size):

        if not BRAND_ICON.exists():
            return QPixmap()

        pixmap = QPixmap(str(BRAND_ICON))

        if pixmap.isNull():
            return QPixmap()

        return pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


    def make_stat_card(self, number_label, caption):

        card = QFrame()
        card.setObjectName("statCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 9)
        card_layout.setSpacing(1)

        number_label.setObjectName("statNumber")

        label = QLabel(caption)
        label.setObjectName("statLabel")

        card_layout.addWidget(number_label)
        card_layout.addWidget(label)

        return card


    def source_display_name(self, source_type):

        normalized = (
            source_type or "chatgpt"
        ).strip().lower()

        if normalized == "chatgpt":
            return "ChatGPT"

        if normalized == "claude":
            return "Claude"

        if normalized == "gmail":
            return "Gmail"

        if not normalized:
            return "Unknown"

        return normalized.replace(
            "_",
            " ",
        ).title()



    def database_table_exists(
        self,
        db,
        table_name,
    ):

        row = db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table_name,),
        ).fetchone()

        return row is not None


    def database_column_exists(
        self,
        db,
        table_name,
        column_name,
    ):

        rows = db.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        return any(
            row[1] == column_name
            for row in rows
        )


    def gmail_schema_available(
        self,
        db,
    ):

        return all(
            self.database_table_exists(
                db,
                table_name,
            )
            for table_name in (
                "email_occurrences",
                "email_message_variants",
                "email_attachments",
            )
        )


    def refresh_account_filter(self):

        if not hasattr(self, "account_filter_menu"):
            return

        previous = set(self.selected_gmail_accounts())
        accounts = []

        try:
            db = self.connect_database()

            if (
                self.database_column_exists(db, "conversations", "source_account")
                and self.database_column_exists(db, "conversations", "source_type")
            ):
                rows = db.execute(
                    """
                    SELECT source_account
                    FROM conversations
                    WHERE LOWER(COALESCE(source_type, '')) = 'gmail'
                      AND source_account IS NOT NULL
                      AND TRIM(source_account) <> ''
                    GROUP BY source_account
                    ORDER BY LOWER(source_account)
                    """
                ).fetchall()

                accounts = [
                    str(row[0]).strip()
                    for row in rows
                    if str(row[0] or "").strip()
                ]

            db.close()

        except Exception:
            accounts = []

        self.gmail_accounts = accounts
        self.account_filter_menu.clear()

        all_action = QAction("All Gmail accounts", self.account_filter_menu)
        all_action.setCheckable(True)
        all_action.setData("")
        self.account_filter_menu.addAction(all_action)

        selected_existing = [account for account in accounts if account in previous]
        all_action.setChecked(not selected_existing)
        all_action.toggled.connect(self.gmail_all_accounts_toggled)

        if accounts:
            self.account_filter_menu.addSeparator()

        for account in accounts:
            action = QAction(account, self.account_filter_menu)
            action.setCheckable(True)
            action.setData(account)
            action.setChecked(account in selected_existing)
            action.toggled.connect(
                lambda checked, value=account: self.gmail_account_action_toggled(value, checked)
            )
            self.account_filter_menu.addAction(action)

        self.update_account_filter_button()
        self.refresh_email_account_inventory()
        self.update_source_filter_state()


    def update_source_filter_state(self):

        if not hasattr(self, "source_filter"):
            return

        if not hasattr(self, "account_filter"):
            return

        is_gmail = self.source_filter.currentText().strip().lower() == "gmail"
        accounts = getattr(self, "gmail_accounts", [])

        self.account_filter.setEnabled(is_gmail and bool(accounts))

        if not is_gmail:
            self.set_all_gmail_accounts()

        self.update_account_filter_button()

    def selected_gmail_accounts(self):

        menu = getattr(self, "account_filter_menu", None)
        if menu is None:
            return []

        return [
            str(action.data())
            for action in menu.actions()
            if action.isCheckable() and action.data() and action.isChecked()
        ]


    def set_all_gmail_accounts(self):

        menu = getattr(self, "account_filter_menu", None)
        if menu is None:
            return

        actions = menu.actions()
        for action in actions:
            action.blockSignals(True)

        try:
            for action in actions:
                if not action.isCheckable():
                    continue
                action.setChecked(not bool(action.data()))
        finally:
            for action in actions:
                action.blockSignals(False)

        self.update_account_filter_button()


    def gmail_all_accounts_toggled(self, checked):

        if not checked:
            if not self.selected_gmail_accounts():
                self.set_all_gmail_accounts()
            return

        for action in self.account_filter_menu.actions():
            if action.isCheckable() and action.data():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)

        self.update_account_filter_button()


    def gmail_account_action_toggled(self, account, checked):

        all_action = next(
            (
                action
                for action in self.account_filter_menu.actions()
                if action.isCheckable() and not action.data()
            ),
            None,
        )

        if checked and all_action is not None:
            all_action.blockSignals(True)
            all_action.setChecked(False)
            all_action.blockSignals(False)

        if not self.selected_gmail_accounts() and all_action is not None:
            all_action.blockSignals(True)
            all_action.setChecked(True)
            all_action.blockSignals(False)

        self.update_account_filter_button()


    def update_account_filter_button(self):

        if not hasattr(self, "account_filter"):
            return

        selected = self.selected_gmail_accounts()

        if not selected:
            label = "All Gmail accounts"
            object_name = "gmailAccountFilterAll"
        elif len(selected) == 1:
            label = selected[0]
            object_name = "gmailAccountFilterActive"
        else:
            label = f"{len(selected)} Gmail accounts"
            object_name = "gmailAccountFilterActive"

        self.account_filter.setText(label)
        self.account_filter.setObjectName(object_name)
        self.account_filter.style().unpolish(self.account_filter)
        self.account_filter.style().polish(self.account_filter)


    def refresh_email_account_inventory(self):

        label = getattr(self, "gmail_account_inventory", None)
        if label is None:
            return

        account_data = {}

        try:
            db = self.connect_database()

            conversation_rows = db.execute(
                """
                SELECT source_account, COUNT(*)
                FROM conversations
                WHERE LOWER(COALESCE(source_type, '')) = 'gmail'
                  AND source_account IS NOT NULL
                  AND TRIM(source_account) <> ''
                GROUP BY source_account
                ORDER BY LOWER(source_account)
                """
            ).fetchall()

            message_rows = db.execute(
                """
                SELECT source_account, COUNT(*)
                FROM messages
                WHERE LOWER(COALESCE(source_type, '')) = 'gmail'
                  AND source_account IS NOT NULL
                  AND TRIM(source_account) <> ''
                GROUP BY source_account
                ORDER BY LOWER(source_account)
                """
            ).fetchall()

            db.close()

            for account, count in conversation_rows:
                value = str(account or "").strip()
                if value:
                    account_data.setdefault(value, {"threads": 0, "messages": 0})
                    account_data[value]["threads"] = int(count)

            for account, count in message_rows:
                value = str(account or "").strip()
                if value:
                    account_data.setdefault(value, {"threads": 0, "messages": 0})
                    account_data[value]["messages"] = int(count)

        except Exception:
            account_data = {}

        if not account_data:
            label.setText(
                "No Gmail accounts loaded yet.\n"
                "Use + Add Gmail Account to import a Takeout archive."
            )
            return

        lines = []
        for account in sorted(account_data, key=str.lower):
            counts = account_data[account]
            lines.append(
                f"{account}\n"
                f"  {counts['threads']:,} threads  •  {counts['messages']:,} messages"
            )

        label.setText("\n\n".join(lines))


    def open_add_gmail_account(self):

        self.show_import_page()
        self.import_source_selector.setCurrentText("Gmail")
        self.gmail_import_account.clear()
        self.selected_export = None
        self.export_path.clear()
        self.export_path.setPlaceholderText("No export selected")
        self.import_status.setText(
            "Enter the Gmail account address, then browse to that account's Takeout ZIP or MBOX."
        )
        self.gmail_import_account.setFocus()


    def decode_json_list(
        self,
        value,
    ):

        if not value:
            return []

        try:

            result = json.loads(value)

        except Exception:

            return []

        if isinstance(result, list):
            return result

        return []


    def address_json_text(
        self,
        value,
    ):

        addresses = self.decode_json_list(
            value
        )

        output = []

        for item in addresses:

            if not isinstance(
                item,
                dict,
            ):
                continue

            name = (
                str(
                    item.get(
                        "name",
                        "",
                    )
                )
                .strip()
            )

            address = (
                str(
                    item.get(
                        "address",
                        "",
                    )
                )
                .strip()
            )

            if name and address:

                output.append(
                    f"{name} <{address}>"
                )

            elif address:

                output.append(
                    address
                )

            elif name:

                output.append(
                    name
                )

        return ", ".join(
            output
        )


    def gmail_message_details(
        self,
        message_rowid,
    ):

        try:

            db = self.connect_database()

            if not self.gmail_schema_available(
                db
            ):

                db.close()
                return None

            row = db.execute(
                """
                SELECT
                    o.occurrence_id,
                    o.source_account,
                    o.source_archive,
                    o.source_file,
                    o.source_ordinal,
                    o.gm_thrid,
                    o.labels_json,
                    o.direction,
                    o.gmail_spam,
                    o.gmail_trash,
                    o.policy_action,
                    o.import_status,
                    v.subject,
                    v.from_raw,
                    v.to_json,
                    v.cc_json,
                    v.bcc_json,
                    v.reply_to_raw,
                    v.raw_date,
                    v.parsed_time_utc,
                    (
                        SELECT COUNT(*)
                        FROM email_attachments AS a
                        WHERE a.occurrence_id =
                              o.occurrence_id
                    ) AS attachment_count

                FROM email_occurrences AS o

                LEFT JOIN email_message_variants AS v
                  ON v.canonical_id =
                     o.canonical_id
                 AND v.content_sha256 =
                     o.content_sha256

                WHERE o.message_rowid = ?

                LIMIT 1
                """,
                (message_rowid,),
            ).fetchone()

            db.close()

        except Exception:

            return None

        if row is None:
            return None

        labels = self.decode_json_list(
            row["labels_json"]
        )

        return {
            "occurrence_id":
                row["occurrence_id"],
            "source_account":
                row["source_account"],
            "source_archive":
                row["source_archive"],
            "source_file":
                row["source_file"],
            "source_ordinal":
                row["source_ordinal"],
            "gm_thrid":
                row["gm_thrid"],
            "labels":
                labels,
            "direction":
                row["direction"],
            "gmail_spam":
                bool(row["gmail_spam"]),
            "gmail_trash":
                bool(row["gmail_trash"]),
            "policy_action":
                row["policy_action"],
            "import_status":
                row["import_status"],
            "subject":
                row["subject"],
            "from_raw":
                row["from_raw"],
            "to_text":
                self.address_json_text(
                    row["to_json"]
                ),
            "cc_text":
                self.address_json_text(
                    row["cc_json"]
                ),
            "bcc_text":
                self.address_json_text(
                    row["bcc_json"]
                ),
            "reply_to_raw":
                row["reply_to_raw"],
            "raw_date":
                row["raw_date"],
            "parsed_time_utc":
                row["parsed_time_utc"],
            "attachment_count":
                int(
                    row["attachment_count"]
                    or 0
                ),
        }


    def gmail_message_details_bulk(
        self,
        message_rowids,
    ):

        unique_ids = []

        seen = set()

        for value in message_rowids:

            try:
                rowid = int(value)
            except Exception:
                continue

            if rowid in seen:
                continue

            seen.add(rowid)
            unique_ids.append(rowid)

        if not unique_ids:
            return {}

        try:

            db = self.connect_database()

            if not self.gmail_schema_available(
                db
            ):

                db.close()
                return {}

            result = {}

            chunk_size = 400

            for start in range(
                0,
                len(unique_ids),
                chunk_size,
            ):

                chunk = unique_ids[
                    start:start + chunk_size
                ]

                placeholders = ",".join(
                    "?"
                    for _ in chunk
                )

                rows = db.execute(
                    f"""
                    SELECT
                        o.message_rowid,
                        o.occurrence_id,
                        o.source_account,
                        o.source_archive,
                        o.source_file,
                        o.source_ordinal,
                        o.gm_thrid,
                        o.labels_json,
                        o.direction,
                        o.gmail_spam,
                        o.gmail_trash,
                        o.policy_action,
                        o.import_status,
                        v.subject,
                        v.from_raw,
                        v.to_json,
                        v.cc_json,
                        v.bcc_json,
                        v.reply_to_raw,
                        v.raw_date,
                        v.parsed_time_utc,
                        COUNT(
                            a.attachment_id
                        ) AS attachment_count

                    FROM email_occurrences AS o

                    LEFT JOIN email_message_variants AS v
                      ON v.canonical_id =
                         o.canonical_id
                     AND v.content_sha256 =
                         o.content_sha256

                    LEFT JOIN email_attachments AS a
                      ON a.occurrence_id =
                         o.occurrence_id

                    WHERE o.message_rowid IN (
                        {placeholders}
                    )

                    GROUP BY
                        o.message_rowid,
                        o.occurrence_id,
                        o.source_account,
                        o.source_archive,
                        o.source_file,
                        o.source_ordinal,
                        o.gm_thrid,
                        o.labels_json,
                        o.direction,
                        o.gmail_spam,
                        o.gmail_trash,
                        o.policy_action,
                        o.import_status,
                        v.subject,
                        v.from_raw,
                        v.to_json,
                        v.cc_json,
                        v.bcc_json,
                        v.reply_to_raw,
                        v.raw_date,
                        v.parsed_time_utc
                    """,
                    chunk,
                ).fetchall()

                for row in rows:

                    result[
                        int(
                            row[
                                "message_rowid"
                            ]
                        )
                    ] = {
                        "occurrence_id":
                            row["occurrence_id"],
                        "source_account":
                            row["source_account"],
                        "source_archive":
                            row["source_archive"],
                        "source_file":
                            row["source_file"],
                        "source_ordinal":
                            row["source_ordinal"],
                        "gm_thrid":
                            row["gm_thrid"],
                        "labels":
                            self.decode_json_list(
                                row["labels_json"]
                            ),
                        "direction":
                            row["direction"],
                        "gmail_spam":
                            bool(
                                row[
                                    "gmail_spam"
                                ]
                            ),
                        "gmail_trash":
                            bool(
                                row[
                                    "gmail_trash"
                                ]
                            ),
                        "policy_action":
                            row["policy_action"],
                        "import_status":
                            row["import_status"],
                        "subject":
                            row["subject"],
                        "from_raw":
                            row["from_raw"],
                        "to_text":
                            self.address_json_text(
                                row["to_json"]
                            ),
                        "cc_text":
                            self.address_json_text(
                                row["cc_json"]
                            ),
                        "bcc_text":
                            self.address_json_text(
                                row["bcc_json"]
                            ),
                        "reply_to_raw":
                            row["reply_to_raw"],
                        "raw_date":
                            row["raw_date"],
                        "parsed_time_utc":
                            row[
                                "parsed_time_utc"
                            ],
                        "attachment_count":
                            int(
                                row[
                                    "attachment_count"
                                ]
                                or 0
                            ),
                    }

            db.close()
            return result

        except Exception:

            try:
                db.close()
            except Exception:
                pass

            return {}


    def update_action_state(self):

        has_results = bool(self.results)
        has_selection = self.result_list.currentRow() >= 0
        has_matches = self.total_results > 0

        self.export_results_button.setEnabled(has_results)
        self.export_all_results_button.setEnabled(has_matches)
        self.copy_button.setEnabled(has_selection)
        self.conversation_button.setEnabled(has_selection)
        self.export_conversation_button.setEnabled(has_selection)

        page_size = int(
            self.limit_filter.currentText()
        )

        self.previous_page_button.setText(
            f"Previous {page_size}"
        )
        self.next_page_button.setText(
            f"Next {page_size}"
        )

        self.previous_page_button.setEnabled(
            has_matches
            and self.search_offset > 0
        )

        self.next_page_button.setEnabled(
            has_matches
            and (
                self.search_offset
                + len(self.results)
                < self.total_results
            )
        )

    # ---------------------------------------------------------
    # SIDEBAR
    # ---------------------------------------------------------

    def build_sidebar(self):

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(11)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(128)

        logo_pixmap = self.brand_pixmap(122)

        if not logo_pixmap.isNull():
            logo.setPixmap(logo_pixmap)

            glow = QGraphicsDropShadowEffect(logo)
            glow.setBlurRadius(34)
            glow.setOffset(0, 0)
            glow.setColor(QColor(42, 211, 255, 105))
            logo.setGraphicsEffect(glow)
        else:
            logo.setText("◐")
            logo.setStyleSheet(
                "font-size:72px; color:#54ddff;"
            )

        brand = QLabel("WyrmMango")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel(
            "Dig deep. Find the thread.\n"
            "Private. Local. Yours."
        )
        tagline.setObjectName("tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(logo)
        layout.addWidget(brand)
        layout.addWidget(tagline)

        layout.addSpacing(10)

        nav_label = QLabel("NAVIGATION")
        nav_label.setObjectName("section")
        layout.addWidget(nav_label)

        self.search_nav = QPushButton("⌕   Search History")
        self.search_nav.clicked.connect(
            self.show_search_page
        )

        self.import_nav = QPushButton(
            "↓   Import / Update"
        )
        self.import_nav.clicked.connect(
            self.show_import_page
        )

        layout.addWidget(self.search_nav)
        layout.addWidget(self.import_nav)

        layout.addSpacing(10)

        section = QLabel("YOUR HISTORY")
        section.setObjectName("section")
        layout.addWidget(section)

        self.conversation_number = QLabel("—")
        self.message_number = QLabel("—")
        self.searchable_number = QLabel("—")

        layout.addWidget(
            self.make_stat_card(
                self.conversation_number,
                "CONVERSATIONS",
            )
        )

        layout.addWidget(
            self.make_stat_card(
                self.message_number,
                "MESSAGE NODES",
            )
        )

        layout.addWidget(
            self.make_stat_card(
                self.searchable_number,
                "SEARCHABLE MESSAGES",
            )
        )

        layout.addStretch()

        privacy = QLabel(
            "●  LOCAL • PRIVATE\n\n"
            "Your archive, searches and exports "
            "stay on this computer."
        )
        privacy.setWordWrap(True)
        privacy.setObjectName("privacy")

        version = QLabel(
            f"WyrmMango {APP_VERSION}"
        )
        version.setObjectName("version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(privacy)
        layout.addWidget(version)

        return sidebar

    def show_search_page(self):

        self.pages.setCurrentWidget(
            self.search_page
        )

        self.search_nav.setObjectName(
            "navActive"
        )

        self.import_nav.setObjectName(
            "nav"
        )

        self.refresh_nav_styles()

    def show_import_page(self):

        self.pages.setCurrentWidget(
            self.import_page
        )

        self.search_nav.setObjectName(
            "nav"
        )

        self.import_nav.setObjectName(
            "navActive"
        )

        self.refresh_email_account_inventory()

        self.refresh_nav_styles()

    def refresh_nav_styles(self):

        self.search_nav.style().unpolish(
            self.search_nav
        )
        self.search_nav.style().polish(
            self.search_nav
        )

        self.import_nav.style().unpolish(
            self.import_nav
        )
        self.import_nav.style().polish(
            self.import_nav
        )

    # ---------------------------------------------------------
    # SEARCH PAGE
    # ---------------------------------------------------------

    def build_search_page(self):

        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(13)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 19)
        hero_layout.setSpacing(7)

        eyebrow = QLabel("MOONLIT LOCAL RETRIEVAL")
        eyebrow.setObjectName("eyebrow")

        heading = QLabel(
            "Dig through your AI history"
        )
        heading.setObjectName("pageTitle")

        subtitle = QLabel(
            "Find projects, ideas, code and forgotten threads "
            "across your local AI history."
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setWordWrap(True)

        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(heading)
        hero_layout.addWidget(subtitle)
        hero_layout.addSpacing(5)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setMinimumHeight(46)
        self.search_box.setPlaceholderText(
            "What are you trying to find?  projects, ideas, recipes, old conversations..."
        )
        self.search_box.setToolTip(
            "Search the full text of your locally indexed conversation history."
        )
        self.search_box.returnPressed.connect(
            self.begin_search
        )

        self.search_button = QPushButton("Search the Deep")
        self.search_button.setObjectName("primaryGold")
        self.search_button.setMinimumWidth(150)
        self.search_button.setMinimumHeight(46)
        self.search_button.clicked.connect(
            self.begin_search
        )

        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.search_button)

        hero_layout.addLayout(search_row)
        layout.addWidget(hero)

        filter_card = QFrame()
        filter_card.setObjectName("filterCard")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 13, 16, 13)
        filter_layout.setSpacing(9)

        filter_top = QHBoxLayout()
        filter_top.setSpacing(10)

        self.source_filter = QComboBox()
        self.source_filter.addItems(
            [
                "All sources",
                "ChatGPT",
                "Claude",
                "Gmail",
            ]
        )
        self.source_filter.setMinimumWidth(120)
        self.source_filter.setMinimumHeight(40)
        self.source_filter.setToolTip(
            "Limit matches to one archive source."
        )

        self.account_filter = QPushButton(
            "All Gmail accounts"
        )
        self.account_filter.setObjectName(
            "gmailAccountFilterAll"
        )
        self.account_filter.setMinimumWidth(190)
        self.account_filter.setMinimumHeight(40)
        self.account_filter.setEnabled(False)
        self.account_filter.setToolTip(
            "Select all Gmail accounts or any combination of imported Gmail accounts."
        )

        self.account_filter_menu = QMenu(
            self.account_filter
        )
        self.account_filter.setMenu(
            self.account_filter_menu
        )

        self.source_filter.currentTextChanged.connect(
            self.update_source_filter_state
        )

        self.role_filter = QComboBox()
        self.role_filter.addItems(
            [
                "All roles",
                "user",
                "assistant",
                "system",
                "tool",
                "email",
            ]
        )
        self.role_filter.setMinimumWidth(120)
        self.role_filter.setMinimumHeight(40)
        self.role_filter.setToolTip("Limit matches to one message role.")

        self.title_filter = QLineEdit()
        self.title_filter.setPlaceholderText(
            "Conversation title contains..."
        )
        self.title_filter.setMinimumHeight(40)
        self.title_filter.setToolTip(
            "Optional title filter; search still runs against message text."
        )

        show_label = QLabel("Show")
        show_label.setObjectName("tagline")

        self.limit_filter = QComboBox()
        self.limit_filter.addItems(
            ["10", "25", "50", "100", "250"]
        )
        self.limit_filter.setCurrentText("50")
        self.limit_filter.setMinimumWidth(90)
        self.limit_filter.setMinimumHeight(40)
        self.limit_filter.setToolTip("Results shown per page.")
        self.limit_filter.currentTextChanged.connect(
            self.page_size_changed
        )

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("secondary")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.clicked.connect(
            self.clear_search
        )

        filter_top.addWidget(self.source_filter)
        filter_top.addWidget(self.account_filter)
        filter_top.addWidget(self.role_filter)
        filter_top.addWidget(self.title_filter, 1)
        filter_top.addWidget(show_label)
        filter_top.addWidget(self.limit_filter)
        filter_top.addWidget(self.clear_button)

        filter_bottom = QHBoxLayout()
        filter_bottom.setSpacing(9)

        self.after_enabled = QCheckBox("After")

        self.after_date = QDateEdit()
        self.after_date.setCalendarPopup(True)
        self.after_date.setDisplayFormat("yyyy-MM-dd")
        self.after_date.setDate(
            QDate.currentDate().addYears(-1)
        )
        self.after_date.setEnabled(False)
        self.after_date.setMinimumWidth(122)
        self.after_date.setMinimumHeight(40)
        self.after_enabled.toggled.connect(
            self.after_date.setEnabled
        )

        self.before_enabled = QCheckBox("Before")

        self.before_date = QDateEdit()
        self.before_date.setCalendarPopup(True)
        self.before_date.setDisplayFormat("yyyy-MM-dd")
        self.before_date.setDate(QDate.currentDate())
        self.before_date.setEnabled(False)
        self.before_date.setMinimumWidth(122)
        self.before_date.setMinimumHeight(40)
        self.before_enabled.toggled.connect(
            self.before_date.setEnabled
        )

        self.exact_phrase = QCheckBox("Exact phrase")
        self.exact_phrase.setToolTip(
            "Require the entered words to appear together in that order."
        )

        filter_bottom.addWidget(self.after_enabled)
        filter_bottom.addWidget(self.after_date)
        filter_bottom.addSpacing(8)
        filter_bottom.addWidget(self.before_enabled)
        filter_bottom.addWidget(self.before_date)
        filter_bottom.addSpacing(12)
        filter_bottom.addWidget(self.exact_phrase)
        filter_bottom.addStretch()

        filter_layout.addLayout(filter_top)
        filter_layout.addLayout(filter_bottom)
        layout.addWidget(filter_card)

        results_panel = QFrame()
        results_panel.setObjectName("panelCard")
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(11, 11, 11, 11)
        results_layout.setSpacing(8)

        results_header = QHBoxLayout()

        results_title = QLabel("MATCHES")
        results_title.setObjectName("paneTitle")

        self.result_count = QLabel(
            "Enter a search above."
        )
        self.result_count.setObjectName(
            "resultCount"
        )
        self.result_count.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        results_header.addWidget(results_title)
        results_header.addStretch()
        results_header.addWidget(self.result_count)
        results_layout.addLayout(results_header)

        self.result_list = QListWidget()
        self.result_list.setSpacing(1)
        self.result_list.itemSelectionChanged.connect(
            self.show_selected_message
        )

        results_layout.addWidget(self.result_list, 1)

        page_row = QHBoxLayout()
        page_row.setSpacing(8)

        self.previous_page_button = QPushButton(
            "Previous 50"
        )
        self.previous_page_button.setObjectName(
            "secondary"
        )
        self.previous_page_button.clicked.connect(
            self.previous_search_page
        )

        self.page_status = QLabel(
            "No results"
        )
        self.page_status.setObjectName(
            "tagline"
        )
        self.page_status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.next_page_button = QPushButton(
            "Next 50"
        )
        self.next_page_button.setObjectName(
            "secondary"
        )
        self.next_page_button.clicked.connect(
            self.next_search_page
        )

        page_row.addWidget(
            self.previous_page_button
        )
        page_row.addWidget(
            self.page_status,
            1,
        )
        page_row.addWidget(
            self.next_page_button
        )

        results_layout.addLayout(
            page_row
        )

        reader_panel = QFrame()
        reader_panel.setObjectName("panelCard")
        reader_layout = QVBoxLayout(reader_panel)
        reader_layout.setContentsMargins(11, 11, 11, 11)
        reader_layout.setSpacing(8)

        reader_header = QHBoxLayout()
        reader_title = QLabel("READER")
        reader_title.setObjectName("paneTitle")
        reader_hint = QLabel("Matched message or full conversation")
        reader_hint.setObjectName("tagline")
        reader_hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        reader_header.addWidget(reader_title)
        reader_header.addStretch()
        reader_header.addWidget(reader_hint)
        reader_layout.addLayout(reader_header)

        self.message_view = QTextEdit()
        self.message_view.setReadOnly(True)
        self.message_view.setPlaceholderText(
            "Select a result and WyrmMango will surface the buried thread here."
        )
        reader_layout.addWidget(self.message_view, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(results_panel)
        splitter.addWidget(reader_panel)
        splitter.setSizes([500, 760])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setObjectName("secondary")
        self.copy_button.clicked.connect(
            self.copy_message
        )

        self.conversation_button = QPushButton(
            "Open Full Conversation"
        )
        self.conversation_button.clicked.connect(
            self.show_conversation
        )

        self.export_results_button = QPushButton(
            "Export This Page"
        )
        self.export_results_button.setObjectName(
            "secondary"
        )
        self.export_results_button.clicked.connect(
            self.export_search_results
        )

        self.export_all_results_button = QPushButton(
            "Export All Matches"
        )
        self.export_all_results_button.setObjectName(
            "secondary"
        )
        self.export_all_results_button.clicked.connect(
            self.export_all_search_results
        )

        self.export_conversation_button = QPushButton(
            "Export Conversation"
        )
        self.export_conversation_button.setObjectName(
            "secondary"
        )
        self.export_conversation_button.clicked.connect(
            self.export_conversation
        )

        bottom.addWidget(self.copy_button)
        bottom.addWidget(self.conversation_button)
        bottom.addStretch()
        bottom.addWidget(self.export_results_button)
        bottom.addWidget(self.export_all_results_button)
        bottom.addWidget(self.export_conversation_button)

        layout.addLayout(bottom)

        self.update_action_state()

        return page

    # ---------------------------------------------------------
    # IMPORT PAGE
    # ---------------------------------------------------------

    def build_import_page(self):

        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(18)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(6)

        eyebrow = QLabel("LOCAL INGEST • NO CLOUD UPLOAD")
        eyebrow.setObjectName("eyebrow")

        heading = QLabel("Bring your history home")
        heading.setObjectName("pageTitle")

        subtitle = QLabel(
            "Bring ChatGPT, Claude, or Gmail history into one "
            "private local archive. Choose the source below, "
            "then select its export file."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("heroSubtitle")

        hero_text.addWidget(eyebrow)
        hero_text.addWidget(heading)
        hero_text.addWidget(subtitle)

        hero_layout.addLayout(hero_text, 1)

        mini_logo = QLabel()
        mini_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mini_logo.setFixedSize(104, 104)

        pixmap = self.brand_pixmap(96)
        if not pixmap.isNull():
            mini_logo.setPixmap(pixmap)

        hero_layout.addWidget(mini_logo)
        layout.addWidget(hero)

        card = QFrame()
        card.setObjectName("importCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        select_title = QLabel(
            "1  •  SELECT YOUR SOURCE AND EXPORT"
        )
        select_title.setObjectName("paneTitle")

        self.import_source_help = QLabel(
            "Choose a source, then select the matching export. "
            "The source archive itself is never modified."
        )
        self.import_source_help.setObjectName("tagline")
        self.import_source_help.setWordWrap(True)

        card_layout.addWidget(select_title)
        card_layout.addWidget(
            self.import_source_help
        )

        source_row = QHBoxLayout()
        source_row.setSpacing(9)

        source_label = QLabel("Source")
        source_label.setObjectName("tagline")
        source_label.setMinimumWidth(110)

        self.import_source_selector = QComboBox()
        self.import_source_selector.addItems(
            [
                "ChatGPT",
                "Claude",
                "Gmail",
            ]
        )
        self.import_source_selector.setMinimumWidth(180)
        self.import_source_selector.setMinimumHeight(40)

        source_row.addWidget(source_label)
        source_row.addWidget(
            self.import_source_selector,
            1,
        )
        card_layout.addLayout(source_row)

        gmail_row = QHBoxLayout()
        gmail_row.setSpacing(9)

        gmail_label = QLabel("Gmail account")
        gmail_label.setObjectName("tagline")
        gmail_label.setMinimumWidth(110)

        self.gmail_import_account = QLineEdit()
        self.gmail_import_account.setPlaceholderText(
            "Required for Gmail Takeout provenance"
        )
        self.gmail_import_account.setMinimumHeight(40)
        self.gmail_import_account.setEnabled(False)

        gmail_row.addWidget(gmail_label)
        gmail_row.addWidget(
            self.gmail_import_account,
            1,
        )
        card_layout.addLayout(gmail_row)

        path_row = QHBoxLayout()
        path_row.setSpacing(9)

        self.export_path = QLineEdit()
        self.export_path.setReadOnly(True)
        self.export_path.setMinimumHeight(40)
        self.export_path.setPlaceholderText(
            "No export selected"
        )

        browse_button = QPushButton("Browse…")
        browse_button.setObjectName("secondary")
        browse_button.setMinimumHeight(40)
        browse_button.clicked.connect(
            self.browse_export
        )

        path_row.addWidget(
            self.export_path,
            1,
        )
        path_row.addWidget(browse_button)
        card_layout.addLayout(path_row)

        self.import_button = QPushButton(
            "Import / Update Local Archive"
        )
        self.import_button.setObjectName("primaryGold")
        self.import_button.setMinimumHeight(43)
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(
            self.start_import
        )

        card_layout.addWidget(
            self.import_button
        )

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        card_layout.addWidget(
            self.import_progress
        )

        self.import_status = QLabel("Ready.")
        self.import_status.setObjectName("tagline")
        card_layout.addWidget(
            self.import_status
        )

        self.import_source_selector.currentTextChanged.connect(
            self.update_import_source_state
        )
        self.gmail_import_account.textChanged.connect(
            self.update_import_button_state
        )
        self.update_import_source_state()

        layout.addWidget(card)

        accounts_panel = QFrame()
        accounts_panel.setObjectName("panelCard")

        accounts_layout = QVBoxLayout(accounts_panel)
        accounts_layout.setContentsMargins(16, 13, 16, 13)
        accounts_layout.setSpacing(8)

        accounts_header = QHBoxLayout()
        accounts_title = QLabel("EMAIL ACCOUNTS")
        accounts_title.setObjectName("paneTitle")
        accounts_hint = QLabel("Gmail archives currently loaded")
        accounts_hint.setObjectName("tagline")

        self.add_gmail_account_button = QPushButton("+ Add Gmail Account")
        self.add_gmail_account_button.setObjectName("secondary")
        self.add_gmail_account_button.setMinimumHeight(40)
        self.add_gmail_account_button.clicked.connect(self.open_add_gmail_account)

        accounts_header.addWidget(accounts_title)
        accounts_header.addStretch()
        accounts_header.addWidget(accounts_hint)
        accounts_header.addSpacing(8)
        accounts_header.addWidget(self.add_gmail_account_button)
        accounts_layout.addLayout(accounts_header)

        self.gmail_account_inventory = QLabel("No Gmail accounts loaded yet.")
        self.gmail_account_inventory.setObjectName("tagline")
        self.gmail_account_inventory.setWordWrap(True)
        self.gmail_account_inventory.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        accounts_layout.addWidget(self.gmail_account_inventory)

        layout.addWidget(accounts_panel)

        log_panel = QFrame()
        log_panel.setObjectName("panelCard")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("IMPORT ACTIVITY")
        log_title.setObjectName("paneTitle")
        log_hint = QLabel(
            "Progress, counts and integrity checks"
        )
        log_hint.setObjectName("tagline")
        log_hint.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(log_hint)
        log_layout.addLayout(log_header)

        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        self.import_log.setPlaceholderText(
            "Import progress will appear here."
        )

        log_layout.addWidget(
            self.import_log,
            1,
        )
        layout.addWidget(
            log_panel,
            1,
        )

        note = QLabel(
            "●  PRIVACY BY DESIGN  —  WyrmMango reads the selected "
            "export locally. The source archive, SQLite database, "
            "searches and exports are not uploaded by this application."
        )
        note.setWordWrap(True)
        note.setObjectName("privacy")

        layout.addWidget(note)

        return page

    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------

    def connect_database(self):

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found:\n"
                f"{self.db_path}"
            )

        if self.read_only_database:

            database_uri = (
                "file:"
                + self.db_path
                .resolve()
                .as_posix()
                + "?mode=ro"
            )

            connection = sqlite3.connect(
                database_uri,
                uri=True,
            )

        else:

            connection = sqlite3.connect(
                self.db_path
            )

        connection.row_factory = (
            sqlite3.Row
        )

        return connection

    def refresh_stats(self):

        try:

            db = self.connect_database()

            conversations = db.execute(
                "SELECT COUNT(*) "
                "FROM conversations"
            ).fetchone()[0]

            messages = db.execute(
                "SELECT COUNT(*) "
                "FROM messages"
            ).fetchone()[0]

            searchable = db.execute(
                "SELECT COUNT(*) "
                "FROM messages_fts"
            ).fetchone()[0]

            db.close()

            self.conversation_number.setText(
                f"{conversations:,}"
            )

            self.message_number.setText(
                f"{messages:,}"
            )

            self.searchable_number.setText(
                f"{searchable:,}"
            )

        except Exception:

            self.conversation_number.setText(
                "—"
            )

            self.message_number.setText(
                "—"
            )

            self.searchable_number.setText(
                "—"
            )

    # ---------------------------------------------------------
    # SEARCH
    # ---------------------------------------------------------

    def make_fts_query(
        self,
        text,
        exact=False,
    ):

        text = text.strip()

        if exact:

            safe = text.replace(
                '"',
                '""',
            )

            return f'"{safe}"'

        words = [
            word.strip()
            for word in text.split()
            if word.strip()
        ]

        result = []

        for word in words:

            safe = word.replace(
                '"',
                '""',
            )

            result.append(
                f'"{safe}"'
            )

        return " AND ".join(
            result
        )

    def begin_search(
        self,
        checked=False,
    ):

        self.search_offset = 0
        self.run_search()


    def page_size_changed(
        self,
        value,
    ):

        self.search_offset = 0

        if self.search_box.text().strip():

            self.run_search()

        else:

            self.update_pagination_status()


    def previous_search_page(self):

        page_size = int(
            self.limit_filter.currentText()
        )

        self.search_offset = max(
            0,
            self.search_offset
            - page_size,
        )

        self.run_search()


    def next_search_page(self):

        page_size = int(
            self.limit_filter.currentText()
        )

        next_offset = (
            self.search_offset
            + page_size
        )

        if next_offset >= self.total_results:
            return

        self.search_offset = next_offset
        self.run_search()


    def update_pagination_status(self):

        page_size = int(
            self.limit_filter.currentText()
        )

        if self.total_results <= 0:

            self.page_status.setText(
                "No results"
            )

            self.previous_page_button.setText(
                f"Previous {page_size}"
            )

            self.next_page_button.setText(
                f"Next {page_size}"
            )

            return

        start_number = (
            self.search_offset
            + 1
        )

        end_number = min(
            self.search_offset
            + len(self.results),
            self.total_results,
        )

        total_pages = max(
            1,
            (
                self.total_results
                + page_size
                - 1
            )
            // page_size,
        )

        current_page = (
            self.search_offset
            // page_size
        ) + 1

        self.page_status.setText(
            f"{start_number:,}–{end_number:,} "
            f"of {self.total_results:,}  •  "
            f"Page {current_page:,} "
            f"of {total_pages:,}"
        )


    def build_search_sql(
        self,
        db,
        query,
        count_only=False,
    ):

        has_message_account = (
            self.database_column_exists(
                db,
                "messages",
                "source_account",
            )
        )

        has_conversation_account = (
            self.database_column_exists(
                db,
                "conversations",
                "source_account",
            )
        )

        if (
            has_message_account
            and has_conversation_account
        ):

            account_expression = (
                "COALESCE("
                "m.source_account,"
                "c.source_account"
                ")"
            )

        elif has_message_account:

            account_expression = (
                "m.source_account"
            )

        elif has_conversation_account:

            account_expression = (
                "c.source_account"
            )

        else:

            account_expression = "NULL"

        if count_only:

            select_clause = (
                "COUNT(*) AS total_count"
            )

        else:

            select_clause = f"""
                m.id,
                m.conversation_id,
                c.title,
                COALESCE(
                    c.source_type,
                    'chatgpt'
                ) AS source_type,
                {account_expression}
                    AS source_account,
                m.role,
                m.author_name,
                m.model_slug,
                m.create_time,
                datetime(
                    m.create_time,
                    'unixepoch',
                    'localtime'
                ) AS local_time,
                m.content,
                bm25(messages_fts) AS rank
            """

        sql = f"""
        SELECT
            {select_clause}

        FROM messages_fts

        JOIN messages AS m
          ON m.id =
             messages_fts.message_rowid

        JOIN conversations AS c
          ON c.id =
             m.conversation_id

        WHERE messages_fts MATCH ?
        """

        params = [
            self.make_fts_query(
                query,
                exact=self.exact_phrase.isChecked(),
            )
        ]

        source_filter = (
            self.source_filter
            .currentText()
        )

        if source_filter != "All sources":

            sql += """
            AND LOWER(
                COALESCE(
                    c.source_type,
                    'chatgpt'
                )
            ) = LOWER(?)
            """

            params.append(
                source_filter
            )

        selected_accounts = (
            self.selected_gmail_accounts()
        )

        if (
            source_filter == "Gmail"
            and selected_accounts
        ):
            if account_expression == "NULL":
                sql += " AND 1 = 0 "
            else:
                placeholders = ", ".join(
                    "?"
                    for _ in selected_accounts
                )
                sql += f"""
                AND LOWER(
                    COALESCE(
                        {account_expression},
                        ''
                    )
                ) IN ({placeholders})
                """
                params.extend(
                    [account.lower() for account in selected_accounts]
                )

        role = (
            self.role_filter
            .currentText()
        )

        if role != "All roles":

            sql += """
            AND LOWER(
                COALESCE(m.role, '')
            ) = LOWER(?)
            """

            params.append(role)

        title = (
            self.title_filter
            .text()
            .strip()
        )

        if title:

            sql += """
            AND LOWER(
                COALESCE(c.title, '')
            ) LIKE LOWER(?)
            """

            params.append(
                f"%{title}%"
            )

        if self.after_enabled.isChecked():

            sql += """
            AND date(
                m.create_time,
                'unixepoch',
                'localtime'
            ) >= date(?)
            """

            params.append(
                self.after_date
                .date()
                .toString("yyyy-MM-dd")
            )

        if self.before_enabled.isChecked():

            sql += """
            AND date(
                m.create_time,
                'unixepoch',
                'localtime'
            ) <= date(?)
            """

            params.append(
                self.before_date
                .date()
                .toString("yyyy-MM-dd")
            )

        return sql, params


    def fetch_all_search_rows(self):

        query = (
            self.search_box
            .text()
            .strip()
        )

        if not query:
            return []

        db = self.connect_database()

        try:

            sql, params = (
                self.build_search_sql(
                    db,
                    query,
                    count_only=False,
                )
            )

            sql += """
            ORDER BY
                rank ASC,
                m.create_time DESC,
                m.id ASC
            """

            return list(
                db.execute(
                    sql,
                    params,
                ).fetchall()
            )

        finally:

            db.close()


    def run_search(self):

        query = (
            self.search_box
            .text()
            .strip()
        )

        if not query:
            return

        try:

            db = self.connect_database()

            count_sql, count_params = (
                self.build_search_sql(
                    db,
                    query,
                    count_only=True,
                )
            )

            self.total_results = int(
                db.execute(
                    count_sql,
                    count_params,
                ).fetchone()[0]
            )

            page_size = int(
                self.limit_filter
                .currentText()
            )

            if (
                self.total_results > 0
                and self.search_offset
                >= self.total_results
            ):

                self.search_offset = (
                    (
                        self.total_results
                        - 1
                    )
                    // page_size
                ) * page_size

            if self.total_results <= 0:

                self.search_offset = 0

            sql, params = (
                self.build_search_sql(
                    db,
                    query,
                    count_only=False,
                )
            )

            sql += """
            ORDER BY
                rank ASC,
                m.create_time DESC,
                m.id ASC

            LIMIT ?
            OFFSET ?
            """

            params.extend(
                [
                    page_size,
                    self.search_offset,
                ]
            )

            rows = db.execute(
                sql,
                params,
            ).fetchall()

            db.close()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Search Error",
                str(exc),
            )

            return

        self.results = list(rows)

        self.result_list.clear()
        self.message_view.clear()

        if self.total_results > 0:

            first_number = (
                self.search_offset
                + 1
            )

            last_number = min(
                self.search_offset
                + len(rows),
                self.total_results,
            )

            self.result_count.setText(
                f"Showing {first_number:,}–"
                f"{last_number:,} of "
                f"{self.total_results:,}  •  "
                f'"{query}"'
            )

        else:

            self.result_count.setText(
                f'0 matches  •  "{query}"'
            )

        for row in rows:

            title_text = (
                row["title"]
                or (
                    "Untitled Email Thread"
                    if (
                        row["source_type"]
                        or ""
                    ).lower() == "gmail"
                    else "Untitled Conversation"
                )
            )

            date_text = (
                row["local_time"]
                or "Unknown date"
            )

            role_text = (
                row["role"]
                or "unknown"
            ).capitalize()

            source_text = (
                self.source_display_name(
                    row["source_type"]
                )
            ).upper()

            author_text = (
                row["author_name"]
                or "Unknown sender"
            )

            preview = " ".join(
                (
                    row["content"]
                    or ""
                ).split()
            )

            if len(preview) > 190:

                preview = (
                    preview[:190]
                    .rstrip()
                    + "..."
                )

            if (
                row["source_type"]
                or ""
            ).lower() == "gmail":

                display = (
                    f"{title_text}\n"
                    f"{date_text}  •  "
                    f"{source_text}  •  "
                    f"{author_text}\n\n"
                    f"{preview}"
                )

            else:

                display = (
                    f"{title_text}\n"
                    f"{date_text}  •  "
                    f"{role_text}  •  "
                    f"{source_text}\n\n"
                    f"{preview}"
                )

            self.result_list.addItem(
                QListWidgetItem(
                    display
                )
            )

        self.update_pagination_status()
        self.update_action_state()

    def format_content_html(self, text):

        text = text or ""
        pieces = []
        position = 0

        code_pattern = re.compile(
            r"```(?:[^\\n`]*)\\n?(.*?)```",
            re.DOTALL,
        )

        for match in code_pattern.finditer(text):

            normal_text = text[
                position:match.start()
            ]

            if normal_text:

                escaped = html.escape(
                    normal_text
                ).replace(
                    "\\n",
                    "<br>"
                )

                pieces.append(
                    f"<div>{escaped}</div>"
                )

            code_text = html.escape(
                match.group(1).rstrip()
            )

            pieces.append(
                "<pre style=\""
                "background-color:#090d14;"
                "color:#dbe5f5;"
                "border:1px solid #2c3a50;"
                "padding:12px;"
                "font-family:Consolas;"
                "font-size:10pt;"
                "white-space:pre-wrap;"
                "\">"
                f"{code_text}"
                "</pre>"
            )

            position = match.end()

        remaining = text[position:]

        if remaining:

            escaped = html.escape(
                remaining
            ).replace(
                "\\n",
                "<br>"
            )

            pieces.append(
                f"<div>{escaped}</div>"
            )

        return "".join(pieces)


    def message_card_html(
        self,
        role,
        date,
        content,
        source_type,
        gmail_details=None,
    ):

        normalized_role = (
            role or "unknown"
        ).lower()

        normalized_source = (
            source_type or "chatgpt"
        ).strip().lower()

        if (
            normalized_source == "gmail"
            or normalized_role == "email"
        ):

            label = "GMAIL"
            background = "#13202b"
            border = "#6f501d"
            label_color = "#ffbd4a"

            left_width = "3%"
            right_width = "3%"

        elif normalized_role == "user":

            label = "YOU"
            background = "#2b2112"
            border = "#8d621d"
            label_color = "#ffbd4a"

            left_width = "16%"
            right_width = "0%"

        elif normalized_role == "assistant":

            if normalized_source == "claude":
                label = "CLAUDE"
            elif normalized_source == "chatgpt":
                label = "CHATGPT"
            else:
                label = "ASSISTANT"

            background = "#0b2632"
            border = "#1a6f86"
            label_color = "#5be3ff"

            left_width = "0%"
            right_width = "16%"

        elif normalized_role == "system":

            label = "SYSTEM"
            background = "#282316"
            border = "#725b26"
            label_color = "#ffd36a"

            left_width = "8%"
            right_width = "8%"

        elif normalized_role == "tool":

            label = "TOOL"
            background = "#21192c"
            border = "#604a78"
            label_color = "#d6b9ff"

            left_width = "8%"
            right_width = "8%"

        else:

            label = normalized_role.upper()
            background = "#0e1d2b"
            border = "#2c5368"
            label_color = "#a8cada"

            left_width = "8%"
            right_width = "8%"

        safe_date = html.escape(
            date or ""
        )

        body = self.format_content_html(
            content
        )

        gmail_meta = ""

        if (
            normalized_source == "gmail"
            and gmail_details
        ):

            meta_lines = []

            sender = (
                gmail_details.get(
                    "from_raw"
                )
                or ""
            )

            recipients = (
                gmail_details.get(
                    "to_text"
                )
                or ""
            )

            cc_text = (
                gmail_details.get(
                    "cc_text"
                )
                or ""
            )

            account = (
                gmail_details.get(
                    "source_account"
                )
                or ""
            )

            labels = (
                gmail_details.get(
                    "labels"
                )
                or []
            )

            attachment_count = int(
                gmail_details.get(
                    "attachment_count"
                )
                or 0
            )

            direction = (
                gmail_details.get(
                    "direction"
                )
                or ""
            )

            if sender:

                meta_lines.append(
                    "<b>From:</b> "
                    + html.escape(sender)
                )

            if recipients:

                meta_lines.append(
                    "<b>To:</b> "
                    + html.escape(recipients)
                )

            if cc_text:

                meta_lines.append(
                    "<b>Cc:</b> "
                    + html.escape(cc_text)
                )

            if account:

                meta_lines.append(
                    "<b>Account:</b> "
                    + html.escape(account)
                )

            if direction:

                meta_lines.append(
                    "<b>Direction:</b> "
                    + html.escape(
                        direction.capitalize()
                    )
                )

            if labels:

                meta_lines.append(
                    "<b>Labels:</b> "
                    + html.escape(
                        ", ".join(
                            str(label)
                            for label in labels
                        )
                    )
                )

            if attachment_count:

                meta_lines.append(
                    "<b>Attachments:</b> "
                    + str(attachment_count)
                )

            if meta_lines:

                gmail_meta = (
                    "<div style=\""
                    "color:#a8c3d3;"
                    "font-size:8.5pt;"
                    "line-height:1.5;"
                    "margin-bottom:12px;"
                    "\">"
                    + "<br>".join(
                        meta_lines
                    )
                    + "</div>"
                )

        return f"""
        <table width="100%"
               cellspacing="0"
               cellpadding="0"
               style="margin-top:12px;
                      margin-bottom:12px;">
            <tr>
                <td width="{left_width}"></td>

                <td style="
                    background-color:{background};
                    border:1px solid {border};
                    padding:15px;
                ">
                    <div style="
                        color:{label_color};
                        font-size:10pt;
                        font-weight:700;
                        margin-bottom:5px;
                    ">
                        {label}
                    </div>

                    <div style="
                        color:#7fa5bb;
                        font-size:8pt;
                        margin-bottom:12px;
                    ">
                        {safe_date}
                    </div>

                    {gmail_meta}

                    <div style="
                        color:#eef9ff;
                        font-size:10.5pt;
                        line-height:1.4;
                    ">
                        {body}
                    </div>
                </td>

                <td width="{right_width}"></td>
            </tr>
        </table>
        """


    def show_selected_message(self):

        selected = (
            self.result_list
            .currentRow()
        )

        self.update_action_state()

        if selected < 0:
            return

        row = self.results[
            selected
        ]

        source_type = (
            row["source_type"]
            or "chatgpt"
        )

        is_gmail = (
            source_type
            .strip()
            .lower()
            == "gmail"
        )

        title = (
            row["title"]
            or (
                "Untitled Email Thread"
                if is_gmail
                else "Untitled Conversation"
            )
        )

        safe_title = html.escape(
            title
        )

        date = (
            row["local_time"]
            or "Unknown date"
        )

        source_name = self.source_display_name(
            source_type
        )

        safe_source = html.escape(
            source_name
        )

        gmail_details = (
            self.gmail_message_details(
                row["id"]
            )
            if is_gmail
            else None
        )

        card = self.message_card_html(
            row["role"],
            date,
            row["content"] or "",
            source_type,
            gmail_details=gmail_details,
        )

        if is_gmail:

            account = (
                (
                    gmail_details
                    or {}
                ).get(
                    "source_account"
                )
                or row["source_account"]
                or "Unknown account"
            )

            thread_id = (
                (
                    gmail_details
                    or {}
                ).get(
                    "gm_thrid"
                )
                or ""
            )

            context = (
                "MATCHED EMAIL"
                " &nbsp; • &nbsp; "
                f"Source: {safe_source}"
                " &nbsp; • &nbsp; "
                f"Account: {html.escape(account)}"
            )

            if thread_id:

                context += (
                    " &nbsp; • &nbsp; "
                    "Thread: "
                    + html.escape(
                        str(thread_id)
                    )
                )

        else:

            model = (
                row["model_slug"]
                or "Unknown"
            )

            context = (
                "MATCHED MESSAGE"
                " &nbsp; • &nbsp; "
                f"Source: {safe_source}"
                " &nbsp; • &nbsp; "
                "Model: "
                + html.escape(model)
            )

        page = f"""
        <div style="
            font-family:'Segoe UI';
            color:#eef9ff;
        ">
            <div style="
                font-size:18pt;
                font-weight:700;
                color:#ffffff;
                margin-bottom:4px;
            ">
                {safe_title}
            </div>

            <div style="
                color:#7ea6bd;
                font-size:9pt;
                margin-bottom:18px;
            ">
                {context}
            </div>

            {card}
        </div>
        """

        self.message_view.setHtml(
            page
        )

        self.message_view.moveCursor(
            QTextCursor.MoveOperation.Start
        )


    def show_conversation(self):

        selected = (
            self.result_list
            .currentRow()
        )

        if selected < 0:
            return

        selected_row = self.results[
            selected
        ]

        conversation_id = (
            selected_row[
                "conversation_id"
            ]
        )

        source_type = (
            selected_row["source_type"]
            or "chatgpt"
        )

        is_gmail = (
            source_type
            .strip()
            .lower()
            == "gmail"
        )

        title = (
            selected_row["title"]
            or (
                "Untitled Email Thread"
                if is_gmail
                else "Untitled Conversation"
            )
        )

        source_name = self.source_display_name(
            source_type
        )

        try:

            db = self.connect_database()

            messages = db.execute(
                """
                SELECT
                    id,
                    role,
                    author_name,
                    model_slug,
                    datetime(
                        create_time,
                        'unixepoch',
                        'localtime'
                    ) AS local_time,
                    content

                FROM messages

                WHERE conversation_id = ?
                  AND content IS NOT NULL
                  AND TRIM(content) <> ''

                ORDER BY
                    CASE
                        WHEN create_time IS NULL
                        THEN 1
                        ELSE 0
                    END,
                    create_time ASC,
                    id ASC
                """,
                (conversation_id,),
            ).fetchall()

            db.close()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Conversation Error",
                str(exc),
            )

            return

        cards = []

        for message in messages:

            gmail_details = (
                self.gmail_message_details(
                    message["id"]
                )
                if is_gmail
                else None
            )

            cards.append(
                self.message_card_html(
                    message["role"],
                    message["local_time"],
                    message["content"] or "",
                    source_type,
                    gmail_details=gmail_details,
                )
            )

        safe_title = html.escape(
            title
        )

        if is_gmail:

            account = (
                selected_row[
                    "source_account"
                ]
                or "Unknown account"
            )

            context = (
                "FULL EMAIL THREAD"
                " &nbsp; • &nbsp; "
                f"Source: {html.escape(source_name)}"
                " &nbsp; • &nbsp; "
                f"Account: {html.escape(account)}"
                " &nbsp; • &nbsp; "
                f"{len(messages):,} messages"
            )

        else:

            context = (
                "FULL CONVERSATION"
                " &nbsp; • &nbsp; "
                f"Source: {html.escape(source_name)}"
                " &nbsp; • &nbsp; "
                f"{len(messages):,} messages"
            )

        page = f"""
        <div style="
            font-family:'Segoe UI';
            color:#eef9ff;
        ">
            <div style="
                font-size:19pt;
                font-weight:700;
                color:#ffffff;
                margin-bottom:5px;
            ">
                {safe_title}
            </div>

            <div style="
                color:#7ea6bd;
                font-size:9pt;
                margin-bottom:20px;
            ">
                {context}
            </div>

            {''.join(cards)}
        </div>
        """

        self.message_view.setHtml(
            page
        )

        self.message_view.moveCursor(
            QTextCursor.MoveOperation.Start
        )


    def copy_message(self):

        text = (
            self.message_view
            .toPlainText()
        )

        if text:

            QApplication.clipboard().setText(
                text
            )

    def clear_search(self):

        self.search_box.clear()
        self.title_filter.clear()

        self.source_filter.setCurrentIndex(
            0
        )

        self.set_all_gmail_accounts()

        self.role_filter.setCurrentIndex(
            0
        )

        self.after_enabled.setChecked(
            False
        )

        self.before_enabled.setChecked(
            False
        )

        self.exact_phrase.setChecked(False)

        self.result_list.clear()
        self.message_view.clear()

        self.results = []
        self.total_results = 0
        self.search_offset = 0

        self.result_count.setText(
            "Enter a search above."
        )

        self.update_pagination_status()
        self.update_action_state()

    # ---------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------

    def safe_filename(self, text):

        text = text or "conversation"

        cleaned = re.sub(
            r'[<>:"/\\|?*]+',
            "_",
            text,
        )

        cleaned = cleaned.strip(
            " ."
        )

        if not cleaned:
            cleaned = "conversation"

        return cleaned[:100]


    def export_search_results(self):

        if not self.results:

            QMessageBox.information(
                self,
                "Export This Page",
                "There are no displayed search results to export.",
            )

            return

        page_size = int(
            self.limit_filter.currentText()
        )

        page_number = (
            self.search_offset
            // page_size
        ) + 1

        self.write_search_export(
            rows=self.results,
            scope_label="Current displayed page",
            start_number=(
                self.search_offset
                + 1
            ),
            default_suffix=(
                f"_Page_{page_number}"
            ),
        )


    def export_all_search_results(self):

        if self.total_results <= 0:

            QMessageBox.information(
                self,
                "Export All Matches",
                "There are no search matches to export.",
            )

            return

        try:

            rows = (
                self.fetch_all_search_rows()
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Export Error",
                str(exc),
            )

            return

        if len(rows) != self.total_results:

            QMessageBox.warning(
                self,
                "Export Count Changed",
                (
                    "The search result count changed "
                    "while preparing the export.\n\n"
                    f"Expected: {self.total_results:,}\n"
                    f"Found now: {len(rows):,}\n\n"
                    "The export was not written. "
                    "Run the search again first."
                ),
            )

            return

        self.write_search_export(
            rows=rows,
            scope_label="All matching results",
            start_number=1,
            default_suffix="_All_Matches",
        )


    def write_search_export(
        self,
        rows,
        scope_label,
        start_number,
        default_suffix,
    ):

        query = (
            self.search_box
            .text()
            .strip()
            or "search"
        )

        default_name = (
            "WyrmMango_Search_"
            + self.safe_filename(query)
            + default_suffix
            + ".md"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Search Results",
            str(
                Path.home()
                / "Documents"
                / default_name
            ),
            "Markdown Files (*.md);;"
            "Text Files (*.txt);;"
            "All Files (*)",
        )

        if not filename:
            return

        output = []

        output.append(
            "# WyrmMango Search Results"
        )
        output.append("")
        output.append(
            f"**Search:** {query}"
        )
        output.append(
            f"**Export scope:** {scope_label}"
        )

        source_filter = self.source_filter.currentText()

        if source_filter != "All sources":
            output.append(
                f"**Source filter:** {source_filter}"
            )

        if source_filter == "Gmail":

            selected_accounts = (
                self.selected_gmail_accounts()
            )

            if selected_accounts:
                output.append(
                    "**Gmail account filter:** "
                    + ", ".join(selected_accounts)
                )
            else:
                output.append(
                    "**Gmail account filter:** All Gmail accounts"
                )

        role = self.role_filter.currentText()

        if role != "All roles":
            output.append(
                f"**Role:** {role}"
            )

        title_filter = (
            self.title_filter
            .text()
            .strip()
        )

        if title_filter:
            output.append(
                f"**Title filter:** "
                f"{title_filter}"
            )

        if self.after_enabled.isChecked():
            output.append(
                "**After:** "
                + self.after_date
                .date()
                .toString("yyyy-MM-dd")
            )

        if self.before_enabled.isChecked():
            output.append(
                "**Before:** "
                + self.before_date
                .date()
                .toString("yyyy-MM-dd")
            )

        output.append(
            "**Exact phrase:** "
            + (
                "Yes"
                if self.exact_phrase.isChecked()
                else "No"
            )
        )

        output.append(
            f"**Total matching search results:** "
            f"{self.total_results:,}"
        )

        output.append(
            f"**Results exported:** "
            f"{len(rows):,}"
        )

        output.append("")
        output.append("---")
        output.append("")

        gmail_rowids = [
            row["id"]
            for row in rows
            if (
                row["source_type"]
                or ""
            ).lower() == "gmail"
        ]

        gmail_details = (
            self.gmail_message_details_bulk(
                gmail_rowids
            )
        )

        for number, row in enumerate(
            rows,
            start=start_number,
        ):

            source_name = self.source_display_name(
                row["source_type"]
            )

            is_gmail = (
                source_name.lower()
                == "gmail"
            )

            title = (
                row["title"]
                or (
                    "Untitled Email Thread"
                    if is_gmail
                    else "Untitled Conversation"
                )
            )

            role = (
                row["role"]
                or "unknown"
            )

            date = (
                row["local_time"]
                or "Unknown date"
            )

            content = (
                row["content"]
                or ""
            )

            output.append(
                f"## {number}. {title}"
            )
            output.append("")
            output.append(
                f"**Source:** {source_name}"
            )
            output.append(
                f"**Date:** {date}"
            )

            if is_gmail:

                details = gmail_details.get(
                    int(
                        row["id"]
                    ),
                    {},
                )

                account = (
                    details.get(
                        "source_account"
                    )
                    or row["source_account"]
                    or ""
                )

                sender = (
                    details.get(
                        "from_raw"
                    )
                    or row["author_name"]
                    or ""
                )

                if account:
                    output.append(
                        f"**Source account:** {account}"
                    )

                if sender:
                    output.append(
                        f"**From:** {sender}"
                    )

                if details.get(
                    "to_text"
                ):
                    output.append(
                        "**To:** "
                        + details["to_text"]
                    )

                if details.get(
                    "gm_thrid"
                ):
                    output.append(
                        "**Gmail thread ID:** "
                        + str(
                            details["gm_thrid"]
                        )
                    )

                labels = (
                    details.get(
                        "labels"
                    )
                    or []
                )

                if labels:
                    output.append(
                        "**Gmail labels:** "
                        + ", ".join(
                            str(label)
                            for label in labels
                        )
                    )

                output.append(
                    "**Attachments:** "
                    + str(
                        details.get(
                            "attachment_count",
                            0,
                        )
                    )
                )

            else:

                model = (
                    row["model_slug"]
                    or "Unknown"
                )

                output.append(
                    f"**Role:** {role}"
                )
                output.append(
                    f"**Model:** {model}"
                )

            output.append(
                "**Conversation ID:** "
                + str(
                    row["conversation_id"]
                )
            )
            output.append("")
            output.append(content)
            output.append("")
            output.append("---")
            output.append("")

        try:

            Path(filename).write_text(
                "\n".join(output),
                encoding="utf-8",
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Export Error",
                str(exc),
            )

            return

        QMessageBox.information(
            self,
            "Export Complete",
            (
                f"{len(rows):,} search result"
                + (
                    ""
                    if len(rows) == 1
                    else "s"
                )
                + " exported successfully."
            ),
        )


    def export_conversation(self):

        selected = (
            self.result_list
            .currentRow()
        )

        if selected < 0:

            QMessageBox.information(
                self,
                "Export Conversation",
                "Select a search result first.",
            )

            return

        selected_row = self.results[
            selected
        ]

        conversation_id = (
            selected_row[
                "conversation_id"
            ]
        )

        source_name = self.source_display_name(
            selected_row["source_type"]
        )

        is_gmail = (
            source_name.lower()
            == "gmail"
        )

        title = (
            selected_row["title"]
            or (
                "Untitled Email Thread"
                if is_gmail
                else "Untitled Conversation"
            )
        )

        try:

            db = self.connect_database()

            messages = db.execute(
                """
                SELECT
                    id,
                    role,
                    author_name,
                    model_slug,
                    datetime(
                        create_time,
                        'unixepoch',
                        'localtime'
                    ) AS local_time,
                    content

                FROM messages

                WHERE conversation_id = ?
                  AND content IS NOT NULL
                  AND TRIM(content) <> ''

                ORDER BY
                    CASE
                        WHEN create_time IS NULL
                        THEN 1
                        ELSE 0
                    END,
                    create_time ASC,
                    id ASC
                """,
                (conversation_id,),
            ).fetchall()

            db.close()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Export Error",
                str(exc),
            )

            return

        default_name = (
            self.safe_filename(title)
            + ".md"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Full Conversation",
            str(
                Path.home()
                / "Documents"
                / default_name
            ),
            "Markdown Files (*.md);;"
            "Text Files (*.txt);;"
            "All Files (*)",
        )

        if not filename:
            return

        output = []

        output.append(
            f"# {title}"
        )
        output.append("")
        output.append(
            "**Exported from WyrmMango**"
        )
        output.append("")
        output.append(
            f"**Source:** {source_name}"
        )

        if is_gmail:

            account = (
                selected_row[
                    "source_account"
                ]
                or ""
            )

            if account:
                output.append("")
                output.append(
                    f"**Source account:** {account}"
                )

            selected_details = (
                self.gmail_message_details(
                    selected_row["id"]
                )
                or {}
            )

            if selected_details.get(
                "gm_thrid"
            ):
                output.append("")
                output.append(
                    "**Gmail thread ID:** "
                    + str(
                        selected_details[
                            "gm_thrid"
                        ]
                    )
                )

        output.append("")
        output.append(
            f"**Conversation ID:** "
            f"{conversation_id}"
        )
        output.append("")
        output.append(
            f"**Messages:** "
            f"{len(messages):,}"
        )
        output.append("")
        output.append("---")
        output.append("")

        for message in messages:

            date = (
                message["local_time"]
                or ""
            )

            content = (
                message["content"]
                or ""
            )

            if is_gmail:

                details = (
                    self.gmail_message_details(
                        message["id"]
                    )
                    or {}
                )

                output.append(
                    "## EMAIL"
                )
                output.append("")

                if date:
                    output.append(
                        f"**Date:** {date}"
                    )

                sender = (
                    details.get(
                        "from_raw"
                    )
                    or message["author_name"]
                    or ""
                )

                if sender:
                    output.append(
                        f"**From:** {sender}"
                    )

                if details.get(
                    "to_text"
                ):
                    output.append(
                        "**To:** "
                        + details["to_text"]
                    )

                if details.get(
                    "cc_text"
                ):
                    output.append(
                        "**Cc:** "
                        + details["cc_text"]
                    )

                labels = (
                    details.get(
                        "labels"
                    )
                    or []
                )

                if labels:
                    output.append(
                        "**Gmail labels:** "
                        + ", ".join(
                            str(label)
                            for label in labels
                        )
                    )

                output.append(
                    "**Attachments:** "
                    + str(
                        details.get(
                            "attachment_count",
                            0,
                        )
                    )
                )

            else:

                role = (
                    message["role"]
                    or "unknown"
                ).upper()

                if role == "USER":
                    role = "YOU"

                model = (
                    message["model_slug"]
                    or ""
                )

                output.append(
                    f"## {role}"
                )
                output.append("")

                if date:
                    output.append(
                        f"**Date:** {date}"
                    )

                if model:
                    output.append(
                        f"**Model:** {model}"
                    )

            output.append("")
            output.append(content)
            output.append("")
            output.append("---")
            output.append("")

        try:

            Path(filename).write_text(
                "\n".join(output),
                encoding="utf-8",
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Export Error",
                str(exc),
            )

            return

        QMessageBox.information(
            self,
            "Export Complete",
            "Conversation exported successfully.",
        )


    # ---------------------------------------------------------
    # IMPORT / UPDATE
    # ---------------------------------------------------------

    def update_import_button_state(self):

        has_export = (
            self.selected_export is not None
            and self.selected_export.exists()
        )

        source_type = (
            self.import_source_selector
            .currentText()
            .strip()
            .lower()
        )

        gmail_ready = (
            source_type != "gmail"
            or bool(
                self.gmail_import_account
                .text()
                .strip()
            )
        )

        process_running = (
            self.import_process is not None
            and self.import_process.state()
            != QProcess.ProcessState.NotRunning
        )

        read_only = bool(
            getattr(
                self,
                "read_only_database",
                False,
            )
        )

        self.import_button.setEnabled(
            has_export
            and gmail_ready
            and not process_running
            and not read_only
        )

    def update_import_source_state(self):

        source_name = (
            self.import_source_selector
            .currentText()
            .strip()
        )

        source_type = source_name.lower()
        is_gmail = source_type == "gmail"

        self.gmail_import_account.setEnabled(
            is_gmail
        )

        if not is_gmail:
            self.gmail_import_account.clear()

        help_text = {
            "chatgpt": (
                "Select the official ChatGPT data-export ZIP. "
                "The source archive itself is never modified."
            ),
            "claude": (
                "Select the official Claude data-export ZIP. "
                "The source archive itself is never modified."
            ),
            "gmail": (
                "Select a Google Takeout ZIP or MBOX file. "
                "Enter the Gmail account represented by that export "
                "so account provenance is preserved."
            ),
        }.get(
            source_type,
            "Select a supported local export.",
        )

        self.import_source_help.setText(
            help_text
        )

        self.selected_export = None
        self.export_path.clear()

        self.import_status.setText(
            f"{source_name} selected. Choose an export."
        )

        self.update_import_button_state()

    def browse_export(self):

        start_dir = (
            PROJECT_ROOT / "exports"
        )

        if not start_dir.exists():
            start_dir = Path.home()

        source_name = (
            self.import_source_selector
            .currentText()
            .strip()
        )

        source_type = source_name.lower()

        if source_type == "gmail":
            title = "Select Gmail Takeout Export"
            file_filter = (
                "Google Takeout ZIP Archives (*.zip);;"
                "MBOX Files (*.mbox);;"
                "All Files (*)"
            )
        elif source_type == "claude":
            title = "Select Claude Export"
            file_filter = (
                "ZIP Archives (*.zip);;"
                "All Files (*)"
            )
        else:
            title = "Select ChatGPT Export"
            file_filter = (
                "ZIP Archives (*.zip);;"
                "All Files (*)"
            )

        filename, _ = (
            QFileDialog.getOpenFileName(
                self,
                title,
                str(start_dir),
                file_filter,
            )
        )

        if not filename:
            return

        self.selected_export = Path(
            filename
        )

        self.export_path.setText(
            str(self.selected_export)
        )

        self.update_import_button_state()

        if (
            source_type == "gmail"
            and not self.gmail_import_account
            .text()
            .strip()
        ):
            self.import_status.setText(
                "Gmail export selected. "
                "Enter the Gmail account for this Takeout."
            )
        else:
            self.import_status.setText(
                f"{source_name} export selected. "
                "Ready to import."
            )

    def append_import_log(
        self,
        text,
    ):

        if not text:
            return

        cursor = (
            self.import_log
            .textCursor()
        )

        cursor.movePosition(
            QTextCursor.MoveOperation.End
        )

        cursor.insertText(text)

        self.import_log.setTextCursor(
            cursor
        )

        self.import_log.ensureCursorVisible()

    def start_import(self):

        if bool(
            getattr(
                self,
                "read_only_database",
                False,
            )
        ):
            QMessageBox.warning(
                self,
                "Import Disabled",
                "Import is disabled while WyrmMango "
                "is running against a read-only test database.",
            )
            return

        if not self.selected_export:
            return

        if not self.selected_export.exists():
            QMessageBox.warning(
                self,
                "Export Not Found",
                "The selected export file no longer exists.",
            )
            self.update_import_button_state()
            return

        if self.import_process is not None:
            if (
                self.import_process.state()
                != QProcess.ProcessState.NotRunning
            ):
                return

        source_type = (
            self.import_source_selector
            .currentText()
            .strip()
            .lower()
        )

        if source_type not in (
            "chatgpt",
            "claude",
            "gmail",
        ):
            QMessageBox.warning(
                self,
                "Unsupported Source",
                "Choose ChatGPT, Claude, or Gmail.",
            )
            self.update_import_button_state()
            return

        source_account = None

        if source_type == "gmail":
            source_account = (
                self.gmail_import_account
                .text()
                .strip()
            )

            if not source_account:
                QMessageBox.warning(
                    self,
                    "Gmail Account Required",
                    "Enter the Gmail account represented "
                    "by this Takeout export.",
                )
                self.update_import_button_state()
                return

        if not IMPORTER_PATH.exists():
            QMessageBox.critical(
                self,
                "Importer Not Found",
                f"Importer not found:\n{IMPORTER_PATH}",
            )
            self.update_import_button_state()
            return

        self.import_log.clear()

        self.append_import_log(
            "WyrmMango Import / Update\n"
            "===========================\n\n"
        )

        self.append_import_log(
            f"Import type: {source_type.upper()}\n"
        )

        self.append_import_log(
            f"Source: {self.selected_export}\n\n"
        )

        self.import_status.setText(
            f"Importing {source_type} archive..."
        )

        self.import_progress.setVisible(
            True
        )

        self.import_progress.setRange(
            0,
            0,
        )

        self.import_button.setEnabled(
            False
        )

        self.import_process = QProcess(
            self
        )

        self.import_process.setWorkingDirectory(
            str(PROJECT_ROOT)
        )

        self.import_process.readyReadStandardOutput.connect(
            self.read_import_stdout
        )

        self.import_process.readyReadStandardError.connect(
            self.read_import_stderr
        )

        self.import_process.finished.connect(
            self.import_finished
        )

        self.import_process.errorOccurred.connect(
            self.import_process_error
        )

        arguments = [
            str(IMPORTER_PATH),
            "--source-type",
            source_type,
            "--input",
            str(self.selected_export),
            "--database",
            str(self.db_path),
        ]

        if source_account:
            arguments.extend(
                [
                    "--source-account",
                    source_account,
                ]
            )

        self.import_process.start(
            sys.executable,
            arguments,
        )

    def read_import_stdout(self):

        if not self.import_process:
            return

        data = bytes(
            self.import_process
            .readAllStandardOutput()
        ).decode(
            "utf-8",
            errors="replace",
        )

        self.append_import_log(
            data
        )

        matches = re.findall(
            r"\[(\d+)/(\d+)\]",
            data,
        )

        if matches:

            current, total = (
                matches[-1]
            )

            current = int(current)
            total = int(total)

            self.import_progress.setRange(
                0,
                total,
            )

            self.import_progress.setValue(
                current
            )

            self.import_status.setText(
                f"Importing conversation "
                f"file {current} of {total}..."
            )

    def read_import_stderr(self):

        if not self.import_process:
            return

        data = bytes(
            self.import_process
            .readAllStandardError()
        ).decode(
            "utf-8",
            errors="replace",
        )

        if data:

            self.append_import_log(
                "\n" + data
            )

    def import_finished(
        self,
        exit_code,
        exit_status,
    ):

        self.import_button.setEnabled(
            True
        )

        if exit_code == 0:

            # Import begins in indeterminate busy mode with range 0..0.
            # Always leave busy mode explicitly when the importer exits
            # successfully, including providers that do not emit [N/N].
            self.import_progress.setRange(
                0,
                1,
            )
            self.import_progress.setValue(
                1
            )

            self.import_status.setText(
                "Import complete. "
                "Archive updated successfully."
            )

            self.import_status.setObjectName(
                "success"
            )

            self.refresh_stats()
            self.refresh_account_filter()
            self.refresh_email_account_inventory()

            self.append_import_log(
                "\n\nImport completed successfully.\n"
            )

        else:

            self.import_progress.setRange(
                0, 1
            )

            self.import_progress.setValue(
                0
            )

            self.import_status.setText(
                f"Import failed "
                f"(exit code {exit_code})."
            )

            self.import_status.setObjectName(
                "warning"
            )

            self.append_import_log(
                f"\n\nImport failed. "
                f"Exit code: {exit_code}\n"
            )

        self.import_status.style().unpolish(
            self.import_status
        )

        self.import_status.style().polish(
            self.import_status
        )

    def import_process_error(
        self,
        error,
    ):

        self.import_button.setEnabled(
            True
        )

        self.import_status.setText(
            "Unable to start importer."
        )

        self.append_import_log(
            "\nUnable to start "
            "the import process.\n"
        )


def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI", 10))

    if BRAND_ICON.exists():
        app.setWindowIcon(QIcon(str(BRAND_ICON)))

    app.setStyleSheet(STYLE)

    window = WyrmMangoWindow()
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()




