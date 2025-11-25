#!/usr/bin/env python3
import sys
import sqlite3
from datetime import datetime
import os
import base64
import urllib.parse
from PyQt6.QtCore import QUrl, Qt, QPoint, QRect, QSize
from PyQt6.QtGui import QIcon, QAction, QFont
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QToolBar,
                             QLineEdit, QPushButton, QWidget, QVBoxLayout,
                             QHBoxLayout, QComboBox, QMessageBox, QLabel,
                             QDialog, QScrollArea, QGridLayout, QMenu)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage


def get_base_path():
    """Get the base path for assets and data files (works with PyInstaller)"""
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running as regular Python script
        return os.path.dirname(os.path.abspath(__file__))


def load_svg_icon(svg_filename):
    """Load an SVG icon from assets/ folder, make it white, and return a QIcon"""
    from PyQt6.QtGui import QIcon, QPixmap
    import re
    import cairosvg
    
    svg_path = os.path.join(get_base_path(), "assets", svg_filename)
    if not os.path.exists(svg_path):
        return None
    
    try:
        # Read SVG file and modify it to be white
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
        # Replace common color attributes with white
        svg_content = re.sub(r'fill="[^"]*"', 'fill="white"', svg_content)
        svg_content = re.sub(r'stroke="[^"]*"', 'stroke="white"', svg_content)
        
        # If no fill/stroke attributes exist, add them to the svg tag
        if 'fill=' not in svg_content:
            svg_content = re.sub(r'<svg', '<svg fill="white"', svg_content)
        if 'stroke=' not in svg_content or svg_content.count('stroke=') < 2:
            svg_content = re.sub(r'<svg', '<svg stroke="white"', svg_content, count=1)
        
        # Convert SVG to PNG using cairosvg
        png_data = cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), 
                                    output_width=28, 
                                    output_height=28)
        
        # Load PNG into QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(png_data)
        
        if not pixmap.isNull():
            return QIcon(pixmap)
        
        return None
    except Exception as e:
        print(f"Error loading SVG {svg_filename}: {e}")
        return None


class TitleBar(QWidget):
    def __init__(self, parent, title="vicebrowser", show_maximize=True):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("titleBar")
        self.show_maximize = show_maximize
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #ff10f0;
            font-family: 'Arial Black', sans-serif;
        """)
        
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        if show_maximize:
            self.minimize_btn = QPushButton("—")
            self.minimize_btn.setObjectName("windowButton")
            self.minimize_btn.setFixedSize(35, 30)
            self.minimize_btn.clicked.connect(self.parent.showMinimized)
            layout.addWidget(self.minimize_btn)
            
            self.maximize_btn = QPushButton("□")
            self.maximize_btn.setObjectName("windowButton")
            self.maximize_btn.setFixedSize(35, 30)
            self.maximize_btn.clicked.connect(self.toggle_maximize)
            layout.addWidget(self.maximize_btn)
        
        self.close_btn = QPushButton()
        close_icon = load_svg_icon("x.svg")
        if close_icon:
            self.close_btn.setIcon(close_icon)
            self.close_btn.setIconSize(QSize(20, 20))
        else:
            self.close_btn.setText("×")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.setFixedSize(35, 30)
        self.close_btn.clicked.connect(self.parent.close)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        
        self.drag_position = None
        self.resize_margin = 8
        
    def is_on_resize_edge(self, pos):
        x = pos.x()
        y = pos.y()
        width = self.width()
        
        on_left = x <= self.resize_margin
        on_right = x >= width - self.resize_margin
        on_top = y <= self.resize_margin
        
        return on_left or on_right or on_top
        
    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_btn.setText("□")
        else:
            self.parent.showMaximized()
            self.maximize_btn.setText("❐")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_on_resize_edge(event.pos()):
                event.ignore()
                return
            
            # Use native window system move on Linux/X11 for better compatibility
            if not self.parent.isMaximized():
                handle = self.parent.windowHandle()
                if handle and hasattr(handle, 'startSystemMove'):
                    handle.startSystemMove()
                    event.accept()
                    return
            
            # Fallback for platforms without startSystemMove or when maximized
            self.drag_position = event.globalPosition().toPoint() - self.parent.pos()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            if not self.parent.isMaximized():
                self.parent.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.show_maximize:
            if not self.is_on_resize_edge(event.pos()):
                self.toggle_maximize()


class FramelessDialog(QDialog):
    def __init__(self, parent, title="Dialog"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        self.resize_margin = 8
        self.resizing = False
        self.resize_direction = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.title_bar = TitleBar(self, title=title, show_maximize=False)
        self.main_layout.addWidget(self.title_bar)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_widget.setLayout(self.content_layout)
        self.main_layout.addWidget(self.content_widget)
        
        # Install event filter on content widget for edge detection
        self.content_widget.installEventFilter(self)
        
        self.setLayout(self.main_layout)
        self.setMouseTracking(True)
    
    def install_filters_recursively(self, widget):
        """Recursively install event filters on all child widgets"""
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)
    
    def get_resize_direction(self, pos):
        rect = self.rect()
        x, y = pos.x(), pos.y()
        
        on_left = x <= self.resize_margin
        on_right = x >= rect.width() - self.resize_margin
        on_top = y <= self.resize_margin
        on_bottom = y >= rect.height() - self.resize_margin
        
        if on_top and on_left:
            return 'top_left'
        elif on_top and on_right:
            return 'top_right'
        elif on_bottom and on_left:
            return 'bottom_left'
        elif on_bottom and on_right:
            return 'bottom_right'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        return None
    
    def update_cursor(self, direction):
        if direction in ['top', 'bottom']:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif direction in ['left', 'right']:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction in ['top_left', 'bottom_right']:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction in ['top_right', 'bottom_left']:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resize_direction = self.get_resize_direction(event.pos())
            if self.resize_direction:
                # Try using native system resize for better Linux/X11 support
                handle = self.windowHandle()
                if handle and hasattr(handle, 'startSystemResize'):
                    edges = self.get_qt_edges(self.resize_direction)
                    if edges:
                        handle.startSystemResize(edges)
                        event.accept()
                        return
                
                # Fallback to manual resize
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def get_qt_edges(self, direction):
        """Convert string direction to Qt.Edges"""
        from PyQt6.QtCore import Qt
        edges = Qt.Edge(0)
        
        if 'left' in direction:
            edges |= Qt.Edge.LeftEdge
        if 'right' in direction:
            edges |= Qt.Edge.RightEdge
        if 'top' in direction:
            edges |= Qt.Edge.TopEdge
        if 'bottom' in direction:
            edges |= Qt.Edge.BottomEdge
        
        return edges
    
    def mouseMoveEvent(self, event):
        if self.resizing and self.resize_direction:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            geo = self.resize_start_geometry
            
            x = geo.x()
            y = geo.y()
            width = geo.width()
            height = geo.height()
            
            if 'left' in self.resize_direction:
                new_width = width - delta.x()
                if new_width >= self.minimumWidth():
                    x = geo.x() + delta.x()
                    width = new_width
            if 'right' in self.resize_direction:
                width = max(self.minimumWidth(), width + delta.x())
            if 'top' in self.resize_direction:
                new_height = height - delta.y()
                if new_height >= self.minimumHeight():
                    y = geo.y() + delta.y()
                    height = new_height
            if 'bottom' in self.resize_direction:
                height = max(self.minimumHeight(), height + delta.y())
            
            self.setGeometry(x, y, width, height)
            event.accept()
            return
        
        direction = self.get_resize_direction(event.pos())
        self.update_cursor(direction)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            self.resize_direction = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        super().mouseReleaseEvent(event)
    
    def eventFilter(self, obj, event):
        """Forward mouse events from child widgets to dialog for edge detection"""
        from PyQt6.QtCore import QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent
        
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            if not isinstance(event, QMouseEvent):
                return super().eventFilter(obj, event)
            
            # Map event position from child widget to dialog coordinates
            global_pos = obj.mapToGlobal(event.pos())
            local_pos = self.mapFromGlobal(global_pos)
            
            # Check if we're near a resize edge
            direction = self.get_resize_direction(local_pos)
            if direction:
                # Create a new mouse event with coordinates in dialog space
                # Convert QPoint to QPointF for PyQt6 compatibility
                new_event = QMouseEvent(
                    event.type(),
                    QPointF(local_pos),
                    QPointF(global_pos),
                    event.button(),
                    event.buttons(),
                    event.modifiers()
                )
                
                # Forward to dialog's mouse event handlers
                if event.type() == QEvent.Type.MouseButtonPress:
                    self.mousePressEvent(new_event)
                elif event.type() == QEvent.Type.MouseMove:
                    self.mouseMoveEvent(new_event)
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self.mouseReleaseEvent(new_event)
                
                return True  # Event handled, stop propagation
        
        return super().eventFilter(obj, event)


class BrowserTab(QWidget):
    def __init__(self, parent=None, home_url=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        if home_url:
            self.browser.setUrl(QUrl(home_url))
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        self.setLayout(layout)


class ViceCityBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("vicebrowser")
        self.setGeometry(100, 100, 1400, 900)
        
        # Set app icon from assets/icon.png
        icon_path = os.path.join(get_base_path(), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        self.resize_margin = 10
        self.resizing = False
        self.resize_direction = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        
        self.init_database()
        
        # Browser settings with default values
        self.font_size = 16  # pixels
        self.icon_size = 24  # pixels
        self.layout_scale = 100  # percentage
        self.background_image = None  # Custom background image path
        
        self.home_url = self.create_vice_city_homepage()
        self.search_engines = {
            "Google": "https://www.google.com/search?q={}",
            "DuckDuckGo": "https://duckduckgo.com/?q={}",
            "Bing": "https://www.bing.com/search?q={}"
        }
        self.current_search_engine = "Google"
        
        self.init_ui()
        self.apply_vice_city_style()
        
        self.setMouseTracking(True)
        
    def create_vice_city_homepage(self):
        # Get favorites
        favorites = self.get_favorites()
        favorites_html = '<div class="favorites-section"><h2 class="favorites-title">FAVORITES</h2><div class="favorites-grid">'
        
        if favorites and len(favorites) > 0:
            # Show actual favorites (max 8)
            for fav in favorites[:8]:
                fav_id, fav_url, fav_title, fav_favicon = fav[0], fav[1], fav[2], fav[3]
                title = fav_title if fav_title else fav_url
                if len(title) > 30:
                    title = title[:27] + "..."
                # Escape HTML characters in title
                title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
                
                # Add favicon if available
                favicon_html = ""
                if fav_favicon:
                    favicon_html = f'<img src="{fav_favicon}" class="fav-favicon" onerror="this.style.display=\'none\'" />'
                
                favorites_html += f'<a href="{fav_url}" class="favorite-card filled">{favicon_html}<div class="fav-title">{title}</div></a>'
        else:
            # Show 5 empty placeholder boxes with borders (no text)
            for i in range(5):
                favorites_html += '<div class="favorite-card placeholder"></div>'
        
        favorites_html += '</div></div>'
        
        # Load assets/logo.png if exists
        logo_img = ""
        logo_path = os.path.join(get_base_path(), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as f:
                    logo_data = base64.b64encode(f.read()).decode()
                logo_img = f'<img src="data:image/png;base64,{logo_data}" class="logo-img" />'
            except:
                logo_img = '<div class="logo"></div>'
        else:
            logo_img = '<div class="logo"></div>'
        
        # Load custom background image if set
        custom_bg_style = ""
        if self.background_image and os.path.exists(self.background_image):
            try:
                from PyQt6.QtGui import QImage
                from PyQt6.QtCore import QBuffer, QIODevice
                
                # Load image with QImage and convert to PNG for reliable embedding
                image = QImage(self.background_image)
                if not image.isNull():
                    # Convert to PNG format for consistent encoding
                    buffer = QBuffer()
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    image.save(buffer, "PNG")
                    # Convert QByteArray to bytes before base64 encoding
                    bg_data = base64.b64encode(bytes(buffer.data())).decode()
                    buffer.close()
                    
                    custom_bg_style = f"""
                    body::before {{
                        content: '';
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-image: url(data:image/png;base64,{bg_data});
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        opacity: 0.4;
                        z-index: -1;
                    }}
                    """
            except Exception as e:
                custom_bg_style = ""
                print(f"Failed to load background image: {e}")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>vicebrowser</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    background: linear-gradient(135deg, #1a0033 0%, #0d0019 50%, #2d0a4e 100%);
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    font-family: 'Arial Black', sans-serif;
                    overflow-x: hidden;
                    overflow-y: auto;
                    position: relative;
                    padding: 20px;
                }}
                .neon-grid {{
                    position: fixed;
                    width: 100%;
                    height: 100%;
                    background-image: 
                        linear-gradient(rgba(255, 16, 240, 0.1) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255, 16, 240, 0.1) 1px, transparent 1px);
                    background-size: 50px 50px;
                    animation: gridMove 20s linear infinite;
                    z-index: 0;
                }}
                @keyframes gridMove {{
                    0% {{ transform: perspective(500px) rotateX(60deg) translateY(0); }}
                    100% {{ transform: perspective(500px) rotateX(60deg) translateY(50px); }}
                }}
                .logo-container {{
                    z-index: 10;
                    text-align: center;
                    animation: float 3s ease-in-out infinite;
                    margin-bottom: 40px;
                }}
                @keyframes float {{
                    0%, 100% {{ transform: translateY(0px); }}
                    50% {{ transform: translateY(-20px); }}
                }}
                .logo {{
                    font-size: 120px;
                    margin-bottom: 20px;
                    text-shadow: 0 0 20px rgba(255, 16, 240, 0.8);
                }}
                .logo-img {{
                    max-width: 350px;
                    max-height: 350px;
                    margin-bottom: 20px;
                    filter: drop-shadow(0 0 20px rgba(255, 16, 240, 0.8));
                    border-radius: 15px;
                }}
                h1 {{
                    font-size: 72px;
                    background: linear-gradient(45deg, #ff10f0, #00ffff, #ff10f0);
                    background-size: 200% auto;
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    animation: gradient 3s linear infinite;
                    margin-bottom: 20px;
                    letter-spacing: 8px;
                }}
                @keyframes gradient {{
                    0% {{ background-position: 0% 50%; }}
                    50% {{ background-position: 100% 50%; }}
                    100% {{ background-position: 0% 50%; }}
                }}
                .tagline {{
                    font-size: 24px;
                    color: #00ffff;
                    text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
                    margin-bottom: 40px;
                    letter-spacing: 4px;
                }}
                .search-container {{
                    z-index: 10;
                    max-width: 700px;
                    width: 100%;
                    margin-bottom: 50px;
                }}
                .search-form {{
                    display: flex;
                    gap: 10px;
                    background: linear-gradient(135deg, rgba(61, 10, 94, 0.8), rgba(45, 10, 78, 0.8));
                    padding: 15px;
                    border-radius: 50px;
                    border: 2px solid #ff10f0;
                    box-shadow: 0 0 20px rgba(255, 16, 240, 0.5);
                }}
                .search-input {{
                    flex: 1;
                    background: rgba(26, 26, 46, 0.8);
                    color: #00ffff;
                    border: 2px solid #ff10f0;
                    border-radius: 25px;
                    padding: 12px 20px;
                    font-size: 16px;
                    font-family: 'Courier New', monospace;
                    outline: none;
                }}
                .search-input:focus {{
                    border-color: #00ffff;
                    box-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
                }}
                .search-input::placeholder {{
                    color: rgba(0, 255, 255, 0.5);
                }}
                .search-select {{
                    background: rgba(26, 26, 46, 0.8);
                    color: #ff69ff;
                    border: 2px solid #ff10f0;
                    border-radius: 25px;
                    padding: 12px 15px;
                    font-size: 14px;
                    font-weight: bold;
                    outline: none;
                    cursor: pointer;
                }}
                .search-button {{
                    background: linear-gradient(135deg, #ff10f0, #8b008b);
                    color: #ffffff;
                    border: 2px solid #ff69ff;
                    border-radius: 25px;
                    padding: 12px 30px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }}
                .search-button:hover {{
                    background: linear-gradient(135deg, #00ffff, #0088ff);
                    border-color: #00ffff;
                    transform: scale(1.05);
                }}
                .sun {{
                    position: fixed;
                    top: 10%;
                    width: 300px;
                    height: 300px;
                    background: linear-gradient(180deg, #ff6b9d 0%, #ffa500 100%);
                    border-radius: 50%;
                    box-shadow: 0 0 100px rgba(255, 107, 157, 0.6);
                    z-index: 1;
                }}
                .palm-trees {{
                    position: fixed;
                    bottom: 20px;
                    font-size: 80px;
                    opacity: 0.3;
                    z-index: 5;
                }}
                .palm-left {{ left: 50px; }}
                .palm-right {{ right: 50px; }}
                .favorites-section {{
                    z-index: 10;
                    max-width: 900px;
                    width: 100%;
                }}
                .favorites-title {{
                    font-size: 20px;
                    color: #ff10f0;
                    text-shadow: 0 0 15px rgba(255, 16, 240, 0.8);
                    margin-bottom: 30px;
                    text-align: center;
                    letter-spacing: 3px;
                }}
                .favorites-grid {{
                    display: grid;
                    grid-template-columns: repeat(5, 1fr);
                    gap: 20px;
                    padding: 20px;
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                @media (max-width: 1200px) {{
                    .favorites-grid {{
                        grid-template-columns: repeat(4, 1fr);
                    }}
                }}
                @media (max-width: 900px) {{
                    .favorites-grid {{
                        grid-template-columns: repeat(3, 1fr);
                    }}
                }}
                @media (max-width: 600px) {{
                    .favorites-grid {{
                        grid-template-columns: repeat(2, 1fr);
                    }}
                }}
                .favorite-card {{
                    border: 2px solid #ff10f0;
                    border-radius: 15px;
                    padding: 20px;
                    text-align: center;
                    transition: all 0.3s ease;
                    text-decoration: none;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    gap: 10px;
                    min-height: 150px;
                }}
                .favorite-card.filled {{
                    background: linear-gradient(135deg, rgba(61, 10, 94, 0.8), rgba(45, 10, 78, 0.8));
                    cursor: pointer;
                }}
                .favorite-card.placeholder {{
                    background: linear-gradient(135deg, rgba(61, 10, 94, 0.3), rgba(45, 10, 78, 0.3));
                    border-style: dashed;
                    border-color: rgba(255, 16, 240, 0.4);
                }}
                .favorite-card.filled:hover {{
                    transform: translateY(-5px);
                    box-shadow: 0 10px 30px rgba(255, 16, 240, 0.5);
                    border-color: #00ffff;
                }}
                .favorite-card.placeholder .fav-icon {{
                    font-size: 48px;
                    color: rgba(255, 16, 240, 0.5);
                    text-shadow: none;
                }}
                .favorite-card.placeholder .fav-title {{
                    font-size: 14px;
                    color: rgba(0, 255, 255, 0.5);
                    text-shadow: none;
                }}
                .favorite-card.filled .fav-icon {{
                    font-size: 48px;
                    color: #ffd700;
                    text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
                }}
                .favorite-card.filled .fav-title {{
                    font-size: 14px;
                    color: #00ffff;
                    font-family: Arial, sans-serif;
                    word-wrap: break-word;
                    text-shadow: 0 0 5px rgba(0, 255, 255, 0.5);
                }}
                .fav-favicon {{
                    width: 32px;
                    height: 32px;
                    object-fit: contain;
                    margin-bottom: 5px;
                    border-radius: 4px;
                }}
                {custom_bg_style}
            </style>
        </head>
        <body>
            <div class="neon-grid"></div>
            <div class="sun"></div>
            <div class="palm-trees palm-left"></div>
            <div class="palm-trees palm-right"></div>
            <div class="logo-container">
                {logo_img}
            </div>
            <div class="search-container">
                <form class="search-form" onsubmit="event.preventDefault(); performSearch();">
                    <select class="search-select" id="searchEngine">
                        <option value="Google">Google</option>
                        <option value="DuckDuckGo">DuckDuckGo</option>
                        <option value="Bing">Bing</option>
                    </select>
                    <input type="text" class="search-input" id="searchInput" placeholder="Search or enter URL..." autocomplete="off">
                    <button type="submit" class="search-button">GO</button>
                </form>
            </div>
            <script>
                function performSearch() {{
                    const input = document.getElementById('searchInput').value.trim();
                    const engine = document.getElementById('searchEngine').value;
                    if (!input) return;
                    
                    // Check if input is a URL (matches Python is_url logic)
                    const hasSpace = input.includes(' ');
                    const hasDot = input.includes('.') && !input.startsWith('.') && !input.endsWith('.');
                    const hasScheme = input.startsWith('http://') || input.startsWith('https://') || 
                                     input.startsWith('file://') || input.startsWith('ftp://');
                    
                    const isUrl = hasScheme || (hasDot && !hasSpace);
                    
                    if (isUrl) {{
                        const url = hasScheme ? input : 'https://' + input;
                        window.location.href = url;
                    }} else {{
                        const searchUrls = {{
                            'Google': 'https://www.google.com/search?q=',
                            'DuckDuckGo': 'https://duckduckgo.com/?q=',
                            'Bing': 'https://www.bing.com/search?q='
                        }};
                        window.location.href = searchUrls[engine] + encodeURIComponent(input);
                    }}
                }}
            </script>
            {favorites_html}
        </body>
        </html>
        """
        return "data:text/html;charset=utf-8," + urllib.parse.quote(html)
    
    def load_svg_icon(self, svg_filename):
        """Load an SVG icon from assets/ folder, make it white, and return a QIcon"""
        return load_svg_icon(svg_filename)
    
    def init_database(self):
        import platform
        if platform.system() == "Windows":
            data_dir = os.path.expandvars("%APPDATA%\\vicebrowser")
        else:
            data_dir = os.path.expanduser("~/.vicebrowser")
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        db_path = os.path.join(data_dir, "browser_history.db")
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                favicon TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Add favicon column if it doesn't exist
        try:
            self.cursor.execute('SELECT favicon FROM favorites LIMIT 1')
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            self.cursor.execute('ALTER TABLE favorites ADD COLUMN favicon TEXT')
        
        self.conn.commit()
        
    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        navbar = QToolBar("Navigation")
        navbar.setMovable(False)
        navbar.setObjectName("navbar")
        navbar.setIconSize(QSize(24, 24))
        
        back_btn = QPushButton()
        back_icon = self.load_svg_icon("back.svg")
        if back_icon:
            back_btn.setIcon(back_icon)
            back_btn.setIconSize(QSize(24, 24))
        else:
            back_btn.setText("◄")
        back_btn.setObjectName("iconButton")
        back_btn.setToolTip("Back")
        back_btn.setFixedSize(45, 45)
        back_btn.clicked.connect(self.navigate_back)
        navbar.addWidget(back_btn)
        
        forward_btn = QPushButton()
        forward_icon = self.load_svg_icon("next.svg")
        if forward_icon:
            forward_btn.setIcon(forward_icon)
            forward_btn.setIconSize(QSize(24, 24))
        else:
            forward_btn.setText("►")
        forward_btn.setObjectName("iconButton")
        forward_btn.setToolTip("Forward")
        forward_btn.setFixedSize(45, 45)
        forward_btn.clicked.connect(self.navigate_forward)
        navbar.addWidget(forward_btn)
        
        reload_btn = QPushButton()
        reload_icon = self.load_svg_icon("refresh.svg")
        if reload_icon:
            reload_btn.setIcon(reload_icon)
            reload_btn.setIconSize(QSize(24, 24))
        else:
            reload_btn.setText("↻")
        reload_btn.setObjectName("iconButton")
        reload_btn.setToolTip("Reload")
        reload_btn.setFixedSize(45, 45)
        reload_btn.clicked.connect(self.reload_page)
        navbar.addWidget(reload_btn)
        
        home_btn = QPushButton()
        home_icon = self.load_svg_icon("home.svg")
        if home_icon:
            home_btn.setIcon(home_icon)
            home_btn.setIconSize(QSize(24, 24))
        else:
            home_btn.setText("⌂")
        home_btn.setObjectName("iconButton")
        home_btn.setToolTip("Home")
        home_btn.setFixedSize(45, 45)
        home_btn.clicked.connect(self.navigate_home)
        navbar.addWidget(home_btn)
        
        navbar.addSeparator()
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL or search...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.url_bar.setObjectName("urlBar")
        self.url_bar.setMinimumWidth(400)
        self.url_bar.setFixedHeight(45)
        navbar.addWidget(self.url_bar)
        
        self.search_engine_combo = QComboBox()
        self.search_engine_combo.addItem("Google", "Google")
        self.search_engine_combo.addItem("DuckDuckGo", "DuckDuckGo")
        self.search_engine_combo.addItem("Bing", "Bing")
        self.search_engine_combo.setCurrentIndex(0)
        self.search_engine_combo.currentTextChanged.connect(self.change_search_engine)
        self.search_engine_combo.setObjectName("searchEngineCombo")
        self.search_engine_combo.setFixedSize(105, 35)
        navbar.addWidget(self.search_engine_combo)
        
        navbar.addSeparator()
        
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setObjectName("zoomControlBtn")
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.setFixedSize(32, 32)
        zoom_out_btn.clicked.connect(self.zoom_out)
        navbar.addWidget(zoom_out_btn)
        
        zoom_reset_btn = QPushButton("100%")
        zoom_reset_btn.setObjectName("zoomButton")
        zoom_reset_btn.setToolTip("Reset Zoom")
        zoom_reset_btn.setFixedSize(45, 32)
        zoom_reset_btn.clicked.connect(self.zoom_reset)
        navbar.addWidget(zoom_reset_btn)
        self.zoom_reset_btn = zoom_reset_btn
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setObjectName("zoomControlBtn")
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.setFixedSize(32, 32)
        zoom_in_btn.clicked.connect(self.zoom_in)
        navbar.addWidget(zoom_in_btn)
        
        navbar.addSeparator()
        
        self.favorite_btn = QPushButton()
        self.favorite_btn.setObjectName("iconButton")
        self.favorite_btn.setToolTip("Add/Remove Favorite")
        self.favorite_btn.setFixedSize(45, 45)
        self.favorite_btn.clicked.connect(self.toggle_favorite)
        navbar.addWidget(self.favorite_btn)
        
        settings_btn = QPushButton()
        settings_icon = self.load_svg_icon("settings.svg")
        if settings_icon:
            settings_btn.setIcon(settings_icon)
            settings_btn.setIconSize(QSize(24, 24))
        else:
            settings_btn.setText("S")
        settings_btn.setObjectName("iconButton")
        settings_btn.setToolTip("Settings")
        settings_btn.setFixedSize(45, 45)
        settings_btn.clicked.connect(self.show_settings_menu)
        navbar.addWidget(settings_btn)
        self.settings_btn = settings_btn
        
        main_layout.addWidget(navbar)
        
        tabs_container = QWidget()
        tabs_container.setObjectName("tabsContainer")
        tabs_container_layout = QHBoxLayout()
        tabs_container_layout.setContentsMargins(0, 0, 0, 0)
        tabs_container_layout.setSpacing(0)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        tabs_container_layout.addWidget(self.tabs, 1)  # Stretch factor 1
        
        new_tab_btn = QPushButton("+")
        new_tab_btn.setObjectName("newTabButton")
        new_tab_btn.setFixedSize(40, 40)
        new_tab_btn.clicked.connect(lambda: self.add_new_tab())
        new_tab_btn.setToolTip("New Tab")
        tabs_container_layout.addWidget(new_tab_btn, 0, Qt.AlignmentFlag.AlignTop)  # No stretch
        
        tabs_container.setLayout(tabs_container_layout)
        main_layout.addWidget(tabs_container, 1)  # Stretch factor 1
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Install event filters to forward mouse events to main window for edge detection
        central_widget.installEventFilter(self)
        self.tabs.installEventFilter(self)
        
        self.add_new_tab(QUrl(self.home_url))
        
        # Update favorite icon after first tab is loaded
        self.update_favorite_icon()
        
    def add_new_tab(self, qurl=None):
        if qurl is None:
            qurl = QUrl(self.home_url)
            
        browser_tab = BrowserTab(home_url=qurl.toString())
        browser = browser_tab.browser
            
        i = self.tabs.addTab(browser_tab, "New Tab")
        self.tabs.setCurrentIndex(i)
        
        # Set custom close button icon for this tab
        self.set_tab_close_icon(i)
        
        # Install event filter on the browser tab and web view for edge detection
        browser_tab.installEventFilter(self)
        browser.installEventFilter(self)
        
        # Set initial zoom level to 90% for the homepage
        if qurl.toString() == self.home_url:
            browser.setZoomFactor(0.9)
        else:
            browser.setZoomFactor(1.0)
        
        browser.urlChanged.connect(lambda qurl, browser=browser: 
                                   self.update_urlbar(qurl, browser))
        browser.loadFinished.connect(lambda _, i=i, browser=browser:
                                    self.update_tab_title(i, browser))
        browser.loadFinished.connect(lambda _, browser=browser:
                                    self.save_to_history(browser))
        
        # Update zoom display
        self.update_zoom_display()
        
    def close_tab(self, i):
        if self.tabs.count() < 2:
            # If closing the last tab, open startpage instead
            self.current_browser().setUrl(QUrl(self.home_url))
            self.current_browser().setZoomFactor(0.9)
            return
        self.tabs.removeTab(i)
        
    def on_tab_changed(self, i):
        if i >= 0:
            qurl = self.current_browser().url()
            self.update_urlbar(qurl, self.current_browser())
            self.update_zoom_display()
            self.update_favorite_icon()
            
    def current_browser(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            return current_tab.browser
        return None
        
    def navigate_back(self):
        browser = self.current_browser()
        if browser:
            browser.back()
            
    def navigate_forward(self):
        browser = self.current_browser()
        if browser:
            browser.forward()
            
    def reload_page(self):
        browser = self.current_browser()
        if browser:
            browser.reload()
            
    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl(self.home_url))
            # Reset zoom to 90% for homepage
            browser.setZoomFactor(0.9)
            self.update_zoom_display()
    
    def zoom_in(self):
        browser = self.current_browser()
        if browser:
            current_zoom = browser.zoomFactor()
            new_zoom = min(current_zoom + 0.1, 3.0)  # Max 300%
            browser.setZoomFactor(new_zoom)
            self.update_zoom_display()
    
    def zoom_out(self):
        browser = self.current_browser()
        if browser:
            current_zoom = browser.zoomFactor()
            new_zoom = max(current_zoom - 0.1, 0.25)  # Min 25%
            browser.setZoomFactor(new_zoom)
            self.update_zoom_display()
    
    def zoom_reset(self):
        browser = self.current_browser()
        if browser:
            browser.setZoomFactor(1.0)
            self.update_zoom_display()
    
    def update_zoom_display(self):
        browser = self.current_browser()
        if browser:
            zoom_percent = int(browser.zoomFactor() * 100)
            self.zoom_reset_btn.setText(f"{zoom_percent}%")
            
    def navigate_to_url(self):
        browser = self.current_browser()
        if not browser:
            return
            
        text = self.url_bar.text().strip()
        
        if not text:
            return
            
        if self.is_url(text):
            if not text.startswith(('http://', 'https://')):
                text = 'https://' + text
            url = QUrl(text)
        else:
            search_url = self.search_engines[self.current_search_engine].format(text)
            url = QUrl(search_url)
            
        browser.setUrl(url)
        
    def is_url(self, text):
        if ' ' in text:
            return False
        if '.' in text and not text.startswith('.') and not text.endswith('.'):
            return True
        if text.startswith(('http://', 'https://', 'file://', 'ftp://')):
            return True
        return False
        
    def update_urlbar(self, qurl, browser=None):
        if browser != self.current_browser():
            return
        url_string = qurl.toString()
        if url_string.startswith("data:text/html"):
            self.url_bar.clear()
        else:
            self.url_bar.setText(url_string)
        # Update favorite icon when URL changes
        self.update_favorite_icon()
        
    def update_tab_title(self, i, browser):
        title = browser.page().title()
        if len(title) > 20:
            title = title[:20] + "..."
        self.tabs.setTabText(i, title)
    
    def set_tab_close_icon(self, index):
        """Set custom x.svg icon for tab close button"""
        from PyQt6.QtWidgets import QAbstractButton
        tab_bar = self.tabs.tabBar()
        close_button = tab_bar.tabButton(index, tab_bar.ButtonPosition.RightSide)
        if not close_button:
            close_button = tab_bar.tabButton(index, tab_bar.ButtonPosition.LeftSide)
        
        if close_button and isinstance(close_button, QAbstractButton):
            close_icon = load_svg_icon("x.svg")
            if close_icon:
                close_button.setIcon(close_icon)
                close_button.setIconSize(QSize(14, 14))
                close_button.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                        padding: 2px;
                    }
                    QPushButton:hover {
                        background: rgba(255, 16, 240, 0.3);
                        border-radius: 3px;
                    }
                """)
        
    def change_search_engine(self, engine_text):
        # Extract engine name from the text (remove emoji)
        if "Google" in engine_text:
            self.current_search_engine = "Google"
        elif "DuckDuckGo" in engine_text:
            self.current_search_engine = "DuckDuckGo"
        elif "Bing" in engine_text:
            self.current_search_engine = "Bing"
        
    def save_to_history(self, browser):
        url = browser.url().toString()
        title = browser.page().title()
        
        if url and url not in ['about:blank', '']:
            self.cursor.execute(
                'INSERT INTO history (url, title) VALUES (?, ?)',
                (url, title)
            )
            self.conn.commit()
            
    def get_favorites(self):
        self.cursor.execute('SELECT id, url, title, favicon FROM favorites ORDER BY timestamp DESC')
        return self.cursor.fetchall()
    
    def add_favorite(self, url, title, favicon=None):
        try:
            self.cursor.execute(
                'INSERT INTO favorites (url, title, favicon) VALUES (?, ?, ?)',
                (url, title, favicon)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_favorite(self, url):
        self.cursor.execute('DELETE FROM favorites WHERE url = ?', (url,))
        self.conn.commit()
    
    def is_favorite(self, url):
        self.cursor.execute('SELECT COUNT(*) FROM favorites WHERE url = ?', (url,))
        return self.cursor.fetchone()[0] > 0
    
    def update_favorite_icon(self):
        """Update the favorite button icon based on whether current page is favorited"""
        browser = self.current_browser()
        if not browser:
            # Default to add_star icon if no browser
            icon = self.load_svg_icon("add_star.svg")
            if icon:
                self.favorite_btn.setIcon(icon)
                self.favorite_btn.setIconSize(QSize(24, 24))
            else:
                self.favorite_btn.setText("")
            return
        
        url = browser.url().toString()
        
        # Check if page is favorited
        if url and url not in ['about:blank', ''] and not url.startswith("data:text/html"):
            if self.is_favorite(url):
                # Show filled star icon
                icon = self.load_svg_icon("star.svg")
                if icon:
                    self.favorite_btn.setIcon(icon)
                    self.favorite_btn.setIconSize(QSize(24, 24))
                    self.favorite_btn.setText("")
                else:
                    self.favorite_btn.setText("")
            else:
                # Show add star icon
                icon = self.load_svg_icon("add_star.svg")
                if icon:
                    self.favorite_btn.setIcon(icon)
                    self.favorite_btn.setIconSize(QSize(24, 24))
                    self.favorite_btn.setText("")
                else:
                    self.favorite_btn.setText("☆")
        else:
            # Default to add_star for special pages
            icon = self.load_svg_icon("add_star.svg")
            if icon:
                self.favorite_btn.setIcon(icon)
                self.favorite_btn.setIconSize(QSize(24, 24))
                self.favorite_btn.setText("")
            else:
                self.favorite_btn.setText("☆")
    
    def toggle_favorite(self):
        browser = self.current_browser()
        if not browser:
            return
        
        url = browser.url().toString()
        title = browser.page().title()
        
        if not url or url in ['about:blank', ''] or url.startswith("data:text/html"):
            QMessageBox.warning(self, "Favorite", "Cannot favorite this page!")
            return
        
        if self.is_favorite(url):
            self.remove_favorite(url)
            QMessageBox.information(self, "Favorite", "Removed from favorites!")
            self.refresh_homepage()
            self.update_favorite_icon()
        else:
            # Get favicon URL
            favicon_url = browser.iconUrl().toString() if browser.iconUrl() else None
            if self.add_favorite(url, title, favicon_url):
                QMessageBox.information(self, "Favorite", "Added to favorites!")
                self.refresh_homepage()
                self.update_favorite_icon()
            else:
                QMessageBox.warning(self, "Favorite", "Already in favorites!")
    
    def refresh_homepage(self):
        self.home_url = self.create_vice_city_homepage()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab and hasattr(tab, 'browser'):
                current_url = tab.browser.url().toString()
                if current_url.startswith("data:text/html"):
                    tab.browser.setUrl(QUrl(self.home_url))
    
    def show_history(self):
        self.cursor.execute('SELECT id, url, title, timestamp FROM history ORDER BY timestamp DESC LIMIT 100')
        history = self.cursor.fetchall()
        
        if not history:
            QMessageBox.information(self, "History", "No browsing history yet!")
            return
        
        dialog = FramelessDialog(self, title="Browsing History")
        dialog.setMinimumSize(800, 500)
        dialog.setStyleSheet("""
            FramelessDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #1a0033, stop:1 #0d0019);
                border: 2px solid #ff10f0;
            }
            QWidget#historyItem {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #3d0a5e, stop:1 #2d0a4e);
                border: 2px solid #ff10f0;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton#actionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
                color: #ffffff;
                border: 2px solid #ff69ff;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 11px;
                min-width: 80px;
            }
            QPushButton#actionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #00ffff, stop:1 #0088ff);
                border: 2px solid #00ffff;
            }
            QPushButton#deleteBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff0000, stop:1 #8b0000);
                color: #ffffff;
                border: 2px solid #ff4444;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 11px;
                min-width: 80px;
            }
            QPushButton#deleteBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff4444, stop:1 #ff0000);
                border: 2px solid #ff6666;
            }
            QLabel#historyTitle {
                color: #00ffff;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#historyUrl {
                color: #ff69ff;
                font-size: 11px;
            }
            QLabel#historyTime {
                color: #ffa500;
                font-size: 10px;
            }
            QLabel {
                color: #ff10f0;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QScrollArea {
                border: 2px solid #ff10f0;
                border-radius: 8px;
                background: transparent;
            }
            QPushButton#closeBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
                color: #ffffff;
                border: 2px solid #ff69ff;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#closeBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #00ffff, stop:1 #0088ff);
                border: 2px solid #00ffff;
            }
        """)
        
        title_label = QLabel("BROWSING HISTORY")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.content_layout.addWidget(title_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(10)
        
        def refresh_list():
            # Clear existing items
            for i in reversed(range(scroll_layout.count())):
                item = scroll_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            # Reload history
            self.cursor.execute('SELECT id, url, title, timestamp FROM history ORDER BY timestamp DESC LIMIT 100')
            updated_history = self.cursor.fetchall()
            if not updated_history:
                dialog.close()
                QMessageBox.information(self, "History", "No more history entries!")
                return
            
            # Rebuild list
            for hist_id, url, title, timestamp in updated_history:
                item_widget = QWidget()
                item_widget.setObjectName("historyItem")
                item_layout = QHBoxLayout()
                item_layout.setContentsMargins(10, 10, 10, 10)
                
                # Info section
                info_layout = QVBoxLayout()
                display_title = title or 'Untitled'
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."
                display_url = url
                if len(display_url) > 60:
                    display_url = display_url[:57] + "..."
                
                time_label = QLabel(f"{timestamp}")
                time_label.setObjectName("historyTime")
                title_label = QLabel(f"{display_title}")
                title_label.setObjectName("historyTitle")
                url_label = QLabel(f"{display_url}")
                url_label.setObjectName("historyUrl")
                
                info_layout.addWidget(time_label)
                info_layout.addWidget(title_label)
                info_layout.addWidget(url_label)
                item_layout.addLayout(info_layout, 1)
                
                # Buttons section
                buttons_layout = QHBoxLayout()
                buttons_layout.setSpacing(5)
                
                open_btn = QPushButton("OPEN")
                open_btn.setObjectName("actionBtn")
                open_btn.clicked.connect(lambda checked, u=url: (self.add_new_tab(QUrl(u)), dialog.close()))
                buttons_layout.addWidget(open_btn)
                
                delete_btn = QPushButton()
                delete_icon = load_svg_icon("x.svg")
                if delete_icon:
                    delete_btn.setIcon(delete_icon)
                    delete_btn.setIconSize(QSize(16, 16))
                else:
                    delete_btn.setText("DELETE")
                delete_btn.setObjectName("deleteBtn")
                delete_btn.setToolTip("Delete")
                delete_btn.clicked.connect(lambda checked, hid=hist_id: self.delete_history_and_refresh(hid, refresh_list))
                buttons_layout.addWidget(delete_btn)
                
                item_layout.addLayout(buttons_layout)
                item_widget.setLayout(item_layout)
                scroll_layout.addWidget(item_widget)
            
            scroll_layout.addStretch()
            
            # Reinstall event filters on all dynamically created widgets
            dialog.install_filters_recursively(scroll_widget)
        
        refresh_list()
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        dialog.content_layout.addWidget(scroll)
        
        # Clear history buttons
        clear_buttons_layout = QHBoxLayout()
        clear_buttons_layout.setSpacing(10)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setObjectName("deleteBtn")
        clear_all_btn.clicked.connect(lambda: self.clear_history_dialog("all", dialog, refresh_list))
        clear_buttons_layout.addWidget(clear_all_btn)
        
        clear_recent_btn = QPushButton("Clear Recent (24h)")
        clear_recent_btn.setObjectName("deleteBtn")
        clear_recent_btn.clicked.connect(lambda: self.clear_history_dialog("recent", dialog, refresh_list))
        clear_buttons_layout.addWidget(clear_recent_btn)
        
        clear_week_btn = QPushButton("Clear Last Week")
        clear_week_btn.setObjectName("deleteBtn")
        clear_week_btn.clicked.connect(lambda: self.clear_history_dialog("week", dialog, refresh_list))
        clear_buttons_layout.addWidget(clear_week_btn)
        
        dialog.content_layout.addLayout(clear_buttons_layout)
        
        close_btn = QPushButton()
        close_icon = load_svg_icon("x.svg")
        if close_icon:
            close_btn.setIcon(close_icon)
            close_btn.setIconSize(QSize(20, 20))
        else:
            close_btn.setText("CLOSE")
        close_btn.setObjectName("closeBtn")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(dialog.close)
        dialog.content_layout.addWidget(close_btn)
        
        # Install event filters recursively on all children for edge detection
        dialog.install_filters_recursively(dialog.content_widget)
        
        dialog.exec()
    
    def delete_history_and_refresh(self, history_id, refresh_callback):
        reply = QMessageBox.question(self, "Delete History Entry", 
                                    "Are you sure you want to delete this history entry?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.cursor.execute('DELETE FROM history WHERE id = ?', (history_id,))
            self.conn.commit()
            refresh_callback()
    
    def clear_history_dialog(self, clear_type, dialog, refresh_callback):
        from datetime import datetime, timedelta
        
        if clear_type == "all":
            message = "Are you sure you want to clear all browsing history?"
            title = "Clear All History"
        elif clear_type == "recent":
            message = "Are you sure you want to clear history from the last 24 hours?"
            title = "Clear Recent History"
        elif clear_type == "week":
            message = "Are you sure you want to clear history from the last week?"
            title = "Clear Last Week History"
        else:
            return
        
        reply = QMessageBox.question(self, title, message,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if clear_type == "all":
                self.cursor.execute('DELETE FROM history')
            elif clear_type == "recent":
                # Delete last 24 hours
                cutoff = datetime.now() - timedelta(days=1)
                cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute('DELETE FROM history WHERE timestamp >= ?', (cutoff_str,))
            elif clear_type == "week":
                # Delete last 7 days
                cutoff = datetime.now() - timedelta(days=7)
                cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute('DELETE FROM history WHERE timestamp >= ?', (cutoff_str,))
            
            self.conn.commit()
            QMessageBox.information(self, "History Cleared", "Selected history has been cleared.")
            refresh_callback()
    
    def show_favorites(self):
        favorites = self.get_favorites()
        
        if not favorites:
            QMessageBox.information(self, "Starred Pages", "No starred pages yet!")
            return
        
        dialog = FramelessDialog(self, title="Starred Pages")
        dialog.setMinimumSize(800, 500)
        dialog.setStyleSheet("""
            FramelessDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #1a0033, stop:1 #0d0019);
                border: 2px solid #ff10f0;
            }
            QWidget#favItem {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #3d0a5e, stop:1 #2d0a4e);
                border: 2px solid #ff10f0;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton#actionBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
                color: #ffffff;
                border: 2px solid #ff69ff;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 11px;
                min-width: 80px;
            }
            QPushButton#actionBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #00ffff, stop:1 #0088ff);
                border: 2px solid #00ffff;
            }
            QPushButton#deleteBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff0000, stop:1 #8b0000);
                color: #ffffff;
                border: 2px solid #ff4444;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 11px;
                min-width: 80px;
            }
            QPushButton#deleteBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff4444, stop:1 #ff0000);
                border: 2px solid #ff6666;
            }
            QLabel#favTitle {
                color: #00ffff;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#favUrl {
                color: #ff69ff;
                font-size: 11px;
            }
            QLabel {
                color: #ff10f0;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QScrollArea {
                border: 2px solid #ff10f0;
                border-radius: 8px;
                background: transparent;
            }
            QPushButton#closeBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
                color: #ffffff;
                border: 2px solid #ff69ff;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#closeBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #00ffff, stop:1 #0088ff);
                border: 2px solid #00ffff;
            }
        """)
        
        title_label = QLabel("STARRED PAGES")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog.content_layout.addWidget(title_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(10)
        
        def refresh_list():
            # Clear existing items
            for i in reversed(range(scroll_layout.count())):
                item = scroll_layout.itemAt(i)
                if item.widget():
                    item.widget().deleteLater()
            
            # Reload favorites
            updated_favorites = self.get_favorites()
            if not updated_favorites:
                dialog.close()
                QMessageBox.information(self, "Starred Pages", "No more starred pages!")
                return
            
            # Rebuild list
            for fav_id, url, title, favicon in updated_favorites:
                item_widget = QWidget()
                item_widget.setObjectName("favItem")
                item_layout = QHBoxLayout()
                item_layout.setContentsMargins(10, 10, 10, 10)
                
                # Info section
                info_layout = QVBoxLayout()
                display_title = title or 'Untitled'
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."
                display_url = url
                if len(display_url) > 60:
                    display_url = display_url[:57] + "..."
                
                title_label = QLabel(f"{display_title}")
                title_label.setObjectName("favTitle")
                url_label = QLabel(f"{display_url}")
                url_label.setObjectName("favUrl")
                
                info_layout.addWidget(title_label)
                info_layout.addWidget(url_label)
                item_layout.addLayout(info_layout, 1)
                
                # Buttons section
                buttons_layout = QHBoxLayout()
                buttons_layout.setSpacing(5)
                
                open_btn = QPushButton("OPEN")
                open_btn.setObjectName("actionBtn")
                open_btn.clicked.connect(lambda checked, u=url: (self.add_new_tab(QUrl(u)), dialog.close()))
                buttons_layout.addWidget(open_btn)
                
                delete_btn = QPushButton()
                delete_icon = load_svg_icon("x.svg")
                if delete_icon:
                    delete_btn.setIcon(delete_icon)
                    delete_btn.setIconSize(QSize(16, 16))
                else:
                    delete_btn.setText("DELETE")
                delete_btn.setObjectName("deleteBtn")
                delete_btn.setToolTip("Delete")
                delete_btn.clicked.connect(lambda checked, fav_url=url: self.delete_favorite_and_refresh(fav_url, refresh_list))
                buttons_layout.addWidget(delete_btn)
                
                item_layout.addLayout(buttons_layout)
                item_widget.setLayout(item_layout)
                scroll_layout.addWidget(item_widget)
            
            scroll_layout.addStretch()
            
            # Reinstall event filters on all dynamically created widgets
            dialog.install_filters_recursively(scroll_widget)
        
        refresh_list()
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        dialog.content_layout.addWidget(scroll)
        
        close_btn = QPushButton()
        close_icon = load_svg_icon("x.svg")
        if close_icon:
            close_btn.setIcon(close_icon)
            close_btn.setIconSize(QSize(20, 20))
        else:
            close_btn.setText("CLOSE")
        close_btn.setObjectName("closeBtn")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(dialog.close)
        dialog.content_layout.addWidget(close_btn)
        
        # Install event filters recursively on all children for edge detection
        dialog.install_filters_recursively(dialog.content_widget)
        
        dialog.exec()
    
    def delete_favorite_and_refresh(self, url, refresh_callback):
        reply = QMessageBox.question(self, "Delete Favorite", 
                                    "Are you sure you want to delete this favorite?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_favorite(url)
            self.refresh_homepage()
            refresh_callback()
    
    def show_browser_settings(self):
        from PyQt6.QtWidgets import QSpinBox, QSlider
        
        dialog = FramelessDialog(self, "Browser Settings")
        dialog.resize(500, 400)
        
        # Font size setting
        font_label = QLabel("Font Size (px):")
        font_label.setStyleSheet("color: #00ffff; font-size: 16px; font-weight: bold;")
        font_spin = QSpinBox()
        font_spin.setRange(10, 32)
        font_spin.setValue(self.font_size)
        font_spin.setStyleSheet("""
            QSpinBox {
                background: #2d0a4e;
                color: #00ffff;
                border: 2px solid #ff10f0;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }
        """)
        
        # Icon size setting
        icon_label = QLabel("Icon Size (px):")
        icon_label.setStyleSheet("color: #00ffff; font-size: 16px; font-weight: bold;")
        icon_spin = QSpinBox()
        icon_spin.setRange(16, 48)
        icon_spin.setValue(self.icon_size)
        icon_spin.setStyleSheet("""
            QSpinBox {
                background: #2d0a4e;
                color: #00ffff;
                border: 2px solid #ff10f0;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
            }
        """)
        
        # Layout scale setting
        scale_label = QLabel("Layout Scale (%):")
        scale_label.setStyleSheet("color: #00ffff; font-size: 16px; font-weight: bold;")
        scale_slider = QSlider(Qt.Orientation.Horizontal)
        scale_slider.setRange(75, 150)
        scale_slider.setValue(self.layout_scale)
        scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        scale_slider.setTickInterval(25)
        scale_value_label = QLabel(f"{self.layout_scale}%")
        scale_value_label.setStyleSheet("color: #ff69ff; font-size: 14px; font-weight: bold;")
        scale_slider.valueChanged.connect(lambda v: scale_value_label.setText(f"{v}%"))
        scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2d0a4e;
                height: 8px;
                border-radius: 4px;
                border: 2px solid #ff10f0;
            }
            QSlider::handle:horizontal {
                background: #ff10f0;
                width: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
        """)
        
        # Add widgets to dialog
        dialog.content_layout.addWidget(font_label)
        dialog.content_layout.addWidget(font_spin)
        dialog.content_layout.addSpacing(10)
        
        dialog.content_layout.addWidget(icon_label)
        dialog.content_layout.addWidget(icon_spin)
        dialog.content_layout.addSpacing(10)
        
        dialog.content_layout.addWidget(scale_label)
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(scale_slider, 1)
        scale_layout.addWidget(scale_value_label)
        dialog.content_layout.addLayout(scale_layout)
        dialog.content_layout.addSpacing(10)
        
        # Background image setting
        bg_label = QLabel("Background Image:")
        bg_label.setStyleSheet("color: #00ffff; font-size: 16px; font-weight: bold;")
        dialog.content_layout.addWidget(bg_label)
        
        bg_buttons_layout = QHBoxLayout()
        
        bg_status_label = QLabel("Default" if not self.background_image else os.path.basename(self.background_image))
        bg_status_label.setStyleSheet("color: #ff69ff; font-size: 14px;")
        bg_buttons_layout.addWidget(bg_status_label, 1)
        
        select_bg_btn = QPushButton("Select Image")
        select_bg_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
                color: #ffffff;
                border: 2px solid #ff69ff;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #00ffff, stop:1 #0088ff);
                border: 2px solid #00ffff;
            }
        """)
        select_bg_btn.clicked.connect(lambda: self.select_background_image(bg_status_label))
        bg_buttons_layout.addWidget(select_bg_btn)
        
        clear_bg_btn = QPushButton("Clear")
        clear_bg_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff0000, stop:1 #8b0000);
                color: #ffffff;
                border: 2px solid #ff4444;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff4444, stop:1 #cc0000);
                border: 2px solid #ff6666;
            }
        """)
        clear_bg_btn.clicked.connect(lambda: self.clear_background_image(bg_status_label))
        bg_buttons_layout.addWidget(clear_bg_btn)
        
        dialog.content_layout.addLayout(bg_buttons_layout)
        dialog.content_layout.addSpacing(20)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("actionBtn")
        apply_btn.clicked.connect(lambda: self.apply_browser_settings(
            font_spin.value(), icon_spin.value(), scale_slider.value(), dialog
        ))
        buttons_layout.addWidget(apply_btn)
        
        close_btn = QPushButton()
        close_icon = load_svg_icon("x.svg")
        if close_icon:
            close_btn.setIcon(close_icon)
            close_btn.setIconSize(QSize(20, 20))
        else:
            close_btn.setText("CLOSE")
        close_btn.setObjectName("closeBtn")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(dialog.close)
        buttons_layout.addWidget(close_btn)
        
        dialog.content_layout.addLayout(buttons_layout)
        
        # Install event filters
        dialog.install_filters_recursively(dialog.content_widget)
        
        dialog.exec()
    
    def apply_browser_settings(self, font_size, icon_size, layout_scale, dialog):
        self.font_size = font_size
        self.icon_size = icon_size
        self.layout_scale = layout_scale
        
        # Apply zoom to current browser based on layout scale
        browser = self.current_browser()
        if browser:
            zoom_factor = layout_scale / 100.0
            browser.setZoomFactor(zoom_factor)
        
        QMessageBox.information(self, "Settings Applied", 
                               f"Browser settings updated:\nFont: {font_size}px\nIcons: {icon_size}px\nScale: {layout_scale}%\n\nNote: Some changes may require restarting the browser.")
        dialog.close()
    
    def select_background_image(self, status_label):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QImage
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Background Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.PNG *.JPG *.JPEG *.BMP *.GIF)"
        )
        
        if file_path:
            # Verify the file is a valid image using QImage
            try:
                test_image = QImage(file_path)
                if test_image.isNull():
                    QMessageBox.warning(self, "Invalid Image", 
                                       f"The selected file could not be loaded as a valid image.")
                    return
                
                self.background_image = file_path
                status_label.setText(os.path.basename(file_path))
                self.refresh_homepage()
                QMessageBox.information(self, "Background Set", 
                                       f"Background image set to:\n{os.path.basename(file_path)}\n\nGo to homepage to see the new background.")
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                    f"Failed to load background image:\n{str(e)}")
                print(f"Error loading background image: {e}")
    
    def clear_background_image(self, status_label):
        self.background_image = None
        status_label.setText("Default")
        self.refresh_homepage()
        QMessageBox.information(self, "Background Cleared", "Background image reset to default.")
    
    def show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #3d0a5e, stop:1 #2d0a4e);
                color: #00ffff;
                border: 2px solid #ff10f0;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                background: transparent;
                padding: 12px 25px;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ff10f0, stop:1 #8b008b);
            }
        """)
        
        browser_settings_action = QAction("Browser Settings", self)
        browser_settings_action.triggered.connect(self.show_browser_settings)
        menu.addAction(browser_settings_action)
        
        menu.addSeparator()
        
        history_action = QAction("History", self)
        history_action.triggered.connect(self.show_history)
        menu.addAction(history_action)
        
        starred_action = QAction("Starred Pages", self)
        starred_action.triggered.connect(self.show_favorites)
        menu.addAction(starred_action)
        
        # Show menu below the settings button
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))
        
    def apply_vice_city_style(self):
        style = """
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1a0033, stop:1 #0d0019);
            border: 1px solid #ff10f0;
        }
        
        QWidget#titleBar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #3d0a5e, stop:1 #2d0a4e);
            border-bottom: 2px solid #ff10f0;
        }
        
        QPushButton#windowButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff69ff, stop:1 #ff10f0);
            color: #ffffff;
            border: 2px solid #ff69ff;
            border-radius: 5px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#windowButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ffa6ff, stop:1 #ff69ff);
            border: 2px solid #ffa6ff;
        }
        
        QPushButton#closeButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff4444, stop:1 #cc0000);
            color: #ffffff;
            border: 2px solid #ff6666;
            border-radius: 5px;
            font-weight: bold;
            font-size: 14px;
        }
        
        QPushButton#closeButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff6666, stop:1 #ff4444);
            border: 2px solid #ff8888;
        }
        
        QWidget#tabsContainer {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #2d0a4e, stop:1 #1a0033);
            padding: 0px;
            margin: 0px;
        }
        
        QToolBar#navbar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #2d0a4e, stop:1 #1a0033);
            border: 2px solid #ff10f0;
            border-radius: 8px;
            padding: 10px;
            spacing: 8px;
            margin: 5px;
        }
        
        QToolBar::separator {
            background: #ff10f0;
            width: 2px;
            margin: 5px 8px;
        }
        
        QPushButton#iconButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff69ff;
            border-radius: 8px;
            font-weight: bold;
            font-size: 20px;
            font-family: 'Arial Black', sans-serif;
        }
        
        QPushButton#iconButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff69ff, stop:1 #ff10f0);
            border: 2px solid #ffa6ff;
        }
        
        QPushButton#iconButton:pressed {
            background: #8b008b;
            border: 2px solid #ff10f0;
        }
        
        QPushButton#zoomControlBtn {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff10f0;
            border-radius: 6px;
            font-weight: bold;
            font-size: 16px;
        }
        
        QPushButton#zoomControlBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #00ffff, stop:1 #0088ff);
            border: 2px solid #00ffff;
        }
        
        QPushButton#zoomControlBtn:pressed {
            background: #0066cc;
            border: 2px solid #00ffff;
        }
        
        QPushButton#zoomButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff10f0;
            border-radius: 6px;
            font-weight: bold;
            font-size: 10px;
            font-family: Arial, sans-serif;
        }
        
        QPushButton#zoomButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #00ffff, stop:1 #0088ff);
            border: 2px solid #00ffff;
        }
        
        QPushButton#zoomButton:pressed {
            background: #0066cc;
            border: 2px solid #00ffff;
        }
        
        QPushButton#newTabButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #00ffff, stop:1 #0088ff);
            color: #000000;
            border: 2px solid #00ffff;
            border-radius: 20px;
            font-weight: bold;
            font-size: 20px;
            font-family: 'Arial Black', sans-serif;
        }
        
        QPushButton#newTabButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #66ffff, stop:1 #00ffff);
            border: 2px solid #66ffff;
        }
        
        QPushButton#newTabButton:pressed {
            background: #0088ff;
        }
        
        
        QLineEdit#urlBar {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1a1a2e, stop:1 #0f0f1e);
            color: #00ffff;
            border: 2px solid #ff10f0;
            border-radius: 8px;
            padding: 0 15px;
            font-size: 14px;
            font-family: 'Courier New', monospace;
            selection-background-color: #ff10f0;
            selection-color: #ffffff;
        }
        
        QLineEdit#urlBar:focus {
            border: 2px solid #00ffff;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #252538, stop:1 #1a1a2e);
        }
        
        QComboBox#searchEngineCombo {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff10f0;
            border-radius: 6px;
            padding: 0 8px;
            font-weight: bold;
            font-size: 11px;
        }
        
        QComboBox#searchEngineCombo:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #00ffff, stop:1 #0088ff);
            border: 2px solid #00ffff;
        }
        
        QComboBox#searchEngineCombo::drop-down {
            border: none;
            background: transparent;
            width: 20px;
        }
        
        QComboBox#searchEngineCombo::down-arrow {
            image: none;
            background: transparent;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #ffffff;
        }
        
        QComboBox#searchEngineCombo QAbstractItemView {
            background: #2d0a4e;
            color: #ff69ff;
            border: 2px solid #ff10f0;
            selection-background-color: #ff10f0;
            selection-color: #ffffff;
            font-size: 11px;
        }
        
        QTabWidget::pane {
            border: none;
            background: #0d0019;
            margin: 0px;
            padding: 0px;
        }
        
        QTabBar::tab {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #2d0a4e, stop:1 #1a0033);
            color: #ff69ff;
            border: 2px solid #8b008b;
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            padding: 8px 16px;
            margin-right: 2px;
            font-weight: bold;
            font-size: 12px;
        }
        
        QTabBar::tab:selected {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff69ff;
            border-bottom: none;
        }
        
        QTabBar::tab:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #3d1a5e, stop:1 #2d0a4e);
            border: 2px solid #ff10f0;
        }
        
        QTabBar::tab:selected:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #ff10f0, stop:1 #8b008b);
            color: #ffffff;
            border: 2px solid #ff69ff;
            border-bottom: none;
        }
        
        QMessageBox {
            background: #1a0033;
            color: #ff69ff;
        }
        
        QMessageBox QPushButton {
            background: #ff10f0;
            color: #ffffff;
            border: 2px solid #ff69ff;
            border-radius: 5px;
            padding: 5px 15px;
            font-weight: bold;
        }
        """
        
        self.setStyleSheet(style)
        
    def get_resize_direction(self, pos):
        rect = self.rect()
        x, y = pos.x(), pos.y()
        
        on_left = x <= self.resize_margin
        on_right = x >= rect.width() - self.resize_margin
        on_top = y <= self.resize_margin
        on_bottom = y >= rect.height() - self.resize_margin
        
        if on_top and on_left:
            return 'top_left'
        elif on_top and on_right:
            return 'top_right'
        elif on_bottom and on_left:
            return 'bottom_left'
        elif on_bottom and on_right:
            return 'bottom_right'
        elif on_left:
            return 'left'
        elif on_right:
            return 'right'
        elif on_top:
            return 'top'
        elif on_bottom:
            return 'bottom'
        return None
    
    def update_cursor(self, direction):
        if direction in ['top', 'bottom']:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif direction in ['left', 'right']:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction in ['top_left', 'bottom_right']:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction in ['top_right', 'bottom_left']:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            self.resize_direction = self.get_resize_direction(event.pos())
            if self.resize_direction:
                # Try using native system resize for better Linux/X11 support
                handle = self.windowHandle()
                if handle and hasattr(handle, 'startSystemResize'):
                    edges = self.get_qt_edges(self.resize_direction)
                    if edges:
                        handle.startSystemResize(edges)
                        event.accept()
                        return
                
                # Fallback to manual resize
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def get_qt_edges(self, direction):
        """Convert string direction to Qt.Edges"""
        from PyQt6.QtCore import Qt
        edges = Qt.Edge(0)
        
        if 'left' in direction:
            edges |= Qt.Edge.LeftEdge
        if 'right' in direction:
            edges |= Qt.Edge.RightEdge
        if 'top' in direction:
            edges |= Qt.Edge.TopEdge
        if 'bottom' in direction:
            edges |= Qt.Edge.BottomEdge
        
        return edges
    
    def mouseMoveEvent(self, event):
        if self.resizing and self.resize_direction:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            geo = self.resize_start_geometry
            
            x = geo.x()
            y = geo.y()
            width = geo.width()
            height = geo.height()
            
            if 'left' in self.resize_direction:
                new_width = width - delta.x()
                if new_width >= self.minimumWidth():
                    x = geo.x() + delta.x()
                    width = new_width
            if 'right' in self.resize_direction:
                width = max(self.minimumWidth(), width + delta.x())
            if 'top' in self.resize_direction:
                new_height = height - delta.y()
                if new_height >= self.minimumHeight():
                    y = geo.y() + delta.y()
                    height = new_height
            if 'bottom' in self.resize_direction:
                height = max(self.minimumHeight(), height + delta.y())
            
            self.setGeometry(x, y, width, height)
            event.accept()
            return
        
        if not self.isMaximized():
            direction = self.get_resize_direction(event.pos())
            self.update_cursor(direction)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            self.resize_direction = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        super().mouseReleaseEvent(event)
    
    def eventFilter(self, obj, event):
        """Forward mouse events from child widgets to main window for edge detection"""
        from PyQt6.QtCore import QEvent, QPointF
        from PyQt6.QtGui import QMouseEvent
        
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            if not isinstance(event, QMouseEvent):
                return super().eventFilter(obj, event)
            
            # Map event position from child widget to main window coordinates
            global_pos = obj.mapToGlobal(event.pos())
            local_pos = self.mapFromGlobal(global_pos)
            
            # Check if we're near a resize edge
            direction = self.get_resize_direction(local_pos)
            if direction and not self.isMaximized():
                # Create a new mouse event with coordinates in main window space
                # Convert QPoint to QPointF for PyQt6 compatibility
                new_event = QMouseEvent(
                    event.type(),
                    QPointF(local_pos),
                    QPointF(global_pos),
                    event.button(),
                    event.buttons(),
                    event.modifiers()
                )
                
                # Forward to main window's mouse event handlers
                if event.type() == QEvent.Type.MouseButtonPress:
                    self.mousePressEvent(new_event)
                elif event.type() == QEvent.Type.MouseMove:
                    self.mouseMoveEvent(new_event)
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self.mouseReleaseEvent(new_event)
                
                return True  # Event handled, stop propagation
        
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        self.conn.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("vicebrowser")
    
    window = ViceCityBrowser()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
