import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton

# Import the required functions from tpo_assets
from tpo_assets import add_icon_search_dir, clear_icon_cache, icon

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from pathlib import Path
class MainWindow(QMainWindow):
    def __init__(self):
        clear_icon_cache()
        super().__init__()
        self.setWindowTitle("Icon Buttons Example")
        self.resize(300, 200)
        self.setStyleSheet("""
        color:#00ff00""")
        # Add the directory where your icon files are stored
        add_icon_search_dir("/home/john/myproject/assets/icons")
        
        # Obtain icons using the tpo_assets.icon helper
        save_icon = icon(".py", foreground="#ff000022")   
        icon2 = icon("ui/power.svg",foreground="#00000022")
        explicit_text_icon = icon("files/txt")  # icon from a subdirectory "files/txt"
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create buttons and assign icons
        btn_save = QPushButton()
        btn_save.setIcon(save_icon)
        btn_save.setFixedSize(100,100)
        btn_save.setIconSize(QSize(80, 80))
        layout.addWidget(btn_save)

        btn_text = QPushButton("Text File")
        btn_text.setIcon(icon2)
        layout.addWidget(btn_text)

        btn_explicit = QPushButton("Explicit")
        btn_explicit.setIcon(explicit_text_icon)
        layout.addWidget(btn_explicit)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
