"""E-commerce application models for multi-tenant SaaS.

Each tenant gets their own schema with these tables:
- customers: Customer information
- products: Product catalog
- orders: Order headers
- order_items: Order line items
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
# from models import Base

Base = declarative_base()

class Customer(Base):
    """Customer model - each tenant's customers."""

    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(100))
    country = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    test_per_tenant_customer = Column(String(1),nullable=True)
    # test_tenant_specific_field = Column(String(100), nullable=True)
    # new_test = Column(String(100), nullable=True)


    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<Customer(id={self.id}, email='{self.email}', name='{self.full_name}')>"


class Product(Base):
    """Product catalog model."""

    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    price = Column(Integer, nullable=False)  # Price in cents
    cost = Column(Integer, nullable=False, default=0)  # Cost in cents
    stock_quantity = Column(Integer, default=0)
    category = Column(String(100), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    test_per_tenant_product = Column(String(1),nullable=True)


    # Relationships
    order_items = relationship("OrderItem", back_populates="product")

    @property
    def profit_margin(self):
        """Calculate profit margin percentage."""
        if self.price == 0:
            return 0
        return ((self.price - self.cost) / self.price) * 100

    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}', price=${self.price/100:.2f})>"


class Order(Base):
    """Order header model."""

    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False, index=True)
    status = Column(String(50), default='pending', index=True)  # pending, processing, shipped, delivered, cancelled
    total_amount = Column(Integer, nullable=False, default=0)  # Total in cents
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    shipped_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    # test_per_tenant = Column(String(1),nullable=True)


    # Relationships
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    @property
    def item_count(self):
        """Total number of items in order."""
        return sum(item.quantity for item in self.items)

    def __repr__(self):
        return f"<Order(id={self.id}, number='{self.order_number}', status='{self.status}', total=${self.total_amount/100:.2f})>"


class OrderItem(Base):
    """Order line items model."""

    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Integer, nullable=False)  # Price at time of order (in cents)
    subtotal = Column(Integer, nullable=False)  # quantity * unit_price
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return f"<OrderItem(id={self.id}, product_id={self.product_id}, qty={self.quantity}, subtotal=${self.subtotal/100:.2f})>"

class AlembicVersion(Base):
    __tablename__ = "alembic_version"
    version_num = Column(String(32), primary_key=True,index=True)


# Note: These models are imported in alembic/env.py for autogenerate
