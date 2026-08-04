"""DeepTutor — agent-native intelligent learning companion."""

import os

# NLTK 3.9+ 安全钩子 (nltk/inisec.py) 会拦截「从当前工作目录导入模块」以防御
# 模块劫持 (CWE-427)。但当虚拟环境 .venv 位于项目根目录内时，site-packages
# 中的合法依赖（如 regex）会被误判为「工作目录中的可疑模块」而抛出 ImportError，
# 阻断 RAG 索引流程。此处必须在任何 nltk 导入之前禁用该钩子。
# 参考: nltk/inisec.py 第 156 行，支持 NLTK_DISABLE_IMPORT_SECURITY=1 完全禁用。
os.environ.setdefault("NLTK_DISABLE_IMPORT_SECURITY", "1")
