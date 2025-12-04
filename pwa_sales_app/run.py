# run.py
from flask import Flask
from views.main_views import main_bp
from database.db import init_db
init_db()

def create_app() -> Flask:
    """
    Flask アプリケーションを作成し、Blueprint と DB を初期化する。
    Render（本番）も、ローカル開発も、この関数を通してアプリを作る。
    """
    app = Flask(__name__)

    # DB 初期化（テーブルがなければ作成）
    init_db()

    # Blueprint 登録
    app.register_blueprint(main_bp)

    return app

# --------------------------
# ローカル実行（開発用）
# --------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=5002,        # 本地端口，你可以改为 5001 等
        debug=True
    )