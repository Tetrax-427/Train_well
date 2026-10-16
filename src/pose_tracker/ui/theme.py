STYLE_SHEET = """
QWidget { background: #0d1117; color: #e6edf3; font-size: 14px; }
QLabel { background: transparent; }
QListWidget { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 12px; border-radius: 6px; }
QListWidget::item:selected { background: #1f6feb; color: white; }
QListWidget:disabled { color: #6e7681; }
QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 8px;
              padding: 10px 22px; font-weight: 600; }
QPushButton:hover { background: #30363d; }
QPushButton:disabled { background: #161b22; color: #6e7681; }
QPushButton#primary { background: #238636; border-color: #2ea043; color: white; }
QPushButton#primary:hover { background: #2ea043; }
QPushButton#primary:disabled { background: #161b22; border-color: #30363d; color: #6e7681; }
QPushButton#danger { background: #da3633; border-color: #f85149; color: white; }
QPushButton#danger:hover { background: #f85149; }
QPushButton#danger:disabled { background: #161b22; border-color: #30363d; color: #6e7681; }
QFrame#panel, QFrame#card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; }
QLabel#title { font-size: 20px; font-weight: 700; }
QLabel#cardTitle { font-size: 15px; font-weight: 700; color: #f0b72f; }
QLabel#subtitle { font-size: 15px; font-weight: 600; }
QLabel#caption { color: #8b949e; font-size: 12px; font-weight: 600; }
QLabel#bigNumber { font-size: 64px; font-weight: 700; }
QLabel#number { font-size: 30px; font-weight: 600; }
QTableWidget { background: #161b22; border: 1px solid #30363d; gridline-color: #30363d; }
QHeaderView::section { background: #21262d; padding: 6px; border: none; font-weight: 600; }
QScrollArea { border: none; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #161b22; padding: 10px 28px; border: 1px solid #30363d;
               border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: #1f6feb; color: white; }
"""