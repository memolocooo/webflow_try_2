from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import os
from videoseries import getOrders, getFees
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Fetch credentials from environment variables
LWA_APP_ID = os.getenv("LWA_APP_ID")
LWA_CLIENT_SECRET = os.getenv("LWA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # Add this for Render

# Ensure credentials are available
if not LWA_APP_ID or not LWA_CLIENT_SECRET or not DATABASE_URL:
    raise Exception("Environment variables are missing. Check your .env file.")

app = Flask(__name__)

# Configure PostgreSQL database for Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize database tables
with app.app_context():
    db.create_all()

# Define database models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    order_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    total = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=False)

@app.route('/customers', methods=['POST'])
def add_customer():
    data = request.json
    if not data or 'name' not in data or 'email' not in data:
        return jsonify({'error': 'Missing name or email'}), 400

    try:
        new_customer = Customer(name=data['name'], email=data['email'])
        db.session.add(new_customer)
        db.session.commit()
        return jsonify({'message': 'Customer added successfully', 'customer_id': new_customer.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@app.route('/user/orders', methods=['GET'])
def user_orders():
    access_token = request.headers.get("Authorization")  # Get token from frontend

    if not access_token:
        return jsonify({"error": "Missing access token"}), 401

    # Fetch orders using the access token
    headers = {"Authorization": f"Bearer {access_token}"}
    orders_url = "https://sellingpartnerapi-na.amazon.com/orders/v0/orders"  # Adjust for region

    try:
        response = requests.get(orders_url, headers=headers)
        response.raise_for_status()
        orders = response.json()
        return jsonify(orders), 200
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/orders', methods=['POST'])
def add_order():
    data = request.json
    required_keys = ['customer_id', 'order_id', 'status', 'total', 'purchase_date']
    
    if not all(key in data for key in required_keys):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        new_order = Order(
            customer_id=data['customer_id'],
            order_id=data['order_id'],
            status=data['status'],
            total=data['total'],
            purchase_date=datetime.strptime(data['purchase_date'], '%Y-%m-%dT%H:%M:%SZ')
        )
        db.session.add(new_order)
        db.session.commit()
        return jsonify({'message': 'Order added successfully', 'order_id': new_order.order_id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/customers/<int:customer_id>/orders', methods=['GET'])
def get_orders(customer_id):
    orders = Order.query.filter_by(customer_id=customer_id).all()
    if not orders:
        return jsonify({'message': 'No orders found for this customer'}), 404
    
    result = [
        {
            'order_id': order.order_id,
            'status': order.status,
            'total': order.total,
            'purchase_date': order.purchase_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        for order in orders
    ]
    return jsonify(result), 200

def fetch_amazon_orders(access_token, created_after):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://sellingpartnerapi-na.amazon.com/orders/v0/orders?CreatedAfter={created_after}'

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


# Route to handle Amazon authorization code exchange
@app.route('/auth/amazon', methods=['POST'])
def amazon_auth():
    auth_code = request.json.get("code")  # Get the authorization code from the frontend
    if not auth_code:
        return jsonify({"error": "Authorization code is required"}), 400

    try:
        # Exchange the authorization code for an access token
        token_url = "https://api.amazon.com/auth/o2/token"
        payload = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": "https://guillermos-amazing-site-b0c75a.webflow.io/callback",
            "client_id": LWA_APP_ID,  # ✅ FIXED: Use the correct variable
            "client_secret": LWA_CLIENT_SECRET,  # ✅ FIXED: Use the correct variable
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = requests.post(token_url, data=payload, headers=headers)
        token_data = token_response.json()

        # Check for access token
        if "access_token" not in token_data:
            return jsonify({"error": "Failed to obtain access token"}), 400

        # Fetch user profile with the access token
        user_info_url = "https://api.amazon.com/user/profile"
        user_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        user_response = requests.get(user_info_url, headers=user_headers)
        user_data = user_response.json()

        # Return user information
        return jsonify({"access_token": token_data["access_token"], "user": user_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/orders', methods=['GET'])
def api_get_orders():
    try:
        orders = getOrders()
        return jsonify(orders), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fees', methods=['GET'])
def api_get_fees():
    asin = request.args.get('asin')
    price = request.args.get('price')
    if not asin or not price:
        return jsonify({"error": "ASIN and price are required"}), 400
    try:
        fees = getFees(asin, price)
        return jsonify({"fees": fees}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/')
def home():
    return "Welcome to the Flask App! API is running."

if __name__ == "__main__":
    app.run()






