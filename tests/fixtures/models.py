"""Sample Python models module for testing."""


class BaseModel:
    def save(self):
        pass


class Product(BaseModel):
    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
