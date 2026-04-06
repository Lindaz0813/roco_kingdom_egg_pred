"""
Roco Kingdom Egg Predictor — Flask web app.
Run: python app.py
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from flask import Flask, render_template, request, jsonify

from predictor import predict

app = Flask(__name__)

BASE_DIR  = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "pokemon.json")
# On Fly.io the volume is mounted at /data; locally falls back to data/observations.db
DB_PATH   = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "observations.db"))


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                egg_size  REAL    NOT NULL,
                egg_weight REAL   NOT NULL,
                pokemon   TEXT    NOT NULL,
                timestamp TEXT    NOT NULL
            )
        """)
    # Migrate from observations.json if it exists and DB is empty
    json_path = os.path.join(BASE_DIR, "data", "observations.json")
    if os.path.exists(json_path):
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            if count == 0:
                with open(json_path, "r", encoding="utf-8") as f:
                    old = json.load(f)
                for o in old:
                    conn.execute(
                        "INSERT INTO observations (egg_size, egg_weight, pokemon, timestamp) VALUES (?,?,?,?)",
                        (o["egg_size"], o["egg_weight"], o["pokemon"], o.get("timestamp", datetime.now().isoformat()))
                    )
                print(f"Migrated {len(old)} observations from JSON to SQLite.")


def load_observations() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT egg_size, egg_weight, pokemon, timestamp FROM observations ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Pokemon data (read-only JSON, never changes at runtime)
# ---------------------------------------------------------------------------

def load_pokemon() -> list[dict]:
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    pokemon_data = load_pokemon()
    hatchable = sorted(
        [p["name"] for p in pokemon_data if p.get("is_hatchable", True)]
    )
    has_data = len(pokemon_data) > 0
    return render_template("index.html", hatchable_pokemon=hatchable, has_data=has_data)


@app.route("/predict", methods=["POST"])
def predict_route():
    body = request.get_json()
    if not body:
        return jsonify({"error": "No JSON body"}), 400

    try:
        egg_size   = float(body["size"])
        egg_weight = float(body["weight"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid size or weight"}), 400

    if egg_size <= 0 or egg_weight <= 0:
        return jsonify({"error": "Size and weight must be positive"}), 400

    pokemon_data = load_pokemon()
    if not pokemon_data:
        return jsonify({"error": "No pokemon data found. Please run the scraper first."}), 503

    observations = load_observations()
    results = predict(egg_size, egg_weight, pokemon_data, observations)

    return jsonify({
        "results": results,
        "egg_size": egg_size,
        "egg_weight": egg_weight,
        "expected_size_range":   f"{egg_size   * 2.2 - 0.03:.2f}~{egg_size   * 3.2 + 0.15:.2f}M",
        "expected_weight_range": f"{egg_weight * 1.9 - 0.03:.2f}~{egg_weight * 3.2 + 0.15:.2f}KG",
    })


@app.route("/confirm", methods=["POST"])
def confirm():
    body = request.get_json()
    if not body:
        return jsonify({"error": "No JSON body"}), 400

    try:
        egg_size     = float(body["size"])
        egg_weight   = float(body["weight"])
        pokemon_name = str(body["pokemon"]).strip()
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid data"}), 400

    if not pokemon_name:
        return jsonify({"error": "Pokemon name required"}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO observations (egg_size, egg_weight, pokemon, timestamp) VALUES (?,?,?,?)",
            (egg_size, egg_weight, pokemon_name, datetime.now().isoformat())
        )
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    return jsonify({"message": f"Confirmed: {pokemon_name}", "total": total})


@app.route("/observations", methods=["GET"])
def get_observations():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, egg_size, egg_weight, pokemon, timestamp FROM observations ORDER BY id DESC"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    return jsonify({"observations": [dict(r) for r in rows], "total": total})


@app.route("/observations/<int:obs_id>", methods=["DELETE"])
def delete_observation(obs_id):
    with get_db() as conn:
        row = conn.execute("SELECT pokemon FROM observations WHERE id=?", (obs_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        conn.execute("DELETE FROM observations WHERE id=?", (obs_id,))
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    return jsonify({"message": f"Removed: {row['pokemon']}", "total": total})


@app.route("/pokemon", methods=["GET"])
def get_pokemon():
    pokemon_data = load_pokemon()
    hatchable = [p for p in pokemon_data if p.get("is_hatchable", True)]
    return jsonify({"pokemon": hatchable, "total": len(hatchable)})


@app.route("/status")
def status():
    pokemon_data = load_pokemon()
    hatchable = [p for p in pokemon_data if p.get("is_hatchable", True)]
    with get_db() as conn:
        total_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    return jsonify({
        "total_pokemon":      len(pokemon_data),
        "hatchable_pokemon":  len(hatchable),
        "total_observations": total_obs,
        "data_loaded":        len(pokemon_data) > 0,
    })


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

init_db()

if __name__ == "__main__":
    print("=== Roco Kingdom Egg Predictor ===")
    if not os.path.exists(DATA_PATH):
        print("WARNING: No pokemon data found!")
        print("Run 'python scraper.py' first to scrape wiki data.\n")
    else:
        data = load_pokemon()
        hatchable = [p for p in data if p.get("is_hatchable", True)]
        print(f"Loaded {len(data)} pokemon ({len(hatchable)} hatchable)")
    print("Starting server at http://127.0.0.1:5000\n")
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
