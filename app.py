import psycopg2
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, redirect, session
import os
from dotenv import load_dotenv
from flask_cors import CORS
from flask_session import Session



# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
CORS(app, supports_credentials=True, origins=["https://guillermos-amazing-site-b0c75a.webflow.io"])

# ✅ Ensure session is properly configured before using `Session(app)`
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_FILE_DIR"] = "./flask_session_data"  # Ensure this exists

# ✅ Initialize Flask-Session after setting config
Session(app)


# Load environment variables
load_dotenv()


print("✅ Connected to PostgreSQL!")

# Amazon OAuth Variables
LWA_APP_ID = os.getenv("LWA_APP_ID")
LWA_CLIENT_SECRET = os.getenv("LWA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTH_URL = os.getenv("AUTH_URL")
TOKEN_URL = os.getenv("TOKEN_URL")
# Use Render's database URL
DATABASE_URL = os.getenv("DB_URL")

# Ensure DATABASE_URL is set correctly
if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL is missing. Check Render Environment Variables.")

# Connect to PostgreSQL
DB_CONN = psycopg2.connect(DATABASE_URL, sslmode="require")


def save_oauth_tokens(selling_partner_id, access_token, refresh_token, expires_in):
    """Save Amazon OAuth credentials to PostgreSQL."""
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    with DB_CONN.cursor() as cur:
        cur.execute("""
            INSERT INTO amazon_oauth_tokens (selling_partner_id, access_token, refresh_token, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (selling_partner_id) DO UPDATE 
            SET access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at;
        """, (selling_partner_id, access_token, refresh_token, expires_at))

        DB_CONN.commit()

@app.route('/start-oauth')
def start_oauth():
    """Redirects user to Amazon OAuth login page."""
    amazon_auth_url = (
        f"{AUTH_URL}"
        f"?application_id={LWA_APP_ID}"
        f"&state=random_state_value"
        f"&redirect_uri={REDIRECT_URI}"
        f"&version=beta"
    )
    return redirect(amazon_auth_url)

@app.route('/callback')
def callback():
    """Handles the OAuth callback and stores credentials in PostgreSQL."""
    auth_code = request.args.get("spapi_oauth_code")
    selling_partner_id = request.args.get("selling_partner_id")

    if not auth_code or not selling_partner_id:
        return jsonify({"error": "Missing parameters"}), 400

    # Exchange Authorization Code for Tokens
    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": LWA_APP_ID,
        "client_secret": LWA_CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    token_data = response.json()

    if "access_token" not in token_data:
        return jsonify({"error": "Failed to exchange token", "details": token_data}), 400

    # Store in PostgreSQL
    save_oauth_tokens(
        selling_partner_id,
        token_data["access_token"],
        token_data["refresh_token"],
        token_data["expires_in"]
    )

@app.route("/dashboard")
def dashboard():
    """Returns stored token for Webflow frontend."""
    print("🚀 Debug: Checking Flask session data:", dict(session))  # ✅ Debugging log

    if "access_token" in session and "refresh_token" in session:
        debug_response = {
            "message": "Amazon SP-API Connected Successfully!",
            "access_token": session["access_token"],
            "refresh_token": session["refresh_token"],
            "selling_partner_id": session.get("selling_partner_id"),
            "expires_in": session.get("expires_in", 3600),  # Default to 1 hour if missing
            "token_type": "bearer"
        }

        print("✅ OAuth Debug Output:", debug_response)  # ✅ Log the JSON response

        return jsonify(debug_response), 200

    print("❌ Error: No tokens found in session!")  # ✅ Debugging log
    return jsonify({"error": "User not authenticated"}), 401


@app.route("/db-test")
def db_test():
    try:
        with DB_CONN.cursor() as cur:
            cur.execute("SELECT 1")
            return jsonify({"message": "✅ PostgreSQL Connection Successful!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


    return redirect("https://guillermos-amazing-site-b0c75a.webflow.io/dashboard")


if __name__ == "__main__":
    from os import environ
    app.run(host="0.0.0.0", port=int(environ.get("PORT", 5000)))





