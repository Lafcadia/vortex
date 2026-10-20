from pathlib import Path

from flask import Flask  # type: ignore[reportMissingImports]
from endpoints import api_bp


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
INDEX_FILE = Path(__file__).with_name("index.html")
ARG_PACK_FILE = Path(__file__).with_name("arg_pack.html")


app.register_blueprint(api_bp)


@app.get("/")
def read_root():
    return INDEX_FILE.read_text(encoding="utf-8")


@app.get("/arg-pack")
def read_arg_pack():
    return ARG_PACK_FILE.read_text(encoding="utf-8")

def main():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()