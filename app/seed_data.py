from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session
from . import models

# Sample data
product_data = [
    {"name": "Laptop", "category": "Electronics", "price": 999.99},
    {"name": "Smartphone", "category": "Electronics", "price": 699.99},
    {"name": "Headphones", "category": "Electronics", "price": 149.99},
    {"name": "T-shirt", "category": "Clothing", "price": 19.99},
    {"name": "Jeans", "category": "Clothing", "price": 49.99},
    {"name": "Sneakers", "category": "Footwear", "price": 79.99},
    {"name": "Coffee Maker", "category": "Appliances", "price": 89.99},
    {"name": "Blender", "category": "Appliances", "price": 49.99},
]

customer_data = [
    {"name": "John Doe", "email": "john@example.com"},
    {"name": "Jane Smith", "email": "jane@example.com"},
    {"name": "Bob Johnson", "email": "bob@example.com"},
    {"name": "Alice Brown", "email": "alice@example.com"},
    {"name": "Charlie Wilson", "email": "charlie@example.com"},
]

def seed_database(db: Session):
    # Clear existing data
    db.query(models.OrderItem).delete()
    db.query(models.Order).delete()
    db.query(models.Customer).delete()
    db.query(models.Product).delete()
    
    # Add products
    products = []
    for data in product_data:
        product = models.Product(**data)
        db.add(product)
        products.append(product)
    
    # Add customers
    customers = []
    for data in customer_data:
        customer = models.Customer(**data)
        db.add(customer)
        customers.append(customer)
    
    # Commit to get IDs
    db.commit()
    
    # Add orders (last 30 days)
    for _ in range(50):  # Create 50 orders
        customer = random.choice(customers)
        order_date = datetime.utcnow() - timedelta(days=random.randint(0, 30))
        
        # Create order
        order = models.Order(
            customer_id=customer.id,
            order_date=order_date,
            total_amount=0
        )
        db.add(order)
        db.flush()  # Get order ID
        
        # Add 1-5 items to order
        total_amount = 0
        for _ in range(random.randint(1, 5)):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            unit_price = product.price
            
            order_item = models.OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price
            )
            db.add(order_item)
            total_amount += quantity * unit_price
        
        # Update order total
        order.total_amount = total_amount
    
    # Commit all changes
    db.commit() 