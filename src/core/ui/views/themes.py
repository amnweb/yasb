import ctypes
import functools
import io
import json
import logging
import math
import os
import platform
import re
import shutil
import ssl
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections import Counter, OrderedDict
from collections.abc import Callable
from ctypes import wintypes
from datetime import datetime
from html import escape as html_escape
from importlib import import_module
from textwrap import indent
from typing import cast
from urllib.parse import urlencode

import certifi
from PIL import Image, ImageFilter
from pydantic import BaseModel, ValidationError
from PyQt6.QtCore import (
    QAbstractListModel,
    QEasingCurve,
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QThreadPool,
    QTimer,
    QUrl,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkProxyFactory, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QWIDGETSIZE_MAX,
    QApplication,
    QCompleter,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QListView,
    QMainWindow,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from yaml import YAMLError, safe_load

from core.ui.components.button import Button
from core.ui.components.content_dialog import ContentDialog, ContentDialogButton
from core.ui.components.drop_down_button import DropDownButton
from core.ui.components.dropdown import DropDown
from core.ui.components.link import Link
from core.ui.components.loader import Spinner
from core.ui.components.text_box import TextBox
from core.ui.theme import FONT_FAMILIES, get_tokens, is_dark
from core.ui.views.view_base import ViewBase
from core.utils.alert_dialog import raise_info_alert
from core.utils.markdown import md_to_html, preprocess_readme
from core.utils.shell_utils import shell_open
from core.utils.system import get_architecture
from core.utils.validation_errors import format_pydantic_errors_to_yaml
from core.validation.config import YasbConfig
from core.validation.widgets.yasb.grouper import GrouperWidgetConfig
from core.widgets.services.quick_launch.icon_utils import svg_to_pixmap
from settings import BUILD_VERSION, CLI_VERSION, DEFAULT_CONFIG_DIRECTORY, RELEASE_CHANNEL

QNetworkProxyFactory.setUseSystemConfiguration(True)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.OpenMutexW.restype = wintypes.HANDLE
_kernel32.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


DEFAULT_THEME_INDEX_URLS = [
    "https://api.yasb.dev/yasb-themes/themes.json",
    "https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/themes.json",
]

DEFAULT_THEME_INSTALL_URLS = [
    "https://api.yasb.dev/yasb-themes/themes/{theme_id}",
    "https://raw.githubusercontent.com/amnweb/yasb-themes/main/themes/{theme_id}",
]

# The running bar holds this mutex until it exits (single_instance_lock in main.py).
BAR_MUTEX_NAME = "yasb_reborn"
BAR_EXIT_TIMEOUT = 10.0
SYNCHRONIZE = 0x00100000

DEFAULT_FEATURED_URLS = [
    "https://api.yasb.dev/yasb-themes/featured.json",
    "https://raw.githubusercontent.com/amnweb/yasb-themes/refs/heads/main/featured.json",
]

ICON_SEARCH = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="64 64 896 896"><path d="M960,928C960,936.667 956.833,944.167 950.5,950.5C944.167,956.833 936.667,960 928,960C919.333,960 911.833,956.833 905.5,950.5L641,686C609.667,712.333 574.583,732.583 535.75,746.75C496.917,760.917 457,768 416,768C383.667,768 352.5,763.833 322.5,755.5C292.5,747.167 264.5,735.333 238.5,720C212.5,704.667 188.75,686.25 167.25,664.75C145.75,643.25 127.333,619.5 112,593.5C96.6667,567.5 84.8333,539.5 76.5,509.5C68.1667,479.5 64,448.333 64,416C64,383.667 68.1667,352.5 76.5,322.5C84.8333,292.5 96.6667,264.5 112,238.5C127.333,212.5 145.75,188.75 167.25,167.25C188.75,145.75 212.5,127.333 238.5,112C264.5,96.6667 292.5,84.8334 322.5,76.5C352.5,68.1667 383.667,64.0001 416,64C448.333,64.0001 479.5,68.1667 509.5,76.5C539.5,84.8334 567.5,96.6667 593.5,112C619.5,127.333 643.25,145.75 664.75,167.25C686.25,188.75 704.667,212.5 720,238.5C735.333,264.5 747.167,292.5 755.5,322.5C763.833,352.5 768,383.667 768,416C768,457 760.917,496.917 746.75,535.75C732.583,574.583 712.333,609.667 686,641L950.5,905.5C956.833,911.833 960,919.333 960,928ZM704,416C704,389.667 700.583,364.25 693.75,339.75C686.917,315.25 677.25,292.333 664.75,271C652.25,249.667 637.167,230.167 619.5,212.5C601.833,194.833 582.333,179.75 561,167.25C539.667,154.75 516.75,145.083 492.25,138.25C467.75,131.417 442.333,128 416,128C376.333,128 339,135.583 304,150.75C269,165.917 238.5,186.5 212.5,212.5C186.5,238.5 165.917,269 150.75,304C135.583,339 128,376.333 128,416C128,456 135.5,493.5 150.5,528.5C165.5,563.5 186,594 212,620C238,646 268.5,666.5 303.5,681.5C338.5,696.5 376,704 416,704C455.667,704 493,696.417 528,681.25C563,666.083 593.5,645.5 619.5,619.5C645.5,593.5 666.083,563 681.25,528C696.417,493 704,455.667 704,416Z"/></svg>"""
ICON_OPEN_IN_NEW_WINDOW = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="64 64 896 896"><path d="M448,544C448,535.333 451.167,527.833 457.5,521.5L851,128L544,128C535.333,128 527.833,124.833 521.5,118.5C515.167,112.167 512,104.667 512,96C512,87.3334 515.167,79.8334 521.5,73.5C527.833,67.1667 535.333,64.0001 544,64L928,64C936.667,64.0001 944.167,67.1667 950.5,73.5C956.833,79.8334 960,87.3334 960,96L960,480C960,488.667 956.833,496.167 950.5,502.5C944.167,508.833 936.667,512 928,512C919.333,512 911.833,508.833 905.5,502.5C899.167,496.167 896,488.667 896,480L896,173.5L502.5,566.5C499.167,569.5 495.75,571.833 492.25,573.5C488.75,575.167 484.667,576 480,576C471.333,576 463.833,572.833 457.5,566.5C451.167,560.167 448,552.667 448,544ZM252,960C227,960 203.083,954.917 180.25,944.75C157.417,934.583 137.417,920.917 120.25,903.75C103.083,886.583 89.4167,866.583 79.25,843.75C69.0833,820.917 64,797 64,772L64,316C64,291 69.0833,267.083 79.25,244.25C89.4167,221.417 103.083,201.417 120.25,184.25C137.417,167.083 157.417,153.417 180.25,143.25C203.083,133.083 227,128 252,128L416,128C424.667,128 432.167,131.167 438.5,137.5C444.833,143.833 448,151.333 448,160C448,168.667 444.833,176.167 438.5,182.5C432.167,188.833 424.667,192 416,192L253.5,192C236.833,192 220.917,195.417 205.75,202.25C190.583,209.083 177.25,218.25 165.75,229.75C154.25,241.25 145.083,254.583 138.25,269.75C131.417,284.917 128,300.833 128,317.5L128,770.5C128,787.167 131.417,803.083 138.25,818.25C145.083,833.417 154.25,846.75 165.75,858.25C177.25,869.75 190.583,878.917 205.75,885.75C220.917,892.583 236.833,896 253.5,896L706.5,896C723.833,896 740.083,892.5 755.25,885.5C770.417,878.5 783.667,869.167 795,857.5C806.333,845.833 815.333,832.25 822,816.75C828.667,801.25 832,785 832,768L832,608C832,599.333 835.167,591.833 841.5,585.5C847.833,579.167 855.333,576 864,576C872.667,576 880.167,579.167 886.5,585.5C892.833,591.833 896,599.333 896,608L896,772C896,797 890.917,820.917 880.75,843.75C870.583,866.583 856.917,886.583 839.75,903.75C822.583,920.917 802.583,934.583 779.75,944.75C756.917,954.917 733,960 708,960Z"/></svg>"""
ICON_CHEVRON_LEFT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="64 64 896 896"><path d="M288,512C288,503.333 291.167,495.833 297.5,489.5L649.5,137.5C655.833,131.167 663.333,128 672,128C680.667,128 688.167,131.167 694.5,137.5C700.833,143.833 704,151.333 704,160C704,168.667 700.833,176.167 694.5,182.5L365.5,512L694.5,841.5C700.833,847.833 704,855.333 704,864C704,872.667 700.833,880.167 694.5,886.5C688.167,892.833 680.667,896 672,896C663.333,896 655.833,892.833 649.5,886.5L297.5,534.5C291.167,528.167 288,520.667 288,512Z"/></svg>"""
ICON_SETTINGS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><path fill="#FFFFFF" d="M300.5,818.5C288.833,818.5 277.333,820.667 266,825C257.667,828.333 249.167,831.833 240.5,835.5L224,842.5C215.667,846.167 207.167,849.667 198.5,853C187.167,857.333 175.667,859.5 164,859.5C154,859.5 144.833,857.417 136.5,853.25C128.167,849.083 120.667,843.167 114,835.5C109.667,830.5 104.583,823.833 98.75,815.5C92.9167,807.167 86.8333,798 80.5,788C74.1667,778 67.8333,767.417 61.5,756.25C55.1667,745.083 49.5833,734.25 44.75,723.75C39.9167,713.25 36,703.333 33,694C30,684.667 28.5,676.833 28.5,670.5C28.5,658.5 31.5,647.75 37.5,638.25C43.5,628.75 50.9167,620.083 59.75,612.25C68.5833,604.417 78.25,597 88.75,590C99.25,583 108.917,575.583 117.75,567.75C126.583,559.917 134,551.583 140,542.75C146,533.917 149,523.667 149,512C149,500.667 146,490.5 140,481.5C134,472.5 126.5,464.083 117.5,456.25C108.5,448.417 98.8333,440.833 88.5,433.5C78.1667,426.167 68.5,418.417 59.5,410.25C50.5,402.083 43,393.333 37,384C31,374.667 28,364 28,352C28,346 29.5833,338.333 32.75,329C35.9167,319.667 40,309.667 45,299C50,288.333 55.75,277.417 62.25,266.25C68.75,255.083 75.25,244.417 81.75,234.25C88.25,224.083 94.5,214.833 100.5,206.5C106.5,198.167 111.667,191.667 116,187C122.667,179.667 130.25,174 138.75,170C147.25,166 156.333,164 166,164C177.667,164 189,166.167 200,170.5C211,174.833 222,179.583 233,184.75C244,189.917 255.083,194.667 266.25,199C277.417,203.333 288.833,205.5 300.5,205.5C315.5,205.5 328.417,200.917 339.25,191.75C350.083,182.583 356.833,170.667 359.5,156L377.5,58C380.167,44.0001 386.25,32.5001 395.75,23.5C405.25,14.5001 417,8.66675 431,6C444.333,3.66675 457.833,2.08337 471.5,1.25C485.167,0.416687 498.667,0 512,0C526,0 540,0.5 554,1.5C568,2.5 581.833,4.33337 595.5,7C609.5,9.66669 621,15.5 630,24.5C639,33.5 644.833,45 647.5,59C649.167,67 650.667,75.1667 652,83.5L660,131.5C661.667,139.5 663.167,147.667 664.5,156C667.167,170.333 674,182.167 685,191.5C696,200.833 708.833,205.5 723.5,205.5C735.167,205.5 746.667,203.333 758,199C766.667,195.667 775.167,192.167 783.5,188.5L800,181.5C808.667,177.833 817.167,174.333 825.5,171C836.833,166.667 848.333,164.5 860,164.5C870.333,164.5 879.583,166.583 887.75,170.75C895.917,174.917 903.333,180.833 910,188.5C914.333,193.5 919.417,200.167 925.25,208.5C931.083,216.833 937.167,226 943.5,236C949.833,246 956.167,256.583 962.5,267.75C968.833,278.917 974.417,289.75 979.25,300.25C984.083,310.75 988,320.667 991,330C994,339.333 995.5,347.167 995.5,353.5C995.5,365.833 992.5,376.667 986.5,386C980.5,395.333 973.083,403.917 964.25,411.75C955.417,419.583 945.75,427 935.25,434C924.75,441 915.083,448.417 906.25,456.25C897.417,464.083 890,472.417 884,481.25C878,490.083 875,500.333 875,512C875,523.333 878,533.5 884,542.5C890,551.5 897.5,559.917 906.5,567.75C915.5,575.583 925.167,583.167 935.5,590.5C945.833,597.833 955.5,605.583 964.5,613.75C973.5,621.917 981,630.667 987,640C993,649.333 996,660 996,672C996,678.667 994.417,686.583 991.25,695.75C988.083,704.917 984,714.833 979,725.5C974,736.167 968.25,747 961.75,758C955.25,769 948.75,779.5 942.25,789.5C935.75,799.5 929.417,808.667 923.25,817C917.083,825.333 911.833,832 907.5,837C900.833,844.333 893.417,850 885.25,854C877.083,858 868.167,860 858.5,860C847.5,860 836.25,857.833 824.75,853.5C813.25,849.167 801.833,844.417 790.5,839.25C779.167,834.083 767.833,829.333 756.5,825C745.167,820.667 734.167,818.5 723.5,818.5C708.833,818.5 697.5,821.5 689.5,827.5C681.5,833.5 675.333,841.25 671,850.75C666.667,860.25 663.583,870.75 661.75,882.25C659.917,893.75 658,904.833 656,915.5L646.5,966C643.833,980.333 637.833,991.917 628.5,1000.75C619.167,1009.58 607.333,1015.33 593,1018C579.667,1020.33 566.25,1021.92 552.75,1022.75C539.25,1023.58 525.667,1024 512,1024C498,1024 484,1023.5 470,1022.5C456,1021.5 442.167,1019.67 428.5,1017C414.5,1014.33 403,1008.42 394,999.25C385,990.083 379.167,978.5 376.5,964.5C374.167,952.5 372,940.5 370,928.5L366,904C364,892 361.833,880 359.5,868C356.833,853.667 350,841.833 339,832.5C328,823.167 315.167,818.5 300.5,818.5ZM583.5,955C584.833,947.667 586.333,938.583 588,927.75C589.667,916.917 591.5,905.833 593.5,894.5C595.5,883.167 597.667,872.333 600,862C602.333,851.667 604.667,843.333 607,837C616.333,812 631.333,792 652,777C672.667,762 696.5,754.5 723.5,754.5C732.5,754.5 742.917,756.083 754.75,759.25C766.583,762.417 778.75,766.167 791.25,770.5C803.75,774.833 815.833,779.333 827.5,784C839.167,788.667 849.5,792.667 858.5,796C874.167,777.333 888,757.583 900,736.75C912,715.917 922.5,694.333 931.5,672L931.5,671.5L855,606.5C841,594.833 830.167,580.75 822.5,564.25C814.833,547.75 811,530.333 811,512C811,493.667 814.917,476.167 822.75,459.5C830.583,442.833 841.5,428.667 855.5,417L931,354L931,353.5C931,353.167 930.333,351.25 929,347.75C927.667,344.25 926.833,342.333 926.5,342C918.5,321.333 908.917,301.583 897.75,282.75C886.583,263.917 874,245.833 860,228.5L859.5,228.5L765.5,262.5C752.167,267.167 738.5,269.5 724.5,269.5C701.833,269.5 681,264 662,253C646,244 632.75,232 622.25,217C611.75,202 604.833,185.5 601.5,167.5L584.5,70C560.5,66.0001 536.333,64.0001 512,64C500,64.0001 488,64.4167 476,65.25C464,66.0834 452.167,67.3334 440.5,69C437.5,85.6667 434.667,102.167 432,118.5C429.333,134.833 426.167,151.167 422.5,167.5C419.5,182.167 414.333,195.75 407,208.25C399.667,220.75 390.667,231.5 380,240.5C369.333,249.5 357.333,256.583 344,261.75C330.667,266.917 316.333,269.5 301,269.5C286,269.5 271.833,267 258.5,262L258,262L166,228L165.5,228C150.167,247 136.333,266.75 124,287.25C111.667,307.75 101.167,329.333 92.5,352L92.5,352.5L169,417.5C183,429.167 193.833,443.25 201.5,459.75C209.167,476.25 213,493.667 213,512C213,530.333 209.083,547.833 201.25,564.5C193.417,581.167 182.5,595.333 168.5,607L93,670L93,670.5C93,670.833 93.6667,672.75 95,676.25C96.3333,679.75 97.1667,681.667 97.5,682C105.5,702.667 115.083,722.417 126.25,741.25C137.417,760.083 150,778.167 164,795.5L164.5,795.5L258.5,761.5C271.833,756.833 285.5,754.5 299.5,754.5C322.167,754.5 343,760 362,771C378,780 391.25,792 401.75,807C412.25,822 419.167,838.5 422.5,856.5L439.5,954C463.5,958 487.667,960 512,960C524,960 536,959.583 548,958.75C560,957.917 571.833,956.667 583.5,955ZM320,512C320,485.333 325,460.333 335,437C345,413.667 358.667,393.333 376,376C393.333,358.667 413.667,345 437,335C460.333,325 485.333,320 512,320C538.667,320 563.667,325 587,335C610.333,345 630.667,358.667 648,376C665.333,393.333 679,413.667 689,437C699,460.333 704,485.333 704,512C704,538.667 699,563.667 689,587C679,610.333 665.333,630.667 648,648C630.667,665.333 610.333,679 587,689C563.667,699 538.667,704 512,704C485.333,704 460.333,699 437,689C413.667,679 393.333,665.333 376,648C358.667,630.667 345,610.333 335,587C325,563.667 320,538.667 320,512ZM640,512C640,494.333 636.667,477.75 630,462.25C623.333,446.75 614.167,433.167 602.5,421.5C590.833,409.833 577.25,400.667 561.75,394C546.25,387.333 529.667,384 512,384C494.333,384 477.75,387.333 462.25,394C446.75,400.667 433.167,409.833 421.5,421.5C409.833,433.167 400.667,446.75 394,462.25C387.333,477.75 384,494.333 384,512C384,529.667 387.333,546.25 394,561.75C400.667,577.25 409.833,590.833 421.5,602.5C433.167,614.167 446.75,623.333 462.25,630C477.75,636.667 494.333,640 512,640C529.667,640 546.25,636.667 561.75,630C577.25,623.333 590.833,614.167 602.5,602.5C614.167,590.833 623.333,577.25 630,561.75C636.667,546.25 640,529.667 640,512Z"/></svg>"""
CARD_MIN_WIDTH = 340
CARD_RADIUS = 8
CARD_MEDIA_HEIGHT = 124
CARD_HEIGHT = CARD_MEDIA_HEIGHT + 76
CARD_IMAGE_OPACITY = 0.3
CARD_PREVIEW_HEIGHT = 40
MAX_COLUMNS = 4
FEATURED_HEIGHT = 360
FEATURED_INTERVAL_MS = 3000
FEATURED_FADE_MS = 600
PROMO_MAX_CARDS = 2
PROMO_MIN_COLUMNS = 3
HERO_HEIGHT = 400
HERO_OPACITY_DARK = 0.24
HERO_OPACITY_LIGHT = 0.18
IMAGE_MAX_WIDTH = 1600
NETWORK_TIMEOUT_MS = 10000
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
PAGE_MAX_WIDTH = 1900
PAGE_PADDING = 48
GRID_SPACING = 16
IMAGE_CACHE_LIMIT = 120
TINT_CACHE_LIMIT = 200
SCREENSHOT_WIDTH = 560
SCREENSHOT_HEIGHT = 315
SCREENSHOT_GAP = 12
SIDEBAR_WIDTH = 300
SIDEBAR_MIN_PAGE_WIDTH = 1100
DESCRIPTION_MAX_WIDTH = 720
SEARCH_BOX_WIDTH = 520
SORT_OPTIONS = [("newest", "Newest"), ("oldest", "Oldest"), ("name", "Name"), ("author", "Author")]
SUGGESTION_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
SUGGESTION_THEME_ROLE = Qt.ItemDataRole.UserRole + 2

SCROLLBAR_WIDTH = 8
SMOOTH_SCROLL_DURATION_MS = 160
SMOOTH_SCROLL_STEP = 192

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_INLINE_CODE = re.compile(r"(?<!<pre>)<code>(.*?)</code>")
_TAG_ATTR = re.compile(r'([\w-]+)\s*=\s*["\']([^"\']*)["\']')
_GITHUB_BLOB = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/blob/(.+)$")
_LIST_TAG = re.compile(r"<(/?)(ul|ol|li)\b[^>]*>", re.IGNORECASE)
_PARAGRAPH_START = re.compile(r"\s*<p\b[^>]*>", re.IGNORECASE)
_SCREENSHOTS_HEADING = re.compile(r"^(#{1,6})[ \t]*screenshots?[ \t#]*$", re.IGNORECASE | re.MULTILINE)


def _ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(list(FONT_FAMILIES))
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


@functools.cache
def _network() -> QNetworkAccessManager:
    return QNetworkAccessManager(QApplication.instance())


def _get(owner: QObject, url: str, referer: str = "") -> QNetworkReply:
    request = QNetworkRequest(QUrl(url))
    request.setTransferTimeout(NETWORK_TIMEOUT_MS)
    request.setRawHeader(b"User-Agent", USER_AGENT.encode())
    if referer:
        request.setRawHeader(b"Referer", referer.encode())
    reply = _network().get(request)
    assert reply is not None
    reply.setParent(owner)
    return reply


def _theme_tokens() -> dict[str, str]:
    t = get_tokens()
    dark = is_dark()
    return t | {
        "code_bg": "rgba(0,0,0,0.4)" if dark else "rgba(0,0,0,0.16)",
        "selection_bg": "rgba(255,255,255,0.15)" if dark else "rgba(0,0,0,0.10)",
    }


def _readme_browser_styles(t: dict[str, str]) -> tuple[str, str]:
    widget_style = (
        f"QTextBrowser {{ background: transparent; border: none; color: {t['text_primary']};"
        f" selection-background-color: {t['selection_bg']}; }}"
    )
    document_style = (
        f"h1, h2, h3, h4 {{ margin-top: 32px; margin-bottom: 8px; }}"
        f"p {{ margin: 4px 0; }}"
        f"a {{ color: {t['accent_text_primary']}; text-decoration: none; }}"
        f"code {{ background: {t['code_bg']}; font-family: 'Consolas', monospace; }}"
        f"pre {{ background: {t['code_bg']}; white-space: pre-wrap; }}"
        f"ul, ol {{ margin: 8px 0; }}"
        f"ul {{ list-style-type: none; }}"
        f"li {{ margin: 6px 0; }}"
        f"blockquote {{ margin: 8px 0; }}"
        f"table {{ border-collapse: collapse; margin: 6px 0; }}"
        f"th, td {{ border: 1px solid {t['divider_stroke_default']}; padding: 6px 10px; }}"
        f"th {{ background: {t['code_bg']}; }}"
        f"kbd {{ background: {t['code_bg']}; font-family: 'Consolas', monospace; }}"
    )
    return widget_style, document_style


def _readme_scroll_style() -> str:
    t = _theme_tokens()
    return (
        "QScrollArea { background: transparent; border: none; }"
        f"QScrollBar:vertical {{ border: none; background: transparent; width: {SCROLLBAR_WIDTH}px; margin: 8px 2px 8px 0; }}"
        f"QScrollBar::handle:vertical {{ background: {t['control_strong_stroke_disabled']}; border-radius: 3px;"
        " min-height: 28px; }"
        f"QScrollBar::handle:vertical:hover {{ background: {t['control_strong_fill_disabled']}; }}"
        "QScrollBar::handle:vertical:disabled { background: transparent; }"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }"
    )


def _strip_scroll_style() -> str:
    t = _theme_tokens()
    return (
        "QScrollArea { background: transparent; border: none; }"
        f"QScrollBar:horizontal {{ border: none; background: transparent; height: {SCROLLBAR_WIDTH}px; margin: 0; }}"
        f"QScrollBar::handle:horizontal {{ background: {t['control_strong_stroke_disabled']}; border-radius: 4px;"
        " min-width: 28px; }"
        f"QScrollBar::handle:horizontal:hover {{ background: {t['control_strong_fill_disabled']}; }}"
        "QScrollBar::handle:horizontal:disabled { background: transparent; }"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
        "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }"
    )


def _icon(svg: str, color: str, size: int = 16) -> QIcon:
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen is not None else 1.0
    pixmap = QPixmap(svg_to_pixmap(svg, size, dpr))
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return QIcon(pixmap)


def _label(text: str, size: int, color: str, weight: QFont.Weight = QFont.Weight.Normal) -> QLabel:
    label = QLabel(text)
    label.setFont(_ui_font(size, weight))
    label.setStyleSheet(f"color: {color}; background: transparent;")
    return label


def _small_tag(text: str) -> Button:
    return Button(text, variant="default", padding="8,2,8,3", font_size=12, font_weight="demibold")


def _frame_style(name: str, background: str, border: str, radius: str = "8px") -> str:
    return f"QFrame#{name} {{ background: {background}; border: 1px solid {border}; border-radius: {radius}; }}"


def _card_section(title: str, name: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
    t = _theme_tokens()
    card = QFrame()
    card.setObjectName(name)
    card.setStyleSheet(_frame_style(name, t["card_bg_default"], t["card_stroke_default"]))
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    header = QWidget()
    header.setStyleSheet("background: transparent;")
    header_layout = QVBoxLayout(header)
    header_layout.setContentsMargins(20, 14, 20, 12)
    title_label = _label(title, 14, t["text_primary"], QFont.Weight.DemiBold)
    header_layout.addWidget(title_label)
    layout.addWidget(header)
    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background: {t['divider_stroke_default']}; border: none;")
    layout.addWidget(divider)
    return card, layout, title_label


class _LruCache(OrderedDict):
    def __init__(self, limit: int):
        super().__init__()
        self._limit = limit

    def get(self, key, default=None):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return default

    def put(self, key, value) -> None:
        self[key] = value
        self.move_to_end(key)
        while len(self) > self._limit:
            self.popitem(last=False)


def _settle_layout() -> None:
    # Nested layouts recalculate one level per event loop pass; running the passes now keeps
    # Qt from painting the half-updated states in between.
    for _ in range(4):
        QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)


def _centered_page(holder: QWidget, right_inset: int = 0) -> QWidget:
    page = QWidget()
    page.setMaximumWidth(PAGE_MAX_WIDTH)
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, right_inset, 0)
    row.setSpacing(0)
    row.addStretch()
    row.addWidget(page, 1)
    row.addStretch()
    return page


def _scroll_area(
    content: QWidget, owner: QObject, extra: tuple[QWidget | None, ...] = ()
) -> tuple[QScrollArea, QScrollBar]:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    area.setStyleSheet(_readme_scroll_style())
    area.setWidget(content)
    bar = area.verticalScrollBar()
    assert bar is not None
    bar.setEnabled(bar.maximum() > 0)
    bar.rangeChanged.connect(lambda _minimum, maximum: bar.setEnabled(maximum > 0))
    smooth = SmoothScrollFilter(bar, owner)
    for widget in (area.viewport(), content, *extra):
        if widget is not None:
            widget.installEventFilter(smooth)
    return area, bar


def _tint_image(image: QImage) -> QImage | None:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        return None
    bits = image.constBits()
    if bits is None:
        return None
    pixels = bits.asstring(image.sizeInBytes())
    source = Image.frombuffer("RGBA", (image.width(), image.height()), pixels, "raw", "RGBA", image.bytesPerLine(), 1)
    small = source.resize((24, 6), Image.Resampling.BOX).convert("RGB")
    field = small.resize((120, 72), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(24))
    return QImage(field.tobytes(), field.width, field.height, field.width * 3, QImage.Format.Format_RGB888).copy()


def _faded_pixmap(tint: QImage, size: QSize, dpr: float, stops: tuple[tuple[float, int], ...]) -> QPixmap:
    image = tint.scaled(
        size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
    ).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    fade = QLinearGradient(0, 0, 0, image.height())
    for position, alpha in stops:
        fade.setColorAt(position, QColor(0, 0, 0, alpha))
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.fillRect(image.rect(), fade)
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def _smooth_hump(peak: float, steps: int = 12) -> tuple[tuple[float, int], ...]:
    def ease(x: float) -> float:
        return x * x * (3 - 2 * x)

    rise = [(peak * i / steps, round(255 * ease(i / steps))) for i in range(steps)]
    fall = [(min(1.0, peak + (1 - peak) * i / steps), round(255 * (1 - ease(i / steps)))) for i in range(steps + 1)]
    return tuple(rise + fall)


def _bar_start(pixmap: QPixmap) -> int:
    width = min(pixmap.width(), 480)
    row = pixmap.toImage().scaled(
        width, 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    background = row.pixelColor(0, 0)
    for x in range(width):
        color = row.pixelColor(x, 0)
        difference = max(
            abs(color.red() - background.red()),
            abs(color.green() - background.green()),
            abs(color.blue() - background.blue()),
        )
        if difference > 8:
            return max(0, x * pixmap.width() // width - 8)
    return 0


def _png_size(head: bytes) -> QSize | None:
    if len(head) < 24 or head[1:4] != b"PNG" or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return QSize(width, height) if width and height else None


def _elide_lines(text: str, font: QFont, width: int, max_lines: int) -> str:
    metrics = QFontMetrics(font)
    words = text.split()
    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        candidate = f"{current} {word}".strip()
        if not current or metrics.horizontalAdvance(candidate) <= width:
            current = candidate
            continue
        lines.append(current)
        if len(lines) == max_lines - 1:
            rest = " ".join(words[index:])
            lines.append(metrics.elidedText(rest, Qt.TextElideMode.ElideRight, width))
            return "\n".join(lines)
        current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _page_style(name: str, t: dict[str, str]) -> str:
    return (
        f"QWidget#{name} {{ background: transparent; }}"
        f"QFrame#relatedItem {{ background: transparent; border: none; border-radius: 8px; }}"
        f"QFrame#relatedItem:hover {{ background: {t['subtle_fill_secondary']}; }}"
    )


def _card_path(widget: QWidget) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
    return path


def _paint_framed(painter: QPainter, rect: QRectF, radius: float, fill: QColor, stroke: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
    painter.setPen(QPen(stroke, 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


def _rounded_top(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(0, 0, 0, radius), radius, radius)
    return path


def _with_bullets(html: str, color: str, indent: int) -> str:
    bullet = f'<span style="color: {color};">&#8226;</span>&nbsp;&nbsp;'
    hanging = f' style="text-indent: -{indent}px;"'
    parts, lists, last = [], [], 0
    for match in _LIST_TAG.finditer(html):
        parts.append(html[last : match.start()])
        last = match.end()
        tag, closing, name = match.group(0), match.group(1), match.group(2).lower()
        if name != "li":
            if closing and lists:
                lists.pop()
            elif not closing:
                lists.append(name)
        elif not closing and lists and lists[-1] == "ul":
            if paragraph := _PARAGRAPH_START.match(html, last):
                parts.append(tag + paragraph.group(0).replace("<p", "<p" + hanging, 1) + bullet)
                last = paragraph.end()
            else:
                parts.append(tag.replace("<li", "<li" + hanging, 1) + bullet)
            continue
        parts.append(tag)
    parts.append(html[last:])
    return "".join(parts)


def _screenshots(text: str, base_url: str) -> list[str]:
    urls = []
    for tag in _IMG_TAG.findall(md_to_html(preprocess_readme(text))):
        src = {key.lower(): value for key, value in _TAG_ATTR.findall(tag)}.get("src", "")
        if src:
            url = QUrl(base_url).resolved(QUrl(src)).toString()
            url = _GITHUB_BLOB.sub(r"https://raw.githubusercontent.com/\1/\2/\3", url)
            if url not in urls:
                urls.append(url)
    return urls


def _split_screenshots(text: str, base_url: str) -> tuple[list[str], str]:
    heading = _SCREENSHOTS_HEADING.search(text)
    if heading is None:
        return [], text
    following = re.compile(rf"^#{{1,{len(heading.group(1))}}}[ \t]", re.MULTILINE).search(text, heading.end())
    end = following.start() if following else len(text)
    urls = _screenshots(text[heading.end() : end], base_url)
    if not urls:
        return [], text
    return urls, text[: heading.start()] + text[end:]


def _widget_index(catalog: list[dict]) -> tuple[dict[str, frozenset[str]], dict[str, float]]:
    sets = {item["id"]: frozenset(item.get("widgets") or []) for item in catalog}
    counts = Counter(name for widgets in sets.values() for name in widgets)
    return sets, {name: math.log(len(catalog) / count) for name, count in counts.items()}


def _related_themes(
    theme: dict,
    catalog: list[dict],
    sets: dict[str, frozenset[str]],
    weights: dict[str, float],
    limit: int = 8,
) -> list[dict]:
    widgets = sets.get(theme["id"]) or frozenset(theme.get("widgets") or [])
    if not widgets:
        return []

    def weight(names: frozenset[str]) -> float:
        return sum(weights.get(name, 0.0) for name in names)

    scored = []
    for other in catalog:
        other_widgets = sets.get(other["id"]) or frozenset(other.get("widgets") or [])
        if other["id"] == theme["id"] or not widgets & other_widgets:
            continue
        scored.append((weight(widgets & other_widgets) / (weight(widgets | other_widgets) or 1), other))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [other for _, other in scored[:limit]]


def _parse_deep_link(args: list[str]) -> str | None:
    for arg in args[1:]:
        if arg.startswith("yasb-themes://"):
            theme_id = arg[len("yasb-themes://") :].strip("/")
            if theme_id and len(theme_id) <= 64 and re.fullmatch(r"[a-zA-Z0-9_-]+", theme_id):
                return theme_id
    return None


# Install


def _run_yasbc(cmd: str):
    subprocess.run(
        ["yasbc", cmd],
        creationflags=subprocess.CREATE_NO_WINDOW,
        capture_output=True,
    )


def _wait_for_bar_exit(timeout: float = BAR_EXIT_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        handle = _kernel32.OpenMutexW(SYNCHRONIZE, False, BAR_MUTEX_NAME)
        if not handle:
            return True
        _kernel32.CloseHandle(handle)
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def _stop_bar() -> None:
    # yasbc stop returns once the bar acknowledges, while it is still running and watching its files.
    _run_yasbc("stop")
    if not _wait_for_bar_exit():
        raise RuntimeError("YASB did not exit in time, so nothing was changed.")


def _config_paths() -> tuple[str, str, str, str]:
    home = DEFAULT_CONFIG_DIRECTORY
    return (
        os.path.join(home, "config.yaml"),
        os.path.join(home, "styles.css"),
        os.path.join(home, "config.yaml.backup"),
        os.path.join(home, "styles.css.backup"),
    )


def _apply_config(files: dict[str, bytes]) -> None:
    _stop_bar()
    try:
        os.makedirs(DEFAULT_CONFIG_DIRECTORY, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(DEFAULT_CONFIG_DIRECTORY, name), "wb") as f:
                f.write(data)
    finally:
        _run_yasbc("start")


def _restore_backup() -> None:
    cfg, sty, bcfg, bsty = _config_paths()
    files = {}
    for target, backup in ((cfg, bcfg), (sty, bsty)):
        with open(backup, "rb") as f:
            files[os.path.basename(target)] = f.read()
    _apply_config(files)


def _export_zip(destination: str) -> None:
    partial = destination + ".partial"
    skip = {os.path.abspath(destination), os.path.abspath(partial)}
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            for folder, _dirs, names in os.walk(DEFAULT_CONFIG_DIRECTORY):
                for name in names:
                    lowered = name.lower()
                    path = os.path.join(folder, name)
                    if lowered.endswith(".log") or ".log." in lowered or os.path.abspath(path) in skip:
                        continue
                    archive.write(path, os.path.relpath(path, DEFAULT_CONFIG_DIRECTORY))
        os.replace(partial, destination)
    except BaseException:
        if os.path.exists(partial):
            os.remove(partial)
        raise


def _download_theme(theme_id: str) -> dict[str, bytes]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    last_err = None
    for url in DEFAULT_THEME_INSTALL_URLS:
        base = url.format(theme_id=theme_id)
        try:
            files = {}
            for fname in ("styles.css", "config.yaml"):
                request = urllib.request.Request(f"{base}/{fname}", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, context=ctx, timeout=15) as r:
                    files[fname] = r.read()
            return files
        except Exception as exc:
            last_err = exc
    raise last_err or RuntimeError("Failed to download theme files")


def _widget_schema(widget_type: str) -> type[BaseModel]:
    # Each validation file mirrors its widget's module and defines the widget's config last, after the models it uses.
    module = import_module(f"core.validation.widgets.{widget_type.rsplit('.', 1)[0]}")
    models = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and issubclass(value, BaseModel) and value.__module__ == module.__name__
    ]
    return models[-1]


def _theme_config_errors(raw: bytes) -> str:
    try:
        data = safe_load(raw.decode("utf-8"))
        config = YasbConfig.model_validate(data if isinstance(data, dict) else {})
    except ValidationError as e:
        return format_pydantic_errors_to_yaml(e)
    except (UnicodeDecodeError, YAMLError) as e:
        return str(e)

    errors = []
    pending = [
        name
        for bar in config.bars.values()
        if bar.enabled
        for name in bar.widgets.left + bar.widgets.center + bar.widgets.right
    ]
    checked = set()
    while pending:
        name = pending.pop(0)
        if name in checked:
            continue
        checked.add(name)
        widget = config.widgets.get(name)
        if not widget:
            errors.append(f' - The widget "{name}" is undefined.')
            continue
        if not isinstance(widget, dict) or "type" not in widget:
            errors.append(f" - {name} has no widget type defined.")
            continue
        widget_type = widget["type"]
        try:
            options = _widget_schema(widget_type).model_validate(widget.get("options", {}))
        except ValidationError as e:
            errors.append(f" - {name}\n{indent(format_pydantic_errors_to_yaml(e), '      ').rstrip()}")
            continue
        except Exception:
            errors.append(f' - {name} has unknown type "{widget_type}"')
            continue
        if isinstance(options, GrouperWidgetConfig):
            pending.extend(options.widgets)
    return "\n".join(errors)


class ThemeInstallWorker(QThread):
    incompatible = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, theme_id: str, parent: QObject | None = None):
        super().__init__(parent)
        self._theme_id = theme_id

    def run(self) -> None:
        try:
            files = _download_theme(self._theme_id)
            errors = _theme_config_errors(files["config.yaml"])
            if errors:
                self.incompatible.emit(errors)
                return
            _apply_config(files)
        except Exception as exc:
            self.failed.emit(str(exc))


class TaskWorker(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], None], parent: QObject | None = None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            self._task()
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


# Shared widgets


class SmoothScrollFilter(QObject):
    def __init__(
        self,
        scroll_bar,
        parent: QObject | None = None,
        *,
        step: int = SMOOTH_SCROLL_STEP,
        duration: int = SMOOTH_SCROLL_DURATION_MS,
    ):
        super().__init__(parent)
        self._scroll_bar = scroll_bar
        self._horizontal = scroll_bar.orientation() == Qt.Orientation.Horizontal
        self._step = step
        self._animation = QPropertyAnimation(scroll_bar, b"value", self)
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if not isinstance(a1, QWheelEvent) or not self._scroll_bar.isVisible():
            return super().eventFilter(a0, a1)

        pixel, angle = a1.pixelDelta(), a1.angleDelta()
        pixel_delta = pixel.x() if self._horizontal else pixel.y()
        angle_delta = angle.x() if self._horizontal else angle.y()
        if pixel_delta == 0 and angle_delta == 0:
            return super().eventFilter(a0, a1)

        if pixel_delta:
            scroll_delta = pixel_delta
        else:
            scroll_delta = int((angle_delta / 120) * self._step)

        running = self._animation.state() == QPropertyAnimation.State.Running
        anchor = self._animation.endValue() if running else self._scroll_bar.value()
        target = max(self._scroll_bar.minimum(), min(self._scroll_bar.maximum(), int(anchor - scroll_delta)))
        if target == anchor:
            return True

        self._animation.stop()
        self._animation.setStartValue(self._scroll_bar.value())
        self._animation.setEndValue(target)
        self._animation.start()
        return True


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, spacing: int = 6):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, a0: QLayoutItem | None) -> None:
        if a0 is not None:
            self._items.append(a0)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, a0: int) -> int:
        return self._arrange(QRect(0, 0, a0, 0), apply=False)

    def setGeometry(self, a0: QRect) -> None:
        super().setGeometry(a0)
        self._arrange(a0, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _arrange(self, rect: QRect, apply: bool) -> int:
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            size = item.sizeHint()
            if x > area.x() and x + size.width() > area.right() + 1:
                x = area.x()
                y += row_height + self.spacing()
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), size))
            x += size.width() + self.spacing()
            row_height = max(row_height, size.height())
        return y + row_height - rect.y() + m.bottom()


class PreviewImage(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self._placeholder: QSize | None = None
        sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def hasHeightForWidth(self):
        return self._source_size() is not None

    def heightForWidth(self, a0):
        size = self._source_size()
        if size is not None and size.width() > 0:
            return int(min(a0, size.width()) * size.height() / size.width())
        return 0

    def set_pixmap(self, pixmap):
        self._original_pixmap = pixmap
        if not pixmap or pixmap.isNull():
            self._original_pixmap = None
        if self._original_pixmap is None:
            self.unsetCursor()
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.updateGeometry()
        self.update()

    def set_placeholder(self, size: QSize | None) -> None:
        self._placeholder = size
        self.updateGeometry()
        self.update()

    def image(self) -> QImage | None:
        return self._original_pixmap.toImage() if self._original_pixmap else None

    def _source_size(self) -> QSize | None:
        return self._original_pixmap.size() if self._original_pixmap else self._placeholder

    def _draw_rect(self) -> tuple[int, int, int, int]:
        size = self._source_size()
        if size is None or size.width() <= 0:
            return 0, 0, 0, 0
        ow, oh = size.width(), size.height()
        w = min(ow, self.width())
        h = int(w * oh / ow)
        x = (self.width() - w) // 2
        return x, 0, w, h

    def paintEvent(self, a0):
        x, y, w, h = self._draw_rect()
        if w <= 0 or h <= 0:
            return
        painter = QPainter(self)
        if self._original_pixmap is None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(_theme_tokens()["control_fill_secondary"]))
            painter.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
        else:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(x, y, w, h, self._original_pixmap)
        painter.end()

    def mouseReleaseEvent(self, ev):
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton and self._original_pixmap is not None:
            if QRect(*self._draw_rect()).contains(ev.position().toPoint()):
                self.clicked.emit()
        super().mouseReleaseEvent(ev)


class ImageViewer(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._host = parent
        self._images: list[QImage] = []
        self._index = 0
        self._pixmap: QPixmap | None = None
        self._wheel = 0
        self._opacity = 0.0
        self._fade = QVariantAnimation(self)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade.valueChanged.connect(self._set_opacity)
        self._fade.finished.connect(self._fade_finished)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        parent.installEventFilter(self)
        self.hide()

    def show_images(self, images: list[QImage], index: int = 0) -> None:
        self._images = images
        self._wheel = 0
        self._show(index)
        self.setGeometry(self._host.rect())
        self.raise_()
        self.show()
        self.setFocus()
        self._animate(1.0, 167)

    def dismiss(self) -> None:
        self._animate(0.0, 83)

    def _animate(self, end: float, duration: int) -> None:
        self._fade.stop()
        self._fade.setDuration(duration)
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(end)
        self._fade.start()

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    def _fade_finished(self) -> None:
        if self._fade.endValue() == 0.0:
            self.hide()

    def _show(self, index: int) -> None:
        self._index = max(0, min(len(self._images) - 1, index))
        self._pixmap = QPixmap.fromImage(self._images[self._index])
        self.update()

    def _step(self, offset: int) -> None:
        if 0 <= self._index + offset < len(self._images):
            self._show(self._index + offset)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1 is not None and a1.type() == QEvent.Type.Resize and a0 is self._host:
            self.setGeometry(self._host.rect())
        return super().eventFilter(a0, a1)

    def paintEvent(self, a0) -> None:
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 190))
        if self._pixmap is None:
            return
        area = self.rect().adjusted(48, 48, -48, -48)
        size = self._pixmap.size()
        if size.width() > area.width() or size.height() > area.height():
            size = size.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRect(QPoint(0, 0), size)
        target.moveCenter(area.center())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(target, self._pixmap)
        if len(self._images) > 1:
            text = f"{self._index + 1} / {len(self._images)}"
            painter.setFont(_ui_font(13))
            counter = QRectF(0, 0, painter.fontMetrics().horizontalAdvance(text) + 24, 28)
            counter.moveCenter(QPointF(self.width() / 2, self.height() - 24))
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.drawRoundedRect(counter, 14, 14)
            painter.setPen(QColor(255, 255, 255, 230))
            painter.drawText(counter, Qt.AlignmentFlag.AlignCenter, text)

    def wheelEvent(self, a0) -> None:
        if a0 is None:
            return
        self._wheel += a0.angleDelta().y()
        while abs(self._wheel) >= 120:
            offset = -1 if self._wheel > 0 else 1
            self._step(offset)
            self._wheel += 120 * offset
        a0.accept()

    def mousePressEvent(self, a0) -> None:
        self.dismiss()

    def keyPressEvent(self, a0) -> None:
        key = a0.key() if a0 is not None else None
        if key == Qt.Key.Key_Escape:
            self.dismiss()
        elif key == Qt.Key.Key_Left:
            self._step(-1)
        elif key == Qt.Key.Key_Right:
            self._step(1)
        else:
            super().keyPressEvent(a0)


class ImageFetcher(QObject):
    ready = pyqtSignal(str, QImage)
    failed = pyqtSignal(str)
    _decoded = pyqtSignal(str, int, QImage)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._replies: dict[str, QNetworkReply] = {}
        self._generation = 0
        self._decoded.connect(self._on_decoded)

    def fetch(self, url: str) -> None:
        generation = self._generation
        reply = _get(self, url, referer="https://github.com")
        self._replies[url] = reply
        reply.finished.connect(lambda u=url, r=reply, g=generation: self._on_finished(u, r, g))

    def cancel(self) -> None:
        self._generation += 1
        replies = list(self._replies.values())
        self._replies.clear()
        for reply in replies:
            reply.abort()
            reply.deleteLater()

    def _on_finished(self, url: str, reply: QNetworkReply, generation: int) -> None:
        if self._replies.get(url) is reply:
            del self._replies[url]
        data = reply.readAll().data() if reply.error() == QNetworkReply.NetworkError.NoError else b""
        reply.deleteLater()
        if generation != self._generation:
            return
        if not data:
            self.failed.emit(url)
            return
        pool = QThreadPool.globalInstance()
        assert pool is not None
        pool.start(lambda: self._decode(url, generation, data))

    def _decode(self, url: str, generation: int, data: bytes) -> None:
        # Pillow releases the GIL while decoding and resizing; QImage.fromData holds it and freezes the UI.
        try:
            with Image.open(io.BytesIO(data)) as source:
                picture = source.convert("RGBA")
            if picture.width > IMAGE_MAX_WIDTH:
                picture = picture.resize(
                    (IMAGE_MAX_WIDTH, round(picture.height * IMAGE_MAX_WIDTH / picture.width)),
                    Image.Resampling.LANCZOS,
                )
            image = QImage(
                picture.tobytes(), picture.width, picture.height, picture.width * 4, QImage.Format.Format_RGBA8888
            ).copy()
        except Exception:
            image = QImage.fromData(data)
        try:
            self._decoded.emit(url, generation, image)
        except RuntimeError:
            pass

    def _on_decoded(self, url: str, generation: int, image: QImage) -> None:
        if generation != self._generation:
            return
        if image.isNull():
            self.failed.emit(url)
        else:
            self.ready.emit(url, image)


# Home page


class ThemeCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.theme: dict | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._name_font = _ui_font(16, QFont.Weight.DemiBold)
        self._author_font = _ui_font(12, QFont.Weight.DemiBold)
        self._pixmap: QPixmap | None = None
        self._start = 0
        self._tint: QImage | None = None
        self._media: QPixmap | None = None
        self._opacity = 1.0
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(200)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.valueChanged.connect(self._set_opacity)

    def clear(self) -> None:
        self.theme = None
        self.update()

    def set_theme(self, theme: dict) -> None:
        self.theme = theme
        self._pixmap, self._start, self._tint, self._media = None, 0, None, None
        self._fade.stop()
        self._opacity = 1.0
        self.update()

    def set_preview(self, pixmap: QPixmap | None, start: int, tint: QImage | None, fade: bool = False) -> None:
        self._pixmap, self._start, self._tint, self._media = pixmap, start, tint, None
        self._fade.stop()
        self._opacity = 0.0 if fade else 1.0
        if fade:
            self._fade.start()
        self.update()

    def _set_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        self.update()

    def _media_pixmap(self, rect: QRectF, tint: QImage) -> QPixmap:
        dpr = self.devicePixelRatioF()
        size = QSize(round(rect.width() * dpr), round(rect.height() * dpr))
        if self._media is not None and self._media.size() == size:
            return self._media
        self._media = QPixmap(size)
        self._media.setDevicePixelRatio(dpr)
        self._media.fill(Qt.GlobalColor.transparent)
        area = QRectF(0, 0, rect.width(), rect.height())
        painter = QPainter(self._media)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipPath(_rounded_top(area, CARD_RADIUS - 1))
        painter.setOpacity(CARD_IMAGE_OPACITY)
        painter.drawImage(area, tint)
        painter.setOpacity(1.0)
        if self._pixmap is not None and not self._pixmap.isNull():
            scale = CARD_PREVIEW_HEIGHT / self._pixmap.height()
            source = min(self._pixmap.width() - self._start, (area.width() - 40) / scale)
            target = QRectF(0, (area.height() - CARD_PREVIEW_HEIGHT) / 2, source * scale, CARD_PREVIEW_HEIGHT)
            target.moveLeft((area.width() - target.width()) / 2)
            strip = QPainterPath()
            strip.addRoundedRect(target, 6, 6)
            painter.setClipPath(strip)
            painter.drawPixmap(target, self._pixmap, QRectF(self._start, 0, source, self._pixmap.height()))
        painter.end()
        return self._media

    def paintEvent(self, a0) -> None:
        t = _theme_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(t["card_bg_secondary"] if self.underMouse() else t["card_bg_default"])
        _paint_framed(painter, QRectF(self.rect()), CARD_RADIUS, fill, QColor(t["card_stroke_default"]))
        if self.theme is None or (self._pixmap is None and self.theme.get("image")):
            return
        painter.setOpacity(self._opacity)
        media = QRectF(1, 1, self.width() - 2, CARD_MEDIA_HEIGHT)
        if self._tint is not None:
            painter.drawPixmap(media.topLeft(), self._media_pixmap(media, self._tint))
        painter.setPen(QColor(t["text_primary"]))
        name = QRectF(16, media.bottom() + 12, self.width() - 32, 24)
        name_text = QFontMetrics(self._name_font).elidedText(
            self.theme.get("name", ""), Qt.TextElideMode.ElideRight, int(name.width())
        )
        painter.setFont(self._name_font)
        painter.drawText(name, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name_text)
        metrics = QFontMetrics(self._author_font)
        author = metrics.elidedText(self.theme.get("author", ""), Qt.TextElideMode.ElideRight, 160)
        if not author:
            return
        width = metrics.horizontalAdvance(author) + 16
        chip = QRectF(self.width() - 16 - width, self.height() - 16 - 24, width, 24)
        _paint_framed(painter, chip, 4, QColor(t["control_fill_default"]), QColor(t["card_stroke_default"]))
        painter.setPen(QColor(t["text_primary"]))
        painter.setFont(self._author_font)
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, author)

    def mouseReleaseEvent(self, a0) -> None:
        if (
            a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and self.theme is not None
            and self.rect().contains(a0.position().toPoint())
        ):
            self.clicked.emit(self.theme)
        super().mouseReleaseEvent(a0)


class ThemeGrid(QWidget):
    theme_clicked = pyqtSignal(dict)
    rendered = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.preview_for: Callable[[str], tuple[QPixmap, int] | None] = lambda theme_id: None
        self.tint_for: Callable[[str], QImage | None] = lambda theme_id: None
        self._themes: list[dict] = []
        self._loading = 0
        self._columns = 2
        self._top = 0
        self._bottom = 0
        self._cards: list[ThemeCard] = []
        self._bound: dict[str, ThemeCard] = {}

    def set_themes(self, themes: list[dict]) -> None:
        self._themes = themes
        self._loading = 0
        self._relayout()

    def set_loading(self, count: int) -> None:
        self._themes = []
        self._loading = count
        self._relayout()

    def set_columns(self, columns: int) -> None:
        if columns != self._columns:
            self._columns = columns
            self._relayout()

    def set_window(self, top: int, bottom: int) -> None:
        self._top, self._bottom = top, bottom
        self._place()

    def rendered_ids(self) -> list[str]:
        return list(self._bound)

    def update_preview(self, theme_id: str, pixmap: QPixmap, start: int) -> None:
        if (card := self._bound.get(theme_id)) is not None:
            card.set_preview(pixmap, start, self.tint_for(theme_id), fade=True)

    def _relayout(self) -> None:
        rows = math.ceil((self._loading or len(self._themes)) / self._columns)
        self.setFixedHeight(max(0, rows * (CARD_HEIGHT + GRID_SPACING) - GRID_SPACING))
        self._place()

    def _cell(self, index: int) -> QRect:
        row, column = divmod(index, self._columns)
        span = self.width() + GRID_SPACING
        left = column * span // self._columns
        right = (column + 1) * span // self._columns - GRID_SPACING
        return QRect(left, row * (CARD_HEIGHT + GRID_SPACING), right - left, CARD_HEIGHT)

    def _window(self) -> range:
        row_height = CARD_HEIGHT + GRID_SPACING
        count = self._loading or len(self._themes)
        first = max(0, self._top // row_height) * self._columns
        last = min(count, (max(0, self._bottom) // row_height + 1) * self._columns)
        return range(first, max(first, last))

    def _place(self) -> None:
        indices = self._window()
        if self._loading:
            self._bound = {}
            while len(self._cards) < len(indices):
                self._new_card()
            for card, index in zip(self._cards, indices, strict=False):
                card.clear()
                card.setGeometry(self._cell(index))
                card.show()
            for card in self._cards[len(indices) :]:
                card.hide()
            return
        wanted = {self._themes[index]["id"]: index for index in indices}
        kept = {theme_id: card for theme_id, card in self._bound.items() if theme_id in wanted}
        free = [card for card in self._cards if card not in kept.values()]
        self._bound = {}
        for theme_id, index in wanted.items():
            card = kept.get(theme_id)
            if card is None:
                card = free.pop() if free else self._new_card()
                card.set_theme(self._themes[index])
                if (preview := self.preview_for(theme_id)) is not None:
                    card.set_preview(*preview, self.tint_for(theme_id))
            card.setGeometry(self._cell(index))
            card.show()
            self._bound[theme_id] = card
        for card in free:
            card.hide()
        self.rendered.emit()

    def _new_card(self) -> ThemeCard:
        card = ThemeCard(self)
        card.clicked.connect(self.theme_clicked.emit)
        self._cards.append(card)
        return card

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        self._place()


class FeaturedBanner(QWidget):
    opened = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(FEATURED_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tint_for: Callable[[str], QImage | None] = lambda _theme_id: None
        self._fetcher = ImageFetcher(self)
        self._fetcher.ready.connect(self._on_image)
        self._theme: dict | None = None
        self._tint: QImage | None = None
        self._tint_scaled: QPixmap | None = None
        self._canvas: QPixmap | None = None
        self._images: list[QPixmap] = []
        self._scaled: dict[int, QPixmap] = {}
        self._index = 0
        self._previous: int | None = None
        self._fade = 1.0
        self._timer = QTimer(self)
        self._timer.setInterval(FEATURED_INTERVAL_MS)
        self._timer.timeout.connect(self._next)
        self._fade_animation = QVariantAnimation(self)
        self._fade_animation.setDuration(FEATURED_FADE_MS)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_animation.valueChanged.connect(self._set_fade)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.addStretch()
        self._text = QWidget()
        text_layout = QVBoxLayout(self._text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        text_layout.addWidget(_label("Featured", 12, "rgba(255,255,255,0.75)", QFont.Weight.DemiBold))
        self._title = _label("", 36, "#ffffff", QFont.Weight.Bold)
        text_layout.addWidget(self._title)
        self._author = _label("", 13, "rgba(255,255,255,0.75)")
        text_layout.addWidget(self._author)
        text_layout.addSpacing(6)
        self._description = _label("", 14, "rgba(255,255,255,0.9)")
        self._description.setWordWrap(True)
        self._description.setMaximumWidth(560)
        text_layout.addWidget(self._description)
        text_layout.addSpacing(14)
        view = Button("View theme", variant="accent")
        view.clicked.connect(self._open)
        text_layout.addWidget(view, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._text)
        self._text.hide()

    def theme(self) -> dict | None:
        return self._theme

    def reset(self) -> None:
        self._theme = None
        self._tint = self._tint_scaled = None
        self._images = []
        self._scaled = {}
        self._index = 0
        self._previous = None
        self._fade = 1.0
        self._timer.stop()
        self._fade_animation.stop()
        self._fetcher.cancel()
        self._text.hide()
        self.update()

    def set_theme(self, theme: dict) -> None:
        self.reset()
        self._theme = theme
        self._title.setText(theme.get("name", ""))
        self._author.setText(f"by {theme.get('author', '')}")
        self._description.setText(
            _elide_lines(theme.get("description", ""), self._description.font(), self._description.maximumWidth(), 2)
        )
        self._text.show()
        self.on_preview_changed(theme["id"])
        if theme.get("readme"):
            reply = _get(self, theme["readme"])
            reply.finished.connect(lambda: self._on_readme(theme, reply))

    def on_preview_changed(self, theme_id: str) -> None:
        if self._theme is not None and self._theme["id"] == theme_id and self._tint is None:
            self._tint = self.tint_for(theme_id)
            self._tint_scaled = None
            self.update()

    def _on_readme(self, theme: dict, reply: QNetworkReply) -> None:
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        text = reply.readAll().data().decode("utf-8", "replace") if ok else ""
        reply.deleteLater()
        if theme is not self._theme:
            return
        assets = f"/themes/{theme['id']}/assets/"
        for url in [url for url in _screenshots(text, theme["readme"]) if assets in url][:5]:
            self._fetcher.fetch(url)

    def _on_image(self, _url: str, image: QImage) -> None:
        if image.height() < FEATURED_HEIGHT or image.width() > image.height() * 4:
            return
        self._images.append(QPixmap.fromImage(image))
        if len(self._images) == 1:
            self._previous = None
            self._fade = 0.0
            self._fade_animation.stop()
            self._fade_animation.start()
        elif self.isVisible() and not self.underMouse():
            self._timer.start()
        self.update()

    def _next(self) -> None:
        if len(self._images) > 1:
            self._show_image((self._index + 1) % len(self._images))

    def _show_image(self, index: int) -> None:
        if index == self._index:
            return
        self._previous = self._index
        self._index = index
        self._fade = 0.0
        self._fade_animation.stop()
        self._fade_animation.start()

    def _set_fade(self, value: float) -> None:
        self._fade = value
        self.update()

    def _dot_rects(self) -> list[QRectF]:
        count = len(self._images)
        if count < 2:
            return []
        size, gap = 6, 8
        x = self.width() - 28 - count * size - (count - 1) * gap
        return [QRectF(x + i * (size + gap), self.height() - 28 - size, size, size) for i in range(count)]

    def _scaled_image(self, index: int) -> QPixmap:
        dpr = self.devicePixelRatioF()
        size = QSize(round(self.width() * dpr), round(self.height() * dpr))
        cached = self._scaled.get(index)
        if cached is None or cached.width() != size.width():
            scaled = self._images[index].scaled(
                size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            cached = scaled.copy((scaled.width() - size.width()) // 2, 0, size.width(), size.height())
            cached.setDevicePixelRatio(dpr)
            self._scaled[index] = cached
        return cached

    def _paint_base(self, painter: QPainter) -> None:
        if self._tint is None:
            painter.fillRect(self.rect(), QColor(_theme_tokens()["card_bg_default"]))
            return
        dpr = self.devicePixelRatioF()
        size = QSize(round(self.width() * dpr), round(self.height() * dpr))
        if self._tint_scaled is None or self._tint_scaled.width() != size.width():
            self._tint_scaled = QPixmap.fromImage(
                self._tint.scaled(
                    size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            self._tint_scaled.setDevicePixelRatio(dpr)
        painter.drawPixmap(0, 0, self._tint_scaled)

    def _open(self) -> None:
        if self._theme is not None:
            self.opened.emit(self._theme)

    def enterEvent(self, event) -> None:
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, a0) -> None:
        if len(self._images) > 1:
            self._timer.start()
        super().leaveEvent(a0)

    def showEvent(self, a0) -> None:
        super().showEvent(a0)
        if len(self._images) > 1 and not self.underMouse():
            self._timer.start()

    def hideEvent(self, a0) -> None:
        self._timer.stop()
        super().hideEvent(a0)

    def mouseReleaseEvent(self, a0) -> None:
        if (
            a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(a0.position().toPoint())
        ):
            position = a0.position()
            dot = next(
                (i for i, rect in enumerate(self._dot_rects()) if rect.adjusted(-6, -6, 6, 6).contains(position)), None
            )
            if dot is None:
                self._open()
            else:
                self._show_image(dot)
        super().mouseReleaseEvent(a0)

    def paintEvent(self, a0) -> None:
        if self._theme is None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(_theme_tokens()["card_bg_default"]))
            painter.drawRoundedRect(QRectF(self.rect()), CARD_RADIUS, CARD_RADIUS)
            return
        dpr = self.devicePixelRatioF()
        size = QSize(round(self.width() * dpr), round(self.height() * dpr))
        if self._canvas is None or self._canvas.size() != size:
            self._canvas = QPixmap(size)
            self._canvas.setDevicePixelRatio(dpr)
        self._canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self._canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._images:
            self._paint_base(painter)
        else:
            if self._fade < 1:
                if self._previous is None:
                    self._paint_base(painter)
                else:
                    painter.drawPixmap(0, 0, self._scaled_image(self._previous))
                painter.setOpacity(self._fade)
            painter.drawPixmap(0, 0, self._scaled_image(self._index))
            painter.setOpacity(1.0)
        bottom = QLinearGradient(0, 0, 0, self.height())
        bottom.setColorAt(0.2, QColor(0, 0, 0, 0))
        bottom.setColorAt(1.0, QColor(0, 0, 0, 200))
        painter.fillRect(self.rect(), bottom)
        side = QLinearGradient(0, 0, self.width(), 0)
        side.setColorAt(0.0, QColor(0, 0, 0, 200))
        side.setColorAt(0.75, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), side)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, rect in enumerate(self._dot_rects()):
            painter.setBrush(QColor(255, 255, 255, 230 if index == self._index else 90))
            painter.drawEllipse(rect)
        painter.end()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, self._canvas)


def _promo_card(card: object) -> dict | None:
    if not isinstance(card, dict) or not isinstance(card.get("title"), str):
        return None
    theme = card.get("theme") if isinstance(card.get("theme"), str) else ""
    url = card.get("url") if isinstance(card.get("url"), str) else ""
    if QUrl(url).scheme() != "https":
        url = ""
    if not theme and not url:
        return None
    return {
        "title": card["title"],
        "label": str(card.get("label") or ""),
        "text": str(card.get("text") or ""),
        "link_text": str(card.get("link_text") or ("View theme" if theme else "Learn more")),
        "image": str(card.get("image") or ""),
        "color": str(card.get("color") or ""),
        "theme": theme,
        "url": url,
    }


class PromoCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, card: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.card = card
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self._color = QColor(card["color"])
        if not self._color.isValid():
            self._color = QColor("#2b2b2b")
        self._image: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self._fetcher = ImageFetcher(self)
        self._fetcher.ready.connect(self._on_image)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(2)
        layout.addStretch()
        if card["label"]:
            layout.addWidget(_label(card["label"], 12, "rgba(255,255,255,0.75)", QFont.Weight.DemiBold))
        self._title = _label("", 24, "#ffffff", QFont.Weight.DemiBold)
        self._title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._title)
        self._text = _label("", 13, "rgba(255,255,255,0.9)")
        self._text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._text)
        self._text.setVisible(bool(card["text"]))
        layout.addSpacing(12)
        link = QHBoxLayout()
        link.setSpacing(6)
        link.addWidget(_label(card["link_text"], 13, "#ffffff", QFont.Weight.DemiBold))
        if card["url"]:
            icon = QLabel()
            icon.setContentsMargins(0, 2, 0, 0)
            icon.setPixmap(_icon(ICON_OPEN_IN_NEW_WINDOW, "#ffffff", 12).pixmap(12, 12))
            link.addWidget(icon)
        link.addStretch()
        layout.addLayout(link)
        if card["image"]:
            self._fetcher.fetch(card["image"])

    def _on_image(self, _url: str, image: QImage) -> None:
        self._image = QPixmap.fromImage(image)
        self._scaled = None
        self.update()

    def _scaled_image(self, image: QPixmap) -> QPixmap:
        dpr = self.devicePixelRatioF()
        size = QSize(round(self.width() * dpr), round(self.height() * dpr))
        if self._scaled is None or self._scaled.size() != size:
            scaled = image.scaled(
                size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
            )
            self._scaled = scaled.copy(
                (scaled.width() - size.width()) // 2,
                (scaled.height() - size.height()) // 2,
                size.width(),
                size.height(),
            )
            self._scaled.setDevicePixelRatio(dpr)
        return self._scaled

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        width = self.width() - 40
        title_metrics = QFontMetrics(self._title.font())
        self._title.setText(title_metrics.elidedText(self.card["title"], Qt.TextElideMode.ElideRight, width))
        if self.height() >= FEATURED_HEIGHT:
            self._text.setText(_elide_lines(self.card["text"], self._text.font(), width, 4))
        else:
            text_metrics = QFontMetrics(self._text.font())
            self._text.setText(text_metrics.elidedText(self.card["text"], Qt.TextElideMode.ElideRight, width))

    def mouseReleaseEvent(self, a0) -> None:
        if (
            a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(a0.position().toPoint())
        ):
            self.clicked.emit(self.card)
        super().mouseReleaseEvent(a0)

    def paintEvent(self, a0) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter.setClipPath(clip)
        if self._image is None:
            painter.fillRect(self.rect(), self._color)
        else:
            painter.drawPixmap(0, 0, self._scaled_image(self._image))
            side = QLinearGradient(0, 0, self.width(), 0)
            side.setColorAt(0.0, QColor(0, 0, 0, 200))
            side.setColorAt(0.75, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), side)
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0.3, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 180))
        painter.fillRect(self.rect(), shade)


class BrowsePage(QWidget):
    theme_opened = pyqtSignal(dict)
    retry_requested = pyqtSignal()
    preview_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._replies: dict[str, QNetworkReply] = {}
        self._pinned: set[str] = set()
        self._themes: dict[str, dict] = {}
        self._featured_id: str | None = None
        self._featured_status = "pending"
        self._promo_cards: list[PromoCard] = []
        self._matches: list[dict] = []
        self._query = ""
        self._sort = SORT_OPTIONS[0][0]
        self._columns = 2
        self._images = _LruCache(IMAGE_CACHE_LIMIT)
        self._tints = _LruCache(TINT_CACHE_LIMIT)
        self.sizes: dict[str, QSize] = {}
        t = _theme_tokens()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("browseContent")
        content.setStyleSheet(_page_style("browseContent", t))
        self._content = content
        column = QVBoxLayout(_centered_page(content))
        column.setContentsMargins(PAGE_PADDING, 28, PAGE_PADDING, PAGE_PADDING)
        column.setSpacing(0)
        self._message = QWidget()
        message_layout = QVBoxLayout(self._message)
        message_layout.setContentsMargins(0, 80, 0, 0)
        message_layout.setSpacing(12)
        self._message_label = _label("", 15, t["text_secondary"])
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_layout.addWidget(self._message_label)
        retry = Button("Try again", variant="default")
        retry.clicked.connect(self.retry_requested.emit)
        message_layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignCenter)
        self._message.hide()
        column.addWidget(self._message)
        self._featured = FeaturedBanner()
        self._featured.opened.connect(self.theme_opened.emit)
        self._featured.tint_for = self.tint
        self.preview_changed.connect(self._featured.on_preview_changed)
        self._promos = QWidget()
        self._promos.setFixedHeight(FEATURED_HEIGHT)
        self._promos_layout = QVBoxLayout(self._promos)
        self._promos_layout.setContentsMargins(0, 0, 0, 0)
        self._promos_layout.setSpacing(16)
        self._featured_host = QWidget()
        self._featured_layout = QGridLayout(self._featured_host)
        self._featured_layout.setContentsMargins(0, 0, 0, 24)
        self._featured_layout.setSpacing(16)
        self._place_featured()
        self._featured_host.hide()
        column.addWidget(self._featured_host)
        self._header = QWidget()
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 16)
        header_layout.setSpacing(8)
        self._header_label = _label("", 20, t["text_primary"], QFont.Weight.DemiBold)
        header_layout.addWidget(self._header_label)
        header_layout.addStretch()
        header_layout.addWidget(_label("Sort by", 14, t["text_secondary"]))
        self.sort_box = DropDown(SORT_OPTIONS, align_selected=False)
        self.sort_box.currentChanged.connect(self.set_sort)
        header_layout.addWidget(self.sort_box)
        self._header.hide()
        column.addWidget(self._header)
        self._grid = ThemeGrid()
        self._grid.preview_for = self._images.get
        self._grid.tint_for = self.tint
        self._grid.theme_clicked.connect(self.theme_opened.emit)
        self._grid.rendered.connect(self._load_rendered)
        column.addWidget(self._grid)
        column.addStretch(1)
        self._scroll, self._scroll_bar = _scroll_area(content, self)
        self._scroll_bar.valueChanged.connect(lambda _value: self._update_visible())
        root.addWidget(self._scroll, stretch=1)
        self.show_loading()

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        columns = max(1, min(MAX_COLUMNS, (min(self.width(), PAGE_MAX_WIDTH) - 60) // CARD_MIN_WIDTH))
        if columns != self._columns:
            self._columns = columns
            self._grid.set_columns(columns)
            self._place_featured()
        self._update_visible()

    def _place_featured(self) -> None:
        layout = self._featured_layout
        while layout.count():
            layout.takeAt(0)
        side = self._featured_ready() and bool(self._promo_cards) and self._columns >= PROMO_MIN_COLUMNS
        span = self._columns - 1 if side else self._columns
        layout.addWidget(self._featured, 0, 0, 1, span)
        if side:
            layout.addWidget(self._promos, 0, span)
        self._promos.setVisible(side)
        for column in range(MAX_COLUMNS):
            layout.setColumnStretch(column, 1 if column < self._columns else 0)

    def _update_visible(self) -> None:
        viewport = self._scroll.height()
        top = self._scroll_bar.value() - self._grid.mapTo(self._content, QPoint(0, 0)).y()
        self._grid.set_window(top - viewport, top + 2 * viewport)

    def _load_rendered(self) -> None:
        rendered = set(self._grid.rendered_ids())
        for theme_id in rendered:
            self._request_image(theme_id)
        for theme_id, reply in list(self._replies.items()):
            if theme_id not in rendered and theme_id not in self._pinned:
                del self._replies[theme_id]
                reply.abort()

    def _clear(self) -> None:
        self._grid.set_themes([])
        self._matches = []
        self._message.hide()
        self._featured_host.hide()
        self._header.hide()

    def featured_failed(self) -> bool:
        return self._featured_status == "failed"

    def show_loading(self) -> None:
        if self._featured_status == "failed":
            self._featured_status = "pending"
        self._clear()
        self._featured.reset()
        self._place_featured()
        self._update_featured_host()
        self._header_label.setText("All themes")
        self._header.show()
        self._grid.set_loading(9)
        self._update_visible()

    def show_error(self, message: str) -> None:
        self._clear()
        self._featured.reset()
        self._message_label.setText(f"Couldn't load themes.\n{message}")
        self._message.show()

    def set_themes(self, themes: list[dict]) -> None:
        self._clear()
        self._themes = {theme["id"]: theme for theme in themes}
        self._show_featured()
        self._place_featured()
        self._header.show()
        self._apply_filters()

    def set_featured(self, data: dict | None) -> None:
        self._featured_status = "failed" if data is None else "loaded"
        data = data or {}
        featured = data.get("featured")
        self._featured_id = featured if isinstance(featured, str) else None
        cards = data.get("cards")
        promos = [card for card in map(_promo_card, cards if isinstance(cards, list) else []) if card]
        self._promo_cards = [PromoCard(card) for card in promos[:PROMO_MAX_CARDS]]
        for widget in self._promo_cards:
            widget.clicked.connect(self._open_promo)
            self._promos_layout.addWidget(widget)
        self._place_featured()
        self._show_featured()
        self._update_featured_host()

    def _featured_ready(self) -> bool:
        return self._featured_status == "loaded" and bool(self._themes)

    def _show_featured(self) -> None:
        if not self._featured_ready():
            self._featured.reset()
            return
        theme = self._themes.get(self._featured_id or "") or max(
            self._themes.values(), key=lambda theme: theme.get("publish_date", "")
        )
        if theme is not self._featured.theme():
            self._featured.set_theme(theme)
            self.load_image(theme["id"])

    def _update_featured_host(self) -> None:
        self._featured_host.setVisible(
            not self._query and self._featured_status != "failed" and self._message.isHidden()
        )

    def _open_promo(self, card: dict) -> None:
        theme = self._themes.get(card["theme"])
        if theme is not None:
            self.theme_opened.emit(theme)
        elif card["url"]:
            shell_open(card["url"])

    def load_image(self, theme_id: str) -> None:
        self._pinned.add(theme_id)
        self._request_image(theme_id)

    def _request_image(self, theme_id: str) -> None:
        theme = self._themes.get(theme_id)
        if theme is None or not theme.get("image") or theme_id in self._images or theme_id in self._replies:
            return
        reply = _get(self, theme["image"])
        reply.readyRead.connect(lambda r=reply: self._on_preview_header(theme_id, r))
        reply.finished.connect(lambda r=reply: self._on_preview(theme_id, r))
        self._replies[theme_id] = reply

    def _on_preview_header(self, theme_id: str, reply: QNetworkReply) -> None:
        if theme_id not in self.sizes and (size := _png_size(bytes(reply.peek(24)))) is not None:
            self.sizes[theme_id] = size
            self.preview_changed.emit(theme_id)

    def _on_preview(self, theme_id: str, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if self._replies.get(theme_id) is not reply:
            return
        del self._replies[theme_id]
        self._pinned.discard(theme_id)
        data = reply.readAll().data() if reply.error() == QNetworkReply.NetworkError.NoError else b""
        pixmap = QPixmap()
        start = _bar_start(pixmap) if data and pixmap.loadFromData(data) else 0
        self._images.put(theme_id, (pixmap, start))
        self._grid.update_preview(theme_id, pixmap, start)
        self.preview_changed.emit(theme_id)

    def image_for(self, theme_id: str) -> QPixmap | None:
        cached = self._images.get(theme_id)
        return cached[0] if cached is not None else None

    def tint(self, theme_id: str) -> QImage | None:
        if theme_id not in self._tints:
            pixmap = self.image_for(theme_id)
            if pixmap is None or pixmap.isNull():
                return None
            self._tints.put(theme_id, _tint_image(pixmap.toImage()))
        return self._tints.get(theme_id)

    def set_query(self, text: str) -> None:
        query = text.strip().lower()
        if query == self._query:
            return
        self._query = query
        self._scroll_bar.setValue(0)
        self._apply_filters()

    def set_sort(self, key: str) -> None:
        self._sort = key
        self._scroll_bar.setValue(0)
        self._apply_filters()

    def _apply_filters(self) -> None:
        self._matches = [
            theme
            for theme in self._themes.values()
            if not self._query
            or self._query in theme.get("name", "").lower()
            or self._query in theme.get("author", "").lower()
            or any(self._query in widget.lower() for widget in theme.get("widgets") or [])
        ]
        if self._sort in ("newest", "oldest"):
            self._matches.sort(key=lambda theme: theme.get("publish_date", ""), reverse=self._sort == "newest")
        else:
            self._matches.sort(
                key=lambda theme: (theme.get(self._sort, "").casefold(), theme.get("name", "").casefold())
            )
        self._update_featured_host()
        self._header_label.setText("Search results" if self._query else "All themes")
        self._grid.set_themes(self._matches)
        self._update_visible()

    def shutdown(self) -> None:
        replies = list(self._replies.values())
        self._replies.clear()
        for reply in replies:
            reply.abort()
            reply.deleteLater()


# Details page


class Swatch(QWidget):
    def __init__(self, tint: QImage | None, size: int = 48, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.set_tint(tint)

    def set_tint(self, tint: QImage | None) -> None:
        self._tint = tint
        self.update()

    def paintEvent(self, a0) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipPath(_card_path(self))
        if self._tint is not None:
            painter.drawImage(QRectF(self.rect()), self._tint)
        else:
            painter.fillRect(self.rect(), QColor(_theme_tokens()["control_fill_secondary"]))


class RelatedItem(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, theme: dict, tint: QImage | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.theme = theme
        self.setObjectName("relatedItem")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = _theme_tokens()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(12)
        self.swatch = Swatch(tint)
        layout.addWidget(self.swatch, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        text_width = SIDEBAR_WIDTH - 96
        name = _label("", 14, t["text_primary"], QFont.Weight.DemiBold)
        name.setText(
            QFontMetrics(name.font()).elidedText(theme.get("name", ""), Qt.TextElideMode.ElideRight, text_width)
        )
        texts.addWidget(name)
        author = _label("", 12, t["text_secondary"])
        author.setText(
            QFontMetrics(author.font()).elidedText(
                f"by {theme.get('author', '')}", Qt.TextElideMode.ElideRight, text_width
            )
        )
        texts.addWidget(author)
        texts.addStretch()
        layout.addLayout(texts, stretch=1)

    def mouseReleaseEvent(self, a0) -> None:
        if (
            a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(a0.position().toPoint())
        ):
            self.clicked.emit(self.theme)
        super().mouseReleaseEvent(a0)


class ReadmeBrowser(QTextBrowser):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAutoFillBackground(False)
        self.setFont(_ui_font(14))
        document = self.document()
        assert document is not None
        layout = document.documentLayout()
        assert layout is not None
        document.setDocumentMargin(20)
        document.setIndentWidth(16)
        # Long documents are laid out in chunks and report partial sizes; size() finishes the layout first.
        layout.documentSizeChanged.connect(lambda _size: self.setFixedHeight(int(document.size().height()) + 1))
        widget_style, document_style = _readme_browser_styles(_theme_tokens())
        self.setStyleSheet(widget_style)
        document.setDefaultStyleSheet(document_style)

    def set_markdown(self, text: str) -> None:
        html = _INLINE_CODE.sub(r"<code>&nbsp;\1&nbsp;</code>", md_to_html(preprocess_readme(text)))
        indent = QFontMetrics(self.font()).horizontalAdvance("\u2022\u00a0\u00a0")
        self.setHtml(_with_bullets(html, _theme_tokens()["text_secondary"], indent))


class ScreenshotStrip(QWidget):
    images_clicked = pyqtSignal(list, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        t = _theme_tokens()
        self._placeholder = QColor(t["control_fill_secondary"])
        self._hover_fill = QColor(t["subtle_fill_secondary"])
        self._text_color = QColor(t["text_secondary"])
        self._urls: list[str] = []
        self._images: dict[str, QImage] = {}
        self._thumbnails: dict[str, QPixmap] = {}
        self._failed: set[str] = set()
        self._hover = -1
        self._fetcher = ImageFetcher(self)
        self._fetcher.ready.connect(self._on_ready)
        self._fetcher.failed.connect(self._on_failed)
        self.setMouseTracking(True)

    def set_urls(self, urls: list[str]) -> None:
        self._fetcher.cancel()
        self._urls = urls
        self._images.clear()
        self._thumbnails.clear()
        self._failed.clear()
        self._hover = -1
        self.unsetCursor()
        for url in urls:
            self._fetcher.fetch(url)
        self.setFixedSize(max(0, len(urls) * (SCREENSHOT_WIDTH + SCREENSHOT_GAP) - SCREENSHOT_GAP), SCREENSHOT_HEIGHT)
        self.update()

    def _rects(self) -> list[QRectF]:
        return [
            QRectF(index * (SCREENSHOT_WIDTH + SCREENSHOT_GAP), 0, SCREENSHOT_WIDTH, SCREENSHOT_HEIGHT)
            for index in range(len(self._urls))
        ]

    def _on_ready(self, url: str, image: QImage) -> None:
        self._images[url] = image
        self.update()

    def _on_failed(self, url: str) -> None:
        self._failed.add(url)
        self.update()

    def _thumbnail(self, url: str) -> QPixmap:
        dpr = self.devicePixelRatioF()
        pixmap = self._thumbnails.get(url)
        if pixmap is None or pixmap.devicePixelRatio() != dpr:
            size = QSize(round(SCREENSHOT_WIDTH * dpr), round(SCREENSHOT_HEIGHT * dpr))
            image = self._images[url]
            if 1.3 <= image.width() / image.height() <= 2.4:
                image = image.scaled(
                    size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
                )
                x, y = (image.width() - size.width()) // 2, (image.height() - size.height()) // 2
                pixmap = QPixmap.fromImage(image.copy(x, y, size.width(), size.height()))
            else:
                fitted = image.size().scaled(size, Qt.AspectRatioMode.KeepAspectRatio).boundedTo(image.size())
                image = image.scaled(
                    fitted, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                pixmap = QPixmap(size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.drawImage((size.width() - image.width()) // 2, (size.height() - image.height()) // 2, image)
                painter.end()
            pixmap.setDevicePixelRatio(dpr)
            self._thumbnails[url] = pixmap
        return pixmap

    def paintEvent(self, a0) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setFont(_ui_font(12))
        for index, (url, rect) in enumerate(zip(self._urls, self._rects(), strict=True)):
            path = QPainterPath()
            path.addRoundedRect(rect, 6, 6)
            if url not in self._images:
                painter.fillPath(path, self._placeholder)
                if url in self._failed:
                    painter.setPen(self._text_color)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Image couldn't be loaded")
                continue
            thumbnail = self._thumbnail(url)
            painter.fillPath(path, self._placeholder)
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(rect, thumbnail, QRectF(thumbnail.rect()))
            painter.restore()
            if index == self._hover:
                painter.fillPath(path, self._hover_fill)

    def _index_at(self, pos: QPointF) -> int:
        for index, rect in enumerate(self._rects()):
            if rect.contains(pos) and self._urls[index] in self._images:
                return index
        return -1

    def mouseMoveEvent(self, a0) -> None:
        if a0 is None:
            return
        index = self._index_at(a0.position())
        if index != self._hover:
            self._hover = index
            if index >= 0:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()
            self.update()

    def leaveEvent(self, a0) -> None:
        super().leaveEvent(a0)
        if self._hover >= 0:
            self._hover = -1
            self.update()

    def mouseReleaseEvent(self, a0) -> None:
        if (
            a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and (index := self._index_at(a0.position())) >= 0
        ):
            loaded = [url for url in self._urls if url in self._images]
            self.images_clicked.emit([self._images[url] for url in loaded], loaded.index(self._urls[index]))

    def shutdown(self) -> None:
        self._fetcher.cancel()


class DetailsPage(QWidget):
    scrolled = pyqtSignal(int)
    widget_tag_clicked = pyqtSignal(str)
    theme_requested = pyqtSignal(dict)
    images_clicked = pyqtSignal(list, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.theme_data: dict | None = None
        self.catalog: list[dict] = []
        self._widget_sets: dict[str, frozenset[str]] = {}
        self._widget_weights: dict[str, float] = {}
        self.image_for: Callable[[str], QPixmap | None] = lambda theme_id: None
        self.sizes: dict[str, QSize] = {}
        self.tint_for: Callable[[str], QImage | None] = lambda theme_id: None
        self.load_image: Callable[[str], None] = lambda theme_id: None
        self._readme_reply: QNetworkReply | None = None
        self._install_worker: ThemeInstallWorker | None = None
        self._install_spinner: Spinner | None = None
        self._has_related = False
        self._related_items: list[RelatedItem] = []
        t = _theme_tokens()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        content.setObjectName("detailsContent")
        content.setStyleSheet(_page_style("detailsContent", t))
        body = QVBoxLayout(_centered_page(content))
        body.setContentsMargins(PAGE_PADDING, 16, PAGE_PADDING, PAGE_PADDING)
        body.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(16)
        self._swatch = Swatch(None, 96)
        header.addWidget(self._swatch, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.name_label = _label("", 28, t["text_primary"], QFont.Weight.DemiBold)
        titles.addWidget(self.name_label)
        self.author_link = Link(padding="0,2", font_size=13)
        self.author_link.clicked.connect(self._open_author)
        titles.addWidget(self.author_link, 0, Qt.AlignmentFlag.AlignLeft)
        report = Link("Report", padding="0,2", font_size=13)
        report.clicked.connect(self._report)
        titles.addWidget(report, 0, Qt.AlignmentFlag.AlignLeft)
        titles.addStretch()
        header.addLayout(titles, stretch=1)
        body.addLayout(header)
        body.addSpacing(14)
        self.desc_label = _label("", 14, t["text_primary"])
        self.desc_label.setWordWrap(True)
        self.desc_label.setMaximumWidth(DESCRIPTION_MAX_WIDTH)
        # In a row the label gets its capped width, so its wrapped height is measured at that width.
        description = QHBoxLayout()
        description.addWidget(self.desc_label, 1)
        description.addStretch()
        body.addLayout(description)
        body.addSpacing(16)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.install_btn = Button("Install", variant="accent", padding="24,10,24,10")
        self.install_btn.clicked.connect(self._confirm_install)
        actions.addWidget(self.install_btn)
        github = Button("View on GitHub", padding="18,9,18,10", variant="default")
        github.setIcon(_icon(ICON_OPEN_IN_NEW_WINDOW, t["text_primary"], 14))
        github.setIconSize(QSize(14, 14))
        github.clicked.connect(self._open_github)
        actions.addWidget(github)
        actions.addStretch()
        body.addLayout(actions)

        columns = QHBoxLayout()
        columns.setSpacing(24)
        cards = QVBoxLayout()
        cards.setSpacing(24)
        columns.addLayout(cards, stretch=1)
        body.addSpacing(36)
        body.addLayout(columns)
        body.addStretch(1)

        self._preview_section, preview_card, _ = _card_section("Preview", "previewCard")
        preview_body = QWidget()
        preview_layout = QVBoxLayout(preview_body)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_layout.setSpacing(0)
        self.preview = PreviewImage()
        self.preview.clicked.connect(self._open_preview)
        preview_layout.addWidget(self.preview)
        preview_card.addWidget(preview_body)
        cards.addWidget(self._preview_section)

        self._widgets_section, widgets_card, self._widgets_title = _card_section("Widgets", "widgetsCard")
        self._tags = QWidget()
        self._tags_layout = FlowLayout(self._tags)
        self._tags_layout.setContentsMargins(20, 20, 20, 20)
        widgets_card.addWidget(self._tags)
        cards.addWidget(self._widgets_section)

        self._screenshots_section, screenshots_card, _ = _card_section("Screenshots", "screenshotsCard")
        screenshots_body = QWidget()
        screenshots_layout = QVBoxLayout(screenshots_body)
        screenshots_layout.setContentsMargins(20, 20, 20, 20)
        self.screenshots = ScreenshotStrip()
        self.screenshots.images_clicked.connect(self.images_clicked.emit)
        self._screenshots_area = QScrollArea()
        self._screenshots_area.setFrameShape(QFrame.Shape.NoFrame)
        self._screenshots_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._screenshots_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._screenshots_area.setStyleSheet(_strip_scroll_style())
        self._screenshots_area.setWidget(self.screenshots)
        self.screenshots.setAutoFillBackground(False)
        self._screenshots_area.setFixedHeight(SCREENSHOT_HEIGHT + SCREENSHOT_GAP + SCROLLBAR_WIDTH)
        strip_bar = self._screenshots_area.horizontalScrollBar()
        assert strip_bar is not None
        self._strip_bar = strip_bar
        strip_bar.setEnabled(False)
        strip_bar.rangeChanged.connect(lambda _minimum, maximum: strip_bar.setEnabled(maximum > 0))
        strip_smooth = SmoothScrollFilter(strip_bar, self)
        for widget in (self._screenshots_area.viewport(), self.screenshots):
            if widget is not None:
                widget.installEventFilter(strip_smooth)
        screenshots_layout.addWidget(self._screenshots_area)
        screenshots_card.addWidget(screenshots_body)
        self._screenshots_section.hide()
        cards.addWidget(self._screenshots_section)

        self._about_section, about, _ = _card_section("About", "aboutCard")
        self.readme = ReadmeBrowser()
        about.addWidget(self.readme)
        cards.addWidget(self._about_section)
        cards.addStretch(1)

        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side = QVBoxLayout(self._sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        side.addWidget(_label("Related themes", 16, t["text_primary"], QFont.Weight.DemiBold))
        self._related = QVBoxLayout()
        self._related.setSpacing(0)
        side.addLayout(self._related)
        side.addStretch()
        columns.addWidget(self._sidebar, 0, Qt.AlignmentFlag.AlignTop)

        self._scroll, self._scroll_bar = _scroll_area(
            content, self, (self.readme, self.readme.viewport(), self.preview)
        )
        self._scroll_bar.valueChanged.connect(self.scrolled.emit)
        root.addWidget(self._scroll)

    def set_catalog(self, catalog: list[dict]) -> None:
        self.catalog = catalog
        self._widget_sets, self._widget_weights = _widget_index(catalog)

    def open_theme(self, theme: dict) -> None:
        self._cancel_requests()
        self.theme_data = theme
        self.load_image(theme["id"])
        widgets = theme.get("widgets") or []
        self.name_label.setText(theme.get("name", ""))
        self.author_link.setText(f"by {html_escape(theme.get('author', ''))}")
        self.desc_label.setText(theme.get("description", ""))
        self.install_btn.setEnabled(self._install_worker is None)
        self._set_tags(widgets)
        self._set_related(theme)
        self._scroll_bar.setValue(0)
        self._update_preview()

        self.screenshots.set_urls([])
        self._strip_bar.setValue(0)
        self._screenshots_section.hide()
        self.readme.clear()
        self.readme.hide()
        self._about_section.setVisible(bool(theme.get("readme")))
        if theme.get("readme"):
            self._readme_reply = _get(self, theme["readme"])
            self._readme_reply.finished.connect(lambda r=self._readme_reply: self._on_readme(r))
        _settle_layout()

    def _set_related(self, theme: dict) -> None:
        while (item := self._related.takeAt(0)) is not None:
            if (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()
        t = _theme_tokens()
        self._related_items = []
        related = _related_themes(theme, self.catalog, self._widget_sets, self._widget_weights)
        for index, other in enumerate(related):
            if index:
                divider = QFrame(self._sidebar)
                divider.setFixedHeight(1)
                divider.setStyleSheet(f"background: {t['divider_stroke_default']}; border: none;")
                self._related.addWidget(divider)
                divider.show()
            self.load_image(other["id"])
            entry = RelatedItem(other, self.tint_for(other["id"]), self._sidebar)
            entry.clicked.connect(self.theme_requested.emit)
            self._related.addWidget(entry)
            entry.show()
            self._related_items.append(entry)
        self._has_related = bool(related)
        self._update_sidebar()

    def _update_sidebar(self) -> None:
        self._sidebar.setVisible(self._has_related and self.width() >= SIDEBAR_MIN_PAGE_WIDTH)

    def resizeEvent(self, a0) -> None:
        super().resizeEvent(a0)
        self._update_sidebar()

    def on_preview_changed(self, theme_id: str) -> None:
        if self.theme_data is not None and self.theme_data["id"] == theme_id:
            self._update_preview()
            _settle_layout()
        for entry in self._related_items:
            if entry.theme["id"] == theme_id:
                entry.swatch.set_tint(self.tint_for(theme_id))

    def _update_preview(self) -> None:
        if self.theme_data is None:
            return
        theme_id = self.theme_data["id"]
        self._swatch.set_tint(self.tint_for(theme_id))
        pixmap = self.image_for(theme_id)
        if pixmap is not None and not pixmap.isNull():
            self.preview.set_pixmap(pixmap)
            self._preview_section.show()
            return
        loading = pixmap is None and bool(self.theme_data.get("image"))
        self.preview.set_pixmap(None)
        self.preview.set_placeholder(self.sizes.get(theme_id, QSize(1920, 46)) if loading else None)
        self._preview_section.setVisible(loading)

    def _open_preview(self) -> None:
        if (image := self.preview.image()) is not None:
            self.images_clicked.emit([image], 0)

    def _set_tags(self, widgets: list[str]) -> None:
        while (item := self._tags_layout.takeAt(0)) is not None:
            if (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()
        for name in widgets:
            tag = _small_tag(name)
            tag.clicked.connect(lambda _checked=False, widget=name: self.widget_tag_clicked.emit(widget))
            self._tags_layout.addWidget(tag)
            tag.show()
        self._widgets_title.setText(f"Widgets ({len(widgets)})")
        self._widgets_section.setVisible(bool(widgets))

    def _on_readme(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply is not self._readme_reply or self.theme_data is None:
            return
        self._readme_reply = None
        data = reply.readAll().data() if reply.error() == QNetworkReply.NetworkError.NoError else b""
        screenshots, text = _split_screenshots(
            data.decode("utf-8", errors="replace"), self.theme_data.get("readme", "")
        )
        self.screenshots.set_urls(screenshots)
        self._screenshots_section.setVisible(bool(screenshots))
        if text.strip():
            self.readme.show()
            self.readme.set_markdown(text)
        else:
            self._about_section.hide()
        _settle_layout()

    def _cancel_requests(self) -> None:
        reply = self._readme_reply
        if reply is not None:
            self._readme_reply = None
            reply.abort()
            reply.deleteLater()

    def _open_author(self) -> None:
        if self.theme_data:
            author = self.theme_data.get("author", "")
            homepage = self.theme_data.get("homepage") or ""
            shell_open(homepage if homepage.startswith(("https://", "http://")) else f"https://github.com/{author}")

    def _open_github(self) -> None:
        if self.theme_data:
            shell_open(f"https://github.com/amnweb/yasb-themes/tree/main/themes/{self.theme_data['id']}")

    def _report(self) -> None:
        if not self.theme_data:
            return
        name = self.theme_data.get("name", "Unknown")
        architecture = get_architecture()
        build = f"{BUILD_VERSION} {architecture}" if architecture else BUILD_VERSION
        version = f"YASB Reborn v{build} ({RELEASE_CHANNEL})\nYASB-CLI v{CLI_VERSION}"
        body = (
            f"**Theme:** {name}\n**ID:** {self.theme_data['id']}\n**Author:** {self.theme_data.get('author', 'Unknown')}"
            f"\n\n**YASB Version:**\n```\n{version}\n```\n"
            f"**Windows Version:** Windows {platform.release()} ({platform.version()})\n\n"
            "**Describe the issue:**\n<!-- Please describe the problem with this theme -->"
        )
        params = urlencode({"title": f"[Theme issue] {name}", "body": body, "labels": "bug"})
        shell_open(f"https://github.com/amnweb/yasb-themes/issues/new?{params}")

    def _confirm_install(self) -> None:
        if not self.theme_data:
            return
        dialog = ContentDialog(
            parent=self.window() or self,
            title="Install Theme",
            content=(
                f"Are you sure you want to install {self.theme_data.get('name', '')}?\n"
                "This will overwrite your current config and styles files.\n"
                "Use Backup config in the settings menu at the top right first to keep a copy.\n"
                "Note: Some themes require additional fonts."
            ),
            primary_button_text="Install",
            close_button_text="Cancel",
            default_button=ContentDialogButton.PRIMARY,
        )
        dialog.primary_button_click.connect(self._start_install)
        dialog.show_dialog()

    def _start_install(self) -> None:
        if not self.theme_data or self._install_worker is not None:
            return
        btn = self.install_btn
        btn.setFixedSize(btn.size())
        btn.setText("")
        btn.setEnabled(False)
        spinner = Spinner(size=16, color=_theme_tokens()["text_primary"], pen_width=2, parent=btn)
        spinner.move((btn.width() - spinner.width()) // 2, (btn.height() - spinner.height()) // 2)
        spinner.show()
        self._install_spinner = spinner
        worker = ThemeInstallWorker(self.theme_data["id"], self)
        worker.incompatible.connect(self._on_install_incompatible)
        worker.failed.connect(self._on_install_failed)
        worker.finished.connect(self._on_install_finished)
        worker.finished.connect(worker.deleteLater)
        self._install_worker = worker
        worker.start()

    def _on_install_finished(self) -> None:
        self._install_worker = None
        if self._install_spinner is not None:
            self._install_spinner.deleteLater()
            self._install_spinner = None
        btn = self.install_btn
        btn.setMinimumSize(0, 0)
        btn.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
        btn.setText("Install")
        btn.setEnabled(True)

    def _on_install_incompatible(self, details: str) -> None:
        raise_info_alert(
            title="Theme not compatible",
            msg="This theme can't be loaded by your YASB version. Please update YASB and try again.",
            informative_msg="For more information, click 'Show Details'.",
            additional_details=details,
        )

    def _on_install_failed(self, error: str) -> None:
        ContentDialog(
            parent=self.window() or self,
            title="Installation Failed",
            content=f"Failed to install theme:\n{error}",
            close_button_text="Close",
        ).show_dialog()

    def shutdown(self) -> None:
        self._cancel_requests()
        self.screenshots.shutdown()
        if self._install_worker is not None:
            self._install_worker.incompatible.disconnect()
            self._install_worker.failed.disconnect()
            if (window := self.window()) is not None:
                window.hide()
            self._install_worker.wait()


# Window


class HeroBackground(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tint: QImage | None = None
        self._pixmap: QPixmap | None = None
        self._offset = 0

    def set_tint(self, tint: QImage | None) -> None:
        if tint is not self._tint:
            self._tint = tint
            self._pixmap = None
            self.update(0, 0, self.width(), HERO_HEIGHT)

    def set_offset(self, offset: int) -> None:
        offset = min(offset, HERO_HEIGHT)
        if offset != self._offset:
            self._offset = offset
            self.update(0, 0, self.width(), HERO_HEIGHT)

    def paintEvent(self, a0) -> None:
        if self._tint is None or self._offset >= HERO_HEIGHT:
            return
        dpr = self.devicePixelRatioF()
        size = QSize(int(self.width() * dpr), int(HERO_HEIGHT * dpr))
        if self._pixmap is None or self._pixmap.size() != size:
            self._pixmap = _faded_pixmap(self._tint, size, dpr, _smooth_hump(0.2))
        painter = QPainter(self)
        painter.setOpacity(HERO_OPACITY_DARK if is_dark() else HERO_OPACITY_LIGHT)
        painter.drawPixmap(0, -self._offset, self._pixmap)


class SuggestionModel(QAbstractListModel):
    def __init__(self, rows: list[tuple[str, str, dict | None]], parent: QObject | None = None):
        super().__init__(parent)
        self._rows = rows

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        name, kind, theme = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return name
        if role == SUGGESTION_KIND_ROLE:
            return kind
        if role == SUGGESTION_THEME_ROLE:
            return theme
        return None


class SuggestionDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._font = _ui_font(12)
        self._color = QColor(_theme_tokens()["text_tertiary"])

    def paint(self, painter: QPainter | None, option, index) -> None:
        super().paint(painter, option, index)
        if painter is None:
            return
        painter.save()
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.drawText(
            option.rect.adjusted(0, 0, -14, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            index.data(SUGGESTION_KIND_ROLE),
        )
        painter.restore()


class ThemeGallery(ViewBase, QMainWindow):
    def __init__(self, deep_link_theme_id: str | None = None):
        super().__init__()
        self.setWindowTitle("YASB Themes")
        self.build_app_icon()
        primary = QApplication.primaryScreen()
        assert primary is not None
        screen = primary.availableGeometry()
        h = max(600, min(int(screen.height() * 0.78), 1000))
        w = max(900, min(int(screen.width() * 0.78), int(h * 1.6), 1600))
        self.setGeometry((screen.width() - w) // 2 + screen.x(), (screen.height() - h) // 2 + screen.y(), w, h)
        self.setMinimumSize(900, 600)
        self.build_view()
        self._theme_reply: QNetworkReply | None = None
        self._featured_reply: QNetworkReply | None = None
        self._config_worker: TaskWorker | None = None
        self._deep_link_theme_id = deep_link_theme_id

        self._hero = HeroBackground()
        self._hero.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(self._hero)
        root = QVBoxLayout(self._hero)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar_row = QWidget()
        bar = QHBoxLayout(_centered_page(bar_row, right_inset=SCROLLBAR_WIDTH))
        bar.setContentsMargins(PAGE_PADDING, 12, PAGE_PADDING, 12)
        bar.setSpacing(8)
        back_slot = QWidget()
        back_slot.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        back_layout = QHBoxLayout(back_slot)
        back_layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = Button("", variant="default", padding="0,0,0,0")
        self.back_button.setIcon(_icon(ICON_CHEVRON_LEFT, _theme_tokens()["text_primary"], 16))
        self.back_button.setIconSize(QSize(16, 16))
        self.back_button.clicked.connect(self.show_browse)
        back_layout.addWidget(self.back_button)
        back_layout.addStretch()
        bar.addWidget(back_slot, 1)
        self.search_box = TextBox(placeholder="Search themes or widgets", icon_svg=ICON_SEARCH, height=36)
        self.search_box.setFixedWidth(SEARCH_BOX_WIDTH)
        self.search_box.textChanged.connect(self._on_search)
        self.search_box.returnPressed.connect(self._submit_search)
        self.search_box.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._completer = self._build_completer()
        bar.addWidget(self.search_box)
        right_slot = QWidget()
        right_slot.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        right_layout = QHBoxLayout(right_slot)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_layout.addStretch()
        self.config_status = _label("", 13, _theme_tokens()["text_secondary"])
        self.config_status.hide()
        right_layout.addWidget(self.config_status)
        right_layout.addSpacing(8)
        self._config_status_timer = QTimer(self)
        self._config_status_timer.setSingleShot(True)
        self._config_status_timer.setInterval(2000)
        self._config_status_timer.timeout.connect(self.config_status.hide)
        self.config_button = DropDownButton(
            icon_svg=ICON_SETTINGS,
            items=[("backup", "Backup config"), ("restore", "Restore config"), None, ("export", "Export as ZIP…")],
        )
        self.config_button.triggered.connect(self._on_config_action)
        right_layout.addWidget(self.config_button)
        side = self.config_button.sizeHint().height()
        self.back_button.setFixedSize(side, side)
        bar.addWidget(right_slot, 1)
        root.addWidget(bar_row)
        self._show_page_buttons(False)
        self._pages = QStackedWidget()
        root.addWidget(self._pages, stretch=1)

        self.browse = BrowsePage()
        self.details = DetailsPage()
        self.details.image_for = self.browse.image_for
        self.details.sizes = self.browse.sizes
        self.details.tint_for = self.browse.tint
        self.details.load_image = self.browse.load_image
        self._pages.addWidget(self.browse)
        self._pages.addWidget(self.details)
        self.viewer = ImageViewer(self._hero)
        self.browse.theme_opened.connect(self.open_theme)
        self.browse.retry_requested.connect(self._retry)
        self.details.widget_tag_clicked.connect(self._filter_by_widget)
        self.details.theme_requested.connect(self.open_theme)
        self.details.images_clicked.connect(self.viewer.show_images)
        self.browse.preview_changed.connect(self.details.on_preview_changed)
        self.browse.preview_changed.connect(lambda _theme_id: self._update_hero())
        self.details.scrolled.connect(self._hero.set_offset)
        self._load_index()
        self._load_featured()

    def _retry(self) -> None:
        if self.browse.featured_failed():
            self._load_featured()
        self._load_index()

    def _load_index(self, index: int = 0) -> None:
        if index == 0:
            self.browse.show_loading()
        if index >= len(DEFAULT_THEME_INDEX_URLS):
            return
        reply = _get(self, DEFAULT_THEME_INDEX_URLS[index])
        reply.finished.connect(lambda i=index, r=reply: self._on_index(i, r))
        self._theme_reply = reply

    def _load_featured(self, index: int = 0) -> None:
        reply = _get(self, DEFAULT_FEATURED_URLS[index])
        reply.finished.connect(lambda i=index, r=reply: self._on_featured(i, r))
        self._featured_reply = reply

    def _on_featured(self, index: int, reply: QNetworkReply) -> None:
        if self._featured_reply is reply:
            self._featured_reply = None
        data = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                data = json.loads(reply.readAll().data().decode("utf-8"))
            except ValueError:
                pass
        reply.deleteLater()
        if isinstance(data, dict):
            self.browse.set_featured(data)
        elif index + 1 < len(DEFAULT_FEATURED_URLS):
            self._load_featured(index + 1)
        else:
            self.browse.set_featured(None)

    def _on_index(self, index: int, reply: QNetworkReply) -> None:
        if self._theme_reply is reply:
            self._theme_reply = None
        error = reply.errorString()
        themes = None
        if reply.error() == QNetworkReply.NetworkError.NoError:
            try:
                themes = json.loads(reply.readAll().data().decode("utf-8"))
            except ValueError:
                pass
            if not isinstance(themes, dict):
                themes, error = None, "Invalid theme index response"
        reply.deleteLater()
        if themes is None:
            if index + 1 < len(DEFAULT_THEME_INDEX_URLS):
                self._load_index(index + 1)
            else:
                self.browse.show_error(error)
            return
        items = [
            {**theme, "id": theme_id}
            for theme_id, theme in themes.items()
            if isinstance(theme, dict) and not theme.get("disabled")
        ]
        self.browse.set_themes(items)
        self.details.set_catalog(items)
        self._set_suggestions(items)
        target = next((item for item in items if item["id"] == self._deep_link_theme_id), None)
        if target is not None:
            self.open_theme(target)

    def open_theme(self, theme: dict) -> None:
        self.details.open_theme(theme)
        self._pages.setCurrentWidget(self.details)
        self._show_page_buttons(True)
        self._update_hero()

    def show_browse(self) -> None:
        self._pages.setCurrentWidget(self.browse)
        self._show_page_buttons(False)
        self._update_hero()

    def _show_page_buttons(self, visible: bool) -> None:
        for button in (self.back_button, self.config_button):
            button.setVisible(visible)
        if not visible:
            self.config_status.hide()

    def _on_config_action(self, key: str) -> None:
        if self._config_worker is not None:
            return
        if key == "backup":
            self._backup_config()
        elif key == "restore":
            self._restore_config()
        elif key == "export":
            self._export_config()

    def _show_config_status(self, text: str, keep: bool = False) -> None:
        self.config_status.setText(text)
        self.config_status.show()
        if keep:
            self._config_status_timer.stop()
        else:
            self._config_status_timer.start()

    def _backup_config(self) -> None:
        cfg, sty, bcfg, bsty = _config_paths()
        try:
            shutil.copy2(cfg, bcfg)
            shutil.copy2(sty, bsty)
            self._show_config_status("Saved")
        except Exception as e:
            ContentDialog(
                parent=self, title="Backup Failed", content=f"Backup failed:\n{e}", close_button_text="Close"
            ).show_dialog()

    def _restore_config(self) -> None:
        *_, bcfg, bsty = _config_paths()
        if not os.path.exists(bcfg) or not os.path.exists(bsty):
            ContentDialog(
                parent=self,
                title="Restore Failed",
                content="Backup files are missing. Please create a backup first.",
                close_button_text="Close",
            ).show_dialog()
            return
        self._run_config_task(_restore_backup, "Restoring…", "Restored", "Restore")

    def _export_config(self) -> None:
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        name = f"yasb-config-{datetime.now():%Y-%m-%d}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Export as ZIP", os.path.join(folder, name), "ZIP files (*.zip)")
        if path:
            self._run_config_task(lambda: _export_zip(path), "Exporting…", "Exported", "Export")

    def _run_config_task(self, task: Callable[[], None], busy: str, done: str, action: str) -> None:
        worker = TaskWorker(task, self)
        worker.succeeded.connect(lambda: self._show_config_status(done))
        worker.failed.connect(lambda error: self._on_config_task_failed(action, error))
        worker.finished.connect(self._on_config_task_finished)
        worker.finished.connect(worker.deleteLater)
        self._config_worker = worker
        self._show_config_status(busy, keep=True)
        worker.start()

    def _on_config_task_failed(self, action: str, error: str) -> None:
        self.config_status.hide()
        ContentDialog(
            parent=self, title=f"{action} Failed", content=f"{action} failed:\n{error}", close_button_text="Close"
        ).show_dialog()

    def _on_config_task_finished(self) -> None:
        self._config_worker = None

    def _update_hero(self) -> None:
        theme = self.details.theme_data if self._pages.currentWidget() is self.details else None
        self._hero.set_tint(self.browse.tint(theme["id"]) if theme is not None else None)

    def _on_search(self, text: str) -> None:
        if not text.strip():
            self.browse.set_query("")

    def _submit_search(self) -> None:
        self.show_browse()
        self.browse.set_query(self.search_box.text())

    def _on_suggestion(self, index: QModelIndex) -> None:
        theme = index.data(SUGGESTION_THEME_ROLE)
        # QCompleter puts the suggestion into the line edit only after emitting activated(QModelIndex).
        QTimer.singleShot(0, lambda: self._pick_suggestion(theme))

    def _pick_suggestion(self, theme: dict | None) -> None:
        if theme is None:
            self._submit_search()
            return
        self.search_box.clear()
        self.open_theme(theme)

    def _build_completer(self) -> QCompleter:
        t = _theme_tokens()
        completer = QCompleter(self)
        completer.activated[QModelIndex].connect(self._on_suggestion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setMaxVisibleItems(8)
        popup = cast(QListView, completer.popup())
        popup.setUniformItemSizes(True)
        popup.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint)
        self._suggestion_delegate = SuggestionDelegate(popup)
        popup.setItemDelegate(self._suggestion_delegate)
        popup.setFont(_ui_font(13))
        popup.setStyleSheet(
            f"QListView {{ background: {t['dropdown_menu_bg_solid']}; color: {t['text_primary']};"
            " border: none; outline: none; }"
            "QListView::item { height: 32px; padding: 0px 10px; margin: 2px 4px; border-radius: 4px; }"
            f"QListView::item:hover, QListView::item:selected {{ background: {t['subtle_fill_secondary']};"
            f" color: {t['text_primary']}; }}"
        )
        self.search_box.setCompleter(completer)
        return completer

    def _set_suggestions(self, items: list[dict]) -> None:
        widgets = Counter(name for item in items for name in set(item.get("widgets") or []))
        authors = Counter(item["author"] for item in items if item.get("author"))
        themes = sorted((item for item in items if item.get("name")), key=lambda item: item["name"].casefold())
        rows: list[tuple[str, str, dict | None]] = [(item["name"], "Theme", item) for item in themes]
        rows += [(name, "Widget", None) for name in sorted(widgets, key=lambda name: (-widgets[name], name.casefold()))]
        rows += [(name, "Author", None) for name in sorted(authors, key=lambda name: (-authors[name], name.casefold()))]
        self._completer.setModel(SuggestionModel(rows, self._completer))

    def _filter_by_widget(self, widget: str) -> None:
        self.search_box.setText(widget)
        self._submit_search()

    def keyPressEvent(self, a0) -> None:
        if a0 is not None and a0.key() == Qt.Key.Key_Escape and self._pages.currentWidget() is self.details:
            self.show_browse()
            return
        super().keyPressEvent(a0)

    def closeEvent(self, a0) -> None:
        for reply in (self._theme_reply, self._featured_reply):
            if reply is not None:
                reply.finished.disconnect()
                reply.abort()
                reply.deleteLater()
        self._theme_reply = self._featured_reply = None
        if self._config_worker is not None:
            self._config_worker.succeeded.disconnect()
            self._config_worker.failed.disconnect()
            self.hide()
            self._config_worker.wait()
        self.browse.shutdown()
        self.details.shutdown()
        super().closeEvent(a0)


if __name__ == "__main__":
    logging.getLogger("deprecation").disabled = True
    app = QApplication(sys.argv)
    gallery = ThemeGallery(deep_link_theme_id=_parse_deep_link(sys.argv))
    gallery.show()
    sys.exit(app.exec())
