from __future__ import annotations

import html
import os
import re
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QDate
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QTextCursor
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
APP_VERSION = "0.1.0"

IS_FROZEN = bool(getattr(sys, "frozen", False))

if IS_FROZEN:
    BUNDLE_ROOT = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(sys.executable).resolve().parent,
        )
    )
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    IMPORTER_PATH = BUNDLE_ROOT / "WyrmMangoImporter.exe"
    ASSET_DIR = BUNDLE_ROOT / "assets"

    LOCAL_DATA_ROOT = (
        Path(
            os.environ.get(
                "LOCALAPPDATA",
                str(Path.home()),
            )
        )
        / "WyrmMango"
    )
    RELEASE_DB = (
        LOCAL_DATA_ROOT
        / "data"
        / "chatarchive.sqlite"
    )
else:
    BUNDLE_ROOT = Path(__file__).resolve().parent.parent
    PROJECT_ROOT = BUNDLE_ROOT
    IMPORTER_PATH = (
        Path(__file__).resolve().parent
        / "import_chatgpt.py"
    )
    ASSET_DIR = PROJECT_ROOT / "assets"
    RELEASE_DB = Path(DEFAULT_DB)

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

        self.db_path = Path(RELEASE_DB)

        if IS_FROZEN:
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        self.results = []

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


    def update_action_state(self):

        has_results = bool(self.results)
        has_selection = self.result_list.currentRow() >= 0

        self.export_results_button.setEnabled(has_results)
        self.copy_button.setEnabled(has_selection)
        self.conversation_button.setEnabled(has_selection)
        self.export_conversation_button.setEnabled(has_selection)

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
            "across your ChatGPT history."
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
            self.run_search
        )

        self.search_button = QPushButton("Search the Deep")
        self.search_button.setObjectName("primaryGold")
        self.search_button.setMinimumWidth(150)
        self.search_button.setMinimumHeight(46)
        self.search_button.clicked.connect(
            self.run_search
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

        self.role_filter = QComboBox()
        self.role_filter.addItems(
            [
                "All roles",
                "user",
                "assistant",
                "system",
                "tool",
            ]
        )
        self.role_filter.setMinimumWidth(120)
        self.role_filter.setToolTip("Limit matches to one message role.")

        self.title_filter = QLineEdit()
        self.title_filter.setPlaceholderText(
            "Conversation title contains..."
        )
        self.title_filter.setToolTip(
            "Optional title filter; search still runs against message text."
        )

        self.limit_filter = QComboBox()
        self.limit_filter.addItems(
            ["10", "25", "50", "100", "250"]
        )
        self.limit_filter.setCurrentText("50")
        self.limit_filter.setMinimumWidth(90)
        self.limit_filter.setToolTip("Maximum results to display.")

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("secondary")
        self.clear_button.clicked.connect(
            self.clear_search
        )

        filter_top.addWidget(self.role_filter)
        filter_top.addWidget(self.title_filter, 1)
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
            "Export Results"
        )
        self.export_results_button.setObjectName(
            "secondary"
        )
        self.export_results_button.clicked.connect(
            self.export_search_results
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
            "Choose your official ChatGPT export ZIP. "
            "WyrmMango reads it locally and updates your private SQLite archive."
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

        select_title = QLabel("1  •  SELECT YOUR EXPORT")
        select_title.setObjectName("paneTitle")

        select_help = QLabel(
            "Use the ZIP downloaded from ChatGPT's data export. "
            "The archive file itself is never modified."
        )
        select_help.setObjectName("tagline")
        select_help.setWordWrap(True)

        card_layout.addWidget(select_title)
        card_layout.addWidget(select_help)

        path_row = QHBoxLayout()
        path_row.setSpacing(9)

        self.export_path = QLineEdit()
        self.export_path.setReadOnly(True)
        self.export_path.setPlaceholderText(
            "No export selected"
        )

        browse_button = QPushButton("Browse…")
        browse_button.setObjectName("secondary")
        browse_button.clicked.connect(
            self.browse_export
        )

        path_row.addWidget(self.export_path, 1)
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

        card_layout.addWidget(self.import_button)

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        card_layout.addWidget(self.import_progress)

        self.import_status = QLabel("Ready.")
        self.import_status.setObjectName("tagline")
        card_layout.addWidget(self.import_status)

        layout.addWidget(card)

        log_panel = QFrame()
        log_panel.setObjectName("panelCard")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("IMPORT ACTIVITY")
        log_title.setObjectName("paneTitle")
        log_hint = QLabel("Progress, counts and integrity checks")
        log_hint.setObjectName("tagline")
        log_hint.setAlignment(Qt.AlignmentFlag.AlignRight)

        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(log_hint)
        log_layout.addLayout(log_header)

        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        self.import_log.setPlaceholderText(
            "Import progress will appear here."
        )

        log_layout.addWidget(self.import_log, 1)
        layout.addWidget(log_panel, 1)

        note = QLabel(
            "●  PRIVACY BY DESIGN  —  WyrmMango reads the selected export locally. "
            "The ZIP, SQLite database, searches and exports are not uploaded by this application."
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

    def run_search(self):

        query = (
            self.search_box
            .text()
            .strip()
        )

        if not query:
            return

        sql = """
        SELECT
            m.id,
            m.conversation_id,
            c.title,
            m.role,
            m.model_slug,
            m.create_time,
            datetime(
                m.create_time,
                'unixepoch',
                'localtime'
            ) AS local_time,
            m.content,
            bm25(messages_fts) AS rank

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

        sql += """
        ORDER BY
            rank ASC,
            m.create_time DESC

        LIMIT ?
        """

        params.append(
            int(
                self.limit_filter
                .currentText()
            )
        )

        try:

            db = self.connect_database()

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
        self.update_action_state()

        self.result_count.setText(
            f'{len(rows):,} shown  •  "{query}"'
        )

        for row in rows:

            title_text = (
                row["title"]
                or "Untitled Conversation"
            )

            date_text = (
                row["local_time"]
                or "Unknown date"
            )

            role_text = (
                row["role"]
                or "unknown"
            ).capitalize()

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

            display = (
                f"{title_text}\n"
                f"{date_text}  •  "
                f"{role_text}\n\n"
                f"{preview}"
            )

            self.result_list.addItem(
                QListWidgetItem(
                    display
                )
            )

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
    ):

        normalized_role = (
            role or "unknown"
        ).lower()

        if normalized_role == "user":

            label = "YOU"
            background = "#2b2112"
            border = "#8d621d"
            label_color = "#ffbd4a"

            left_width = "16%"
            right_width = "0%"

        elif normalized_role == "assistant":

            label = "CHATGPT"
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

        title = (
            row["title"]
            or "Untitled Conversation"
        )

        safe_title = html.escape(
            title
        )

        date = (
            row["local_time"]
            or "Unknown date"
        )

        model = (
            row["model_slug"]
            or "Unknown"
        )

        safe_model = html.escape(
            model
        )

        card = self.message_card_html(
            row["role"],
            date,
            row["content"] or "",
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
                MATCHED MESSAGE &nbsp; • &nbsp;
                Model: {safe_model}
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

        title = (
            selected_row["title"]
            or "Untitled Conversation"
        )

        try:

            db = self.connect_database()

            messages = db.execute(
                """
                SELECT
                    role,
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

            cards.append(
                self.message_card_html(
                    message["role"],
                    message["local_time"],
                    message["content"] or "",
                )
            )

        safe_title = html.escape(
            title
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
                FULL CONVERSATION
                &nbsp; • &nbsp;
                {len(messages):,} messages
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

        self.result_count.setText(
            "Enter a search above."
        )

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
                "Export Results",
                "There are no search results to export.",
            )

            return

        query = (
            self.search_box
            .text()
            .strip()
            or "search"
        )

        default_name = (
            "WyrmMango_Search_"
            + self.safe_filename(query)
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
            f"**Results exported:** "
            f"{len(self.results):,}"
        )

        output.append("")
        output.append("---")
        output.append("")

        for number, row in enumerate(
            self.results,
            start=1,
        ):

            title = (
                row["title"]
                or "Untitled Conversation"
            )

            role = (
                row["role"]
                or "unknown"
            )

            date = (
                row["local_time"]
                or "Unknown date"
            )

            model = (
                row["model_slug"]
                or "Unknown"
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
                f"**Date:** {date}"
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
            "Search results exported successfully.",
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

        title = (
            selected_row["title"]
            or "Untitled Conversation"
        )

        try:

            db = self.connect_database()

            messages = db.execute(
                """
                SELECT
                    role,
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

            role = (
                message["role"]
                or "unknown"
            ).upper()

            if role == "USER":
                role = "YOU"

            date = (
                message["local_time"]
                or ""
            )

            model = (
                message["model_slug"]
                or ""
            )

            content = (
                message["content"]
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

    def browse_export(self):

        start_dir = (
            PROJECT_ROOT / "exports"
        )

        if not start_dir.exists():
            start_dir = Path.home()

        filename, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Select ChatGPT Export",
                str(start_dir),
                (
                    "ZIP Archives (*.zip);;"
                    "All Files (*)"
                ),
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

        self.import_button.setEnabled(
            True
        )

        self.import_status.setText(
            "Export selected. Ready to import."
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

        if not self.selected_export:
            return

        if not (
            self.selected_export.exists()
        ):

            QMessageBox.warning(
                self,
                "Export Not Found",
                "The selected export file "
                "no longer exists.",
            )

            return

        if self.import_process is not None:

            if (
                self.import_process.state()
                != QProcess.ProcessState.NotRunning
            ):

                return

        self.import_log.clear()

        self.append_import_log(
            "WyrmMango Import / Update\n"
            "===========================\n\n"
        )

        self.append_import_log(
            f"Source: "
            f"{self.selected_export}\n\n"
        )

        self.import_status.setText(
            "Importing archive..."
        )

        self.import_progress.setVisible(
            True
        )

        # Busy indicator until the importer
        # reports [1/N].
        self.import_progress.setRange(
            0, 0
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

        if IS_FROZEN:

            program = str(IMPORTER_PATH)

            arguments = [
                str(self.selected_export),
                "--database",
                str(self.db_path),
            ]

        else:

            program = sys.executable

            arguments = [
                str(IMPORTER_PATH),
                str(self.selected_export),
                "--database",
                str(self.db_path),
            ]

        self.import_process.start(
            program,
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

            if (
                self.import_progress
                .maximum()
                > 0
            ):

                self.import_progress.setValue(
                    self.import_progress
                    .maximum()
                )

            self.import_status.setText(
                "Import complete. "
                "Archive updated successfully."
            )

            self.import_status.setObjectName(
                "success"
            )

            self.refresh_stats()

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




