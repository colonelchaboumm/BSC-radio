"""Brewers Social Club visual identity, adapted to a desktop production tool."""

STYLESHEET = """
QWidget { background:#1a1a1a; color:#ffffff; font-family:'Roboto'; font-size:14px; }
QMainWindow, QWidget#workspace { background:#1a1a1a; }
QFrame#masthead QLabel { background:transparent; color:#ffffff; }
QLabel#mastheadBrand { font-size:12px; font-weight:800; letter-spacing:2px; }
QLabel#mastheadTitle { font-size:34px; font-weight:900; }
QFrame#masthead QLabel#mastheadPill { background:#000000; color:#ffffff; font-size:11px; font-weight:800; padding:9px 13px; }
QLabel#mastheadNote { font-size:12px; color:#ffffff; }
QWidget#navigation, QWidget#navigation QWidget { background:#ffffff; }
QPushButton#navTab { background:#ffffff; color:#111111; border:0; border-bottom:4px solid transparent; border-radius:0;
    padding:16px 8px 12px; font-size:12px; font-weight:900; }
QPushButton#navTab:hover { color:#8c27ec; border-bottom-color:#d8b9ff; }
QPushButton#navTab:checked { color:#000000; border-bottom-color:#00d1b4; }
QPushButton#navTab:disabled { color:#999999; background:#f2f2f2; }
QLabel#heading { font-size:39px; font-weight:900; }
QLabel#subheading { color:#c4c4c4; font-size:14px; }
QLabel#eyebrow { color:#00d1b4; font-size:11px; font-weight:900; }
QLabel#hint { color:#bdbdbd; font-size:12px; }
QLabel#metric { font-size:43px; font-weight:900; color:#ffffff; }
QLabel#sectionTag { background:#000000; color:#ffffff; padding:7px 12px; font-size:11px; font-weight:900; }
QFrame#card { background:#222222; border:1px solid #373737; border-top:3px solid #00d1b4; border-radius:0; }
QFrame#card QLabel { background:transparent; border:0; }
QPushButton { border:1px solid #575757; border-radius:0; background:#222222; padding:11px 14px;
    color:#ffffff; font-size:12px; font-weight:700; }
QPushButton:hover { background:#303030; border-color:#ffffff; }
QPushButton:pressed { background:#111111; }
QPushButton:disabled { color:#747474; background:#242424; border-color:#333333; }
QPushButton#primary { background:#ffffff; color:#080808; border-color:#ffffff; font-weight:900; }
QPushButton#primary:hover { background:#00d1b4; color:#000000; border-color:#00d1b4; }
QPushButton#primary:pressed { background:#00b49a; border-color:#00b49a; }
QPushButton#primary:disabled { background:#353535; color:#777777; border-color:#353535; }
QPushButton#fileButton { background:transparent; border:0; border-bottom:1px solid #6e6e6e; color:#ffffff; padding:6px 4px; font-size:11px; }
QPushButton#fileButton:hover { color:#00d1b4; border-bottom-color:#00d1b4; }
QLineEdit,QPlainTextEdit,QComboBox { background:#111111; color:#ffffff; border:1px solid #494949; border-radius:0;
    padding:10px; selection-background-color:#673b95; selection-color:#ffffff; }
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus { border-color:#bd009f; }
QLineEdit:disabled,QPlainTextEdit:disabled,QComboBox:disabled { color:#8b8b8b; }
QComboBox::drop-down { border:0; width:25px; }
QComboBox QAbstractItemView { background:#222222; color:#ffffff; selection-background-color:#62278b; }
QTableWidget { background:#1a1a1a; alternate-background-color:#232323; border:1px solid #393939;
    gridline-color:#383838; selection-background-color:#4a245f; selection-color:#ffffff; }
QTableWidget::item { padding:10px; }
QHeaderView::section { background:#ffffff; color:#111111; border:0; border-right:1px solid #dedede;
    padding:12px 10px; font-size:11px; font-weight:900; }
QTableCornerButton::section { background:#ffffff; border:0; }
QProgressBar { background:#353535; border:0; border-radius:0; height:4px; color:transparent; }
QProgressBar::chunk { background:#00d1b4; }
QScrollArea { border:0; }
QScrollBar:vertical { width:9px; background:#111111; }
QScrollBar::handle:vertical { background:#555555; min-height:30px; border-radius:0; }
QScrollBar::handle:vertical:hover { background:#8b8b8b; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { height:9px; background:#111111; }
QScrollBar::handle:horizontal { background:#555555; min-width:30px; }
QCheckBox { spacing:10px; }
QCheckBox::indicator { width:18px; height:18px; }
QSlider::groove:horizontal { background:#555555; height:4px; }
QSlider::handle:horizontal { background:#00d1b4; width:12px; margin:-5px 0; border-radius:6px; }
QToolTip { background:#000000; color:#ffffff; border:1px solid #00d1b4; padding:5px; }
"""
