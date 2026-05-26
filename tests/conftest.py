"""
Гарантирует, что корень проекта есть в sys.path при запуске pytest.
Положи этот файл в папку tests/ (или в корень проекта).
"""
import sys, os
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)