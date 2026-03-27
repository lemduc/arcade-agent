"""Sample Python module for testing."""

from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str


class UserService:
    def __init__(self):
        self.users = []

    def add_user(self, user: User) -> None:
        self.users.append(user)

    def get_user(self, name: str) -> User | None:
        for user in self.users:
            if user.name == name:
                return user
        return None


def main():
    service = UserService()
    service.add_user(User("Alice", "alice@example.com"))
