from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests

app = Flask(__name__)

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Baramericas1250@localhost:5432/webflow_database'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    new_customer = Customer(name=data['name'], email=data['email'])
    db.session.add(new_customer)
    db.session.commit()
    return jsonify({'message': 'Customer added successfully'}), 201


@app.route('/orders', methods=['POST'])
def add_order():
    data = request.json
    new_order = Order(
        customer_id=data['customer_id'],
        order_id=data['order_id'],
        status=data['status'],
        total=data['total'],
        purchase_date=datetime.strptime(data['purchase_date'], '%Y-%m-%dT%H:%M:%SZ')
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({'message': 'Order added successfully'}), 201


@app.route('/customers/<int:customer_id>/orders', methods=['GET'])
def get_orders(customer_id):
    orders = Order.query.filter_by(customer_id=customer_id).all()
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
        'Authorization': f'Bearer {access_token}',
        'x-amz-access-token': access_token,
    }
    url = f'https://sellingpartnerapi-na.amazon.com/orders/v0/orders?CreatedAfter={created_after}'
    response = requests.get(url, headers=headers)
    return response.json()
