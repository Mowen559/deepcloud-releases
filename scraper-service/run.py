"""
PyInstaller 打包入口

app/main.py 内部用的是相对导入（from .extractor import ...），直接把它当脚本跑会
报 "attempted relative import with no known parent package"，所以需要这个薄入口
以包的方式导入后再启动。
"""

from app.main import main

if __name__ == "__main__":
    main()
