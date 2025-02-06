from videoseries import getOrders

print("Fetching Orders...")
orders = getOrders()
print(orders)  # Print the retrieved orders


import requests
response = requests.get("http://127.0.0.1:5000/api/orders")
print(response.json())

