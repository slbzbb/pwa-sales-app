# run.py
from flask import Flask
from views.main_views import main_bp
from database.db import init_db, ensure_default_users


def create_app() -> Flask:
    """
    Flask アプリケーションを作成し、Blueprint と DB を初期化する。
    Render（本番）も、ローカル開発も、この関数を通してアプリを作る。
    """
    app = Flask(__name__)

    # session 用 secret key（可以以后放到环境变量）
    app.secret_key = "change_me_to_a_random_secret_key_2025"

    # DB 初期化（建表）
    init_db()

    # 用户初始化（若无用户，创建默认账号和后门账号）
    ensure_default_users()

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
        port=5002,      # 你现在在用 5002，就保持这个
        debug=True
    )